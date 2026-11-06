#!/usr/bin/env python3
"""Estima el costo mensual desde `terraform show -json`.

Usa la API publica Azure Retail Prices: gratis, sin cuenta y sin clave. Solo depende de la
biblioteca estandar. El consumo no aparece en un plan, por eso se declara en usage.json.
"""

import argparse
import json
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

PRICES_URL = "https://prices.azure.com/api/retail/prices"
HERE = Path(__file__).parent

# clave: (filtro OData, meterName, unidad esperada)
METERS = {
    "aca_vcpu_second": (
        "serviceName eq 'Azure Container Apps' and skuName eq 'Standard'",
        "Standard vCPU Active Usage",
        "1 Second",
    ),
    "aca_gib_second": (
        "serviceName eq 'Azure Container Apps' and skuName eq 'Standard'",
        "Standard Memory Active Usage",
        "1 GiB Second",
    ),
    "aca_million_requests": (
        "serviceName eq 'Azure Container Apps' and skuName eq 'Standard'",
        "Standard Requests",
        "1M",
    ),
    "sql_vcore_hour": (
        "serviceName eq 'SQL Database' and skuName eq '1 vCore' and "
        "productName eq 'SQL Database General Purpose - Serverless - Compute Gen5'",
        "vCore",
        "1 Hour",
    ),
    "sql_gb_month": (
        "serviceName eq 'SQL Database' and skuName eq 'General Purpose' and "
        "productName eq 'SQL Database Single/Elastic Pool General Purpose - Storage'",
        "General Purpose Data Stored",
        "1 GB/Month",
    ),
    "kv_10k_operations": (
        "serviceName eq 'Key Vault' and skuName eq 'Standard'",
        "Operations",
        "10K",
    ),
    "log_gb_ingested": (
        "serviceName eq 'Log Analytics' and skuName eq 'Analytics Logs'",
        "Analytics Logs Data Ingestion",
        "1 GB",
    ),
    "blob_gb_month": (
        "serviceName eq 'Storage' and productName eq 'Blob Storage' and skuName eq 'Hot LRS'",
        "Hot LRS Data Stored",
        "1 GB/Month",
    ),
    "blob_10k_writes": (
        "serviceName eq 'Storage' and productName eq 'Blob Storage' and skuName eq 'Hot LRS'",
        "Hot LRS Write Operations",
        "10K",
    ),
}

# Recursos sin cargo propio: su costo aparece, si lo hay, en los recursos que los usan.
FREE_RESOURCES = {
    "azurerm_resource_group",
    "azurerm_role_assignment",
    "azurerm_user_assigned_identity",
    "azurerm_mssql_server",
    "azurerm_mssql_firewall_rule",
    "azurerm_key_vault_secret",
    "azurerm_container_app_environment",  # El plan de consumo no cobra por el ambiente.
    "azurerm_storage_container",
}


class PriceNotFound(Exception):
    pass


def fetch_live_price(key: str, region: str) -> float:
    odata, meter, unit = METERS[key]
    query = f"{odata} and armRegionName eq '{region}' and type eq 'Consumption'"
    url = f"{PRICES_URL}?{urllib.parse.urlencode({'$filter': query})}"
    prices = []
    while url:
        with urllib.request.urlopen(url, timeout=30) as response:
            page = json.load(response)
        prices += [
            item
            for item in page["Items"]
            if item["meterName"] == meter and item["unitOfMeasure"] == unit
        ]
        url = page.get("NextPageLink")
    if not prices:
        raise PriceNotFound(f"Sin precio para {key} en {region}")
    # Algunos medidores son escalonados; la escala mas alta es la estimacion conservadora.
    return max(item["retailPrice"] for item in prices)


class PriceBook:
    """Precios en vivo con respaldo a una copia local, para no bloquearse sin red."""

    def __init__(self, snapshot: dict, offline: bool = False, fetcher=fetch_live_price):
        self.snapshot = snapshot
        self.offline = offline
        self.fetcher = fetcher
        self.cache: dict[tuple[str, str], float] = {}
        self.used_snapshot = False

    def price(self, key: str, region: str) -> float:
        if (key, region) in self.cache:
            return self.cache[(key, region)]
        value = None
        if not self.offline:
            try:
                value = self.fetcher(key, region)
            except OSError as error:
                print(f"Aviso: sin acceso a la API de precios ({error})", file=sys.stderr)
        if value is None:
            try:
                value = self.snapshot[region][key]
            except KeyError as error:
                raise PriceNotFound(f"Sin copia local de {key} en {region}") from error
            self.used_snapshot = True
        self.cache[(key, region)] = value
        return value


@dataclass
class Line:
    environment: str
    address: str
    monthly_usd: float
    detail: str


def walk_resources(module: dict):
    yield from module.get("resources", [])
    for child in module.get("child_modules", []):
        yield from walk_resources(child)


def plan_resources(plan: dict) -> list[dict]:
    root = plan.get("planned_values", {}).get("root_module", {})
    return [r for r in walk_resources(root) if r.get("mode") == "managed"]


def plan_region(resources: list[dict], fallback: str) -> str:
    for resource in resources:
        location = resource.get("values", {}).get("location")
        if location:
            return location.replace(" ", "").lower()
    return fallback


def parse_gib(memory: str) -> float:
    return float(memory.removesuffix("Gi"))


def estimate_plan(name: str, plan: dict, usage: dict, book: PriceBook, grant: dict) -> tuple:
    """Devuelve las lineas de costo y los recursos sin regla de precio."""
    resources = plan_resources(plan)
    region = plan_region(resources, usage.get("default_region", "eastus"))
    lines, unknown = [], []

    for resource in resources:
        kind, values, address = resource["type"], resource.get("values", {}), resource["address"]
        if kind in FREE_RESOURCES or kind.startswith(("random_", "time_")):
            continue
        if kind == "azurerm_container_app":
            lines.append(_container_app(name, address, values, usage, region, book, grant))
        elif kind == "azapi_resource" and "Microsoft.Sql/servers/databases" in values.get("type", ""):
            lines.append(_azapi_database(name, address, values, usage, region, book))
        elif kind == "azurerm_mssql_database":
            lines.append(_paid_database(name, address, usage, region, book))
        elif kind == "azurerm_key_vault":
            operations = usage["key_vault_operations_per_month"]
            cost = operations / 10_000 * book.price("kv_10k_operations", region)
            lines.append(Line(name, address, cost, f"{operations:,} operaciones"))
        elif kind == "azurerm_log_analytics_workspace":
            billable = max(0.0, usage["log_gb_per_month"] - 5.0)
            cost = billable * book.price("log_gb_ingested", region)
            lines.append(Line(name, address, cost, f"{usage['log_gb_per_month']} GB (5 GB gratis)"))
        elif kind == "azurerm_storage_account":
            storage = usage["state_storage_gb"] * book.price("blob_gb_month", region)
            writes = usage["state_writes_per_month"] / 10_000 * book.price("blob_10k_writes", region)
            lines.append(Line(name, address, storage + writes, f"{usage['state_storage_gb']} GB"))
        else:
            unknown.append(address)
    return lines, unknown


def _container_app(env, address, values, usage, region, book, grant) -> Line:
    container = values["template"][0]["container"][0]
    seconds = usage["app_active_hours_per_month"][env] * 3600
    vcpu_seconds = seconds * float(container["cpu"])
    gib_seconds = seconds * parse_gib(container["memory"])
    requests = usage["requests_per_month"][env]

    # La concesion gratuita es por suscripcion: dev y prod consumen de la misma bolsa.
    def consume(name: str, amount: float) -> float:
        covered = min(grant[name], amount)
        grant[name] -= covered
        return amount - covered

    cost = (
        consume("vcpu_seconds", vcpu_seconds) * book.price("aca_vcpu_second", region)
        + consume("gib_seconds", gib_seconds) * book.price("aca_gib_second", region)
        + consume("requests", requests) / 1e6 * book.price("aca_million_requests", region)
    )
    return Line(env, address, cost, f"{seconds / 3600:.0f} h activas, {requests:,} solicitudes")


def _azapi_database(env, address, values, usage, region, book) -> Line:
    properties = values.get("body", {}).get("properties", {})
    behavior = properties.get("freeLimitExhaustionBehavior")
    if properties.get("useFreeLimit") and behavior == "AutoPause":
        return Line(env, address, 0.0, "oferta gratuita; se pausa al agotarla")
    return _paid_database(env, address, usage, region, book)


def _paid_database(env, address, usage, region, book) -> Line:
    vcore_hours = usage["database_vcore_hours_per_month"][env]
    compute = vcore_hours * book.price("sql_vcore_hour", region)
    storage = usage["database_storage_gb"] * book.price("sql_gb_month", region)
    return Line(env, address, compute + storage, f"{vcore_hours} vCore-h sin oferta gratuita")


def estimate(plans: dict[str, dict], usage: dict, book: PriceBook) -> tuple:
    grant = dict(usage["container_apps_free_grant"])
    lines, unknown = [], []
    for name, plan in plans.items():
        plan_lines, plan_unknown = estimate_plan(name, plan, usage, book, grant)
        lines += plan_lines
        unknown += [f"{name}: {address}" for address in plan_unknown]
    return lines, unknown


def render(lines: list[Line], unknown: list[str], budget: float | None) -> str:
    width = max([len(line.address) for line in lines] + [7])
    rows = [f"{'Ambiente':<9} {'Recurso':<{width}} {'USD/mes':>9}  Supuesto"]
    rows += [
        f"{line.environment:<9} {line.address:<{width}} {line.monthly_usd:>9.2f}  {line.detail}"
        for line in lines
    ]
    total = sum(line.monthly_usd for line in lines)
    rows.append(f"{'TOTAL':<9} {'':<{width}} {total:>9.2f}")
    if budget is not None:
        rows.append(f"Presupuesto: {budget:.2f} USD/mes")
    rows += [f"SIN PRECIO: {address}" for address in unknown]
    return "\n".join(rows)


def refresh_snapshot(path: Path, region: str) -> None:
    snapshot = json.loads(path.read_text()) if path.exists() else {}
    snapshot[region] = {key: fetch_live_price(key, region) for key in METERS}
    path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n")


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--plan", action="append", default=[], metavar="AMBIENTE=ARCHIVO",
        help="Plan JSON de terraform; se puede repetir, p. ej. --plan dev=dev.json",
    )
    parser.add_argument("--usage", type=Path, default=HERE / "usage.json")
    parser.add_argument("--snapshot", type=Path, default=HERE / "prices-snapshot.json")
    parser.add_argument("--offline", action="store_true", help="Usa solo la copia local de precios")
    parser.add_argument("--budget", type=float, help="Falla si el total mensual lo supera")
    parser.add_argument("--refresh-snapshot", metavar="REGION", help="Actualiza la copia local")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.refresh_snapshot:
        refresh_snapshot(args.snapshot, args.refresh_snapshot)
        print(f"Copia de precios actualizada para {args.refresh_snapshot}")
        return 0
    if not args.plan:
        print("Indica al menos un --plan AMBIENTE=ARCHIVO", file=sys.stderr)
        return 2

    plans = {}
    for item in args.plan:
        name, _, filename = item.partition("=")
        plans[name] = json.loads(Path(filename).read_text())
    snapshot = json.loads(args.snapshot.read_text()) if args.snapshot.exists() else {}
    book = PriceBook(snapshot, offline=args.offline)
    usage = json.loads(args.usage.read_text())

    try:
        lines, unknown = estimate(plans, usage, book)
    except PriceNotFound as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2

    print(render(lines, unknown, args.budget))
    if book.used_snapshot:
        print("Aviso: se usaron precios de la copia local; pueden estar desactualizados.")
    # Un recurso sin regla volveria engañoso el total, asi que tambien detiene el despliegue.
    if unknown:
        print("Error: agrega una regla de precio para los recursos listados.", file=sys.stderr)
        return 1
    total = sum(line.monthly_usd for line in lines)
    if args.budget is not None and total > args.budget:
        print(f"Error: {total:.2f} USD supera el presupuesto.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
