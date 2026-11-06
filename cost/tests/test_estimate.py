import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))

import estimate as cost  # noqa: E402

PRICES = {
    "aca_vcpu_second": 0.000024,
    "aca_gib_second": 0.000003,
    "aca_million_requests": 0.4,
    "sql_vcore_hour": 0.5,
    "sql_gb_month": 0.1,
    "kv_10k_operations": 0.03,
    "log_gb_ingested": 2.3,
    "blob_gb_month": 0.02,
    "blob_10k_writes": 0.05,
}


def book():
    return cost.PriceBook({"eastus": PRICES}, offline=True)


def usage(**overrides):
    base = json.loads((HERE.parent / "usage.json").read_text())
    base.update(overrides)
    return base


def app(cpu=0.25, memory="0.5Gi"):
    return {
        "address": "module.stack.module.app.azurerm_container_app.this",
        "mode": "managed",
        "type": "azurerm_container_app",
        "values": {"template": [{"container": [{"cpu": cpu, "memory": memory}]}]},
    }


def database(free=True, behavior="AutoPause"):
    return {
        "address": "module.stack.module.database.azapi_resource.free[0]",
        "mode": "managed",
        "type": "azapi_resource",
        "values": {
            "location": "eastus",
            "type": "Microsoft.Sql/servers/databases@2023-08-01",
            "body": {"properties": {
                "useFreeLimit": free, "freeLimitExhaustionBehavior": behavior,
            }},
        },
    }


def plan(*resources):
    return {"planned_values": {"root_module": {"child_modules": [{"resources": list(resources)}]}}}


def total(lines):
    return sum(line.monthly_usd for line in lines)


def test_free_grant_covers_light_usage():
    lines, unknown = cost.estimate({"dev": plan(app())}, usage(), book())
    assert total(lines) == 0
    assert unknown == []


def test_usage_over_grant_is_billed():
    hours = {"dev": 1000}
    lines, _ = cost.estimate(
        {"dev": plan(app())}, usage(app_active_hours_per_month=hours), book()
    )
    # 3.6M segundos x 0.25 vCPU - 180k gratis = 720k; x 0.5 GiB - 360k gratis = 1.44M.
    assert total(lines) == pytest.approx(720_000 * 0.000024 + 1_440_000 * 0.000003)


def test_grant_is_shared_between_environments():
    hours = {"dev": 150, "prod": 150}
    alone, _ = cost.estimate(
        {"dev": plan(app())}, usage(app_active_hours_per_month=hours), book()
    )
    both, _ = cost.estimate(
        {"dev": plan(app()), "prod": plan(app())},
        usage(app_active_hours_per_month=hours), book(),
    )
    assert total(alone) == 0
    assert total(both) > 0


def test_free_sql_with_autopause_costs_zero():
    lines, _ = cost.estimate({"dev": plan(database())}, usage(), book())
    assert total(lines) == 0


@pytest.mark.parametrize("kwargs", [{"free": False}, {"behavior": "BillOverUsage"}])
def test_sql_that_can_bill_is_not_reported_as_free(kwargs):
    lines, _ = cost.estimate({"dev": plan(database(**kwargs))}, usage(), book())
    assert total(lines) == pytest.approx(10 * 0.5 + 1 * 0.1)


def test_unknown_resource_is_reported():
    vm = {"address": "azurerm_linux_virtual_machine.x", "mode": "managed",
          "type": "azurerm_linux_virtual_machine", "values": {}}
    _, unknown = cost.estimate({"dev": plan(vm)}, usage(), book())
    assert unknown == ["dev: azurerm_linux_virtual_machine.x"]


def test_data_sources_and_helpers_are_ignored():
    data = {"address": "data.x", "mode": "data", "type": "azurerm_client_config", "values": {}}
    helper = {"address": "random_string.s", "mode": "managed", "type": "random_string", "values": {}}
    lines, unknown = cost.estimate({"dev": plan(data, helper)}, usage(), book())
    assert lines == [] and unknown == []


def test_network_failure_falls_back_to_snapshot():
    def broken(_key, _region):
        raise OSError("sin red")

    prices = cost.PriceBook({"eastus": PRICES}, fetcher=broken)
    assert prices.price("kv_10k_operations", "eastus") == 0.03
    assert prices.used_snapshot


def test_missing_price_is_an_error_not_zero():
    with pytest.raises(cost.PriceNotFound):
        cost.PriceBook({}, offline=True).price("kv_10k_operations", "eastus")


def run_cli(tmp_path, resources, *extra):
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan(*resources)))
    snapshot = tmp_path / "prices.json"
    snapshot.write_text(json.dumps({"eastus": PRICES}))
    return cost.main([
        "--plan", f"dev={path}", "--snapshot", str(snapshot), "--offline", *extra,
    ])


def test_budget_gate_fails_when_exceeded(tmp_path):
    assert run_cli(tmp_path, [database(free=False)], "--budget", "1") == 1


def test_budget_gate_passes_within_limit(tmp_path):
    assert run_cli(tmp_path, [database()], "--budget", "1") == 0


def test_unknown_resource_fails_the_gate(tmp_path):
    vm = {"address": "azurerm_linux_virtual_machine.x", "mode": "managed",
          "type": "azurerm_linux_virtual_machine", "values": {}}
    assert run_cli(tmp_path, [vm]) == 1
