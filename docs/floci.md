# Ejecutar con floci-az

[floci-az](https://github.com/floci-io/floci-az) es un emulador local de Azure, gratuito y con licencia
MIT. Permite practicar `plan`, `apply` y `destroy` sin cuenta.

> **Estado:** esta ruta sigue la documentación de floci-az, pero aún no se ha ejecutado de principio a
> fin. Solo `terraform validate` está comprobado en `infra/environments/local`. Container Apps, Key
> Vault y los roles podrían necesitar ajustes.

## Qué se puede emular

| Pieza | En floci-az |
|---|---|
| Grupo de recursos, Key Vault, Azure SQL (ARM) | Sí, según su documentación |
| Container Apps | Sí, según su documentación |
| SQL Server real con TDS | Solo si aceptas su licencia con `ACCEPT_SQL_EULA=Y` |
| Oferta gratuita de Azure SQL (`azapi`) | No se usa: `local` fija `use_free_offer = false` |
| Políticas de región de Azure for Students | No representa las de tu suscripción |

## Pasos

Revisa la imagen y sus permisos antes de ejecutarla: el contenedor monta el socket de Docker, lo que
le da control sobre el Docker de tu equipo.

```bash
docker compose --profile floci up -d floci-az
```

El proveedor `azurerm` exige HTTPS, así que debes confiar en el certificado autofirmado:

```bash
curl -sf http://localhost:4577/_floci/tls-cert -o floci-az.crt
```

En macOS, agrégalo al llavero de tu sistema, y quítalo al terminar:

```bash
sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain floci-az.crt
```

Luego aplica el ambiente local:

```bash
terraform -chdir=infra/environments/local init
```

```bash
terraform -chdir=infra/environments/local apply
```

Y, al terminar, limpia:

```bash
terraform -chdir=infra/environments/local destroy
```

```bash
docker compose --profile floci down
```

## Costos sin Azure

Un plan contra floci-az sirve como entrada del estimador, y los precios siguen siendo los reales:

```bash
terraform -chdir=infra/environments/local plan -out=local.tfplan
```

```bash
terraform -chdir=infra/environments/local show -json local.tfplan > local.plan.json
```

```bash
python3 cost/estimate.py --plan local=local.plan.json
```

`local` crea una base sin oferta gratuita, pero `cost/usage.json` le asigna cero horas de consumo.

## Pruebas contra SQL Server

Las pruebas usan SQLite por defecto. SQLite no tiene los mismos bloqueos que SQL Server, así que vale
la pena repetirlas contra un motor real. Necesitas el driver ODBC 18 y la URL que entrega el endpoint
`/connect` de floci-az:

```bash
TEST_DATABASE_URL='mssql+pyodbc://...' uv run --project app --python 3.12 --extra dev --extra mssql pytest app -q
```

**Cuidado:** estas pruebas borran todas las tablas de esa base. Nunca apuntes a `dev` ni a `prod`.
