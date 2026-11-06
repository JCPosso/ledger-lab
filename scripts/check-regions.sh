#!/usr/bin/env bash
# Muestra las regiones que permite la politica de la suscripcion de Azure for Students.
source "$(dirname "$0")/lib.sh"
use_azure_cli_identity
require jq

echo
echo "Asignaciones de politica que limitan regiones:"
az policy assignment list --disable-scope-strict-match -o json | jq -r '
  .[]
  | select(((.displayName // "") + " " + (.name // "")) | test("region|location"; "i"))
  | "- \(.displayName // .name)",
    ((.parameters // {}) | to_entries[]
      | select(.value.value | type == "array")
      | "    \(.value.value | join(", "))")
'
echo
echo "Azure SQL en regiones comunes (restringido por suscripcion, no por politica):"
for region in eastus eastus2 centralus southcentralus northcentralus westus westus2 westus3 \
  canadacentral brazilsouth mexicocentral westeurope northeurope; do
  status="$(az rest --method get \
    --url "/subscriptions/$ARM_SUBSCRIPTION_ID/providers/Microsoft.Sql/locations/$region/capabilities?api-version=2023-08-01" \
    --query status -o tsv 2>/dev/null || echo desconocido)"
  case "$status" in
    Available | Default) echo "  $region: disponible" ;;
    *) echo "  $region: restringida ($status)" ;;
  esac
done

echo
echo "Si no aparece una lista, prueba una region en el portal al crear un grupo de recursos."
echo "Container Apps y Azure SQL tambien deben estar disponibles en la region elegida."
