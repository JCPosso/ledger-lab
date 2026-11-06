# Funciones comunes. Se carga con `source`.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPLOY_DIR="$ROOT/.deploy"

die() {
  echo "Error: $*" >&2
  exit 1
}

require() {
  local tool
  for tool in "$@"; do
    command -v "$tool" >/dev/null || die "falta '$tool' en el PATH"
  done
}

# Toda la autenticacion sale de `az login`. No hay service principal ni secretos de cliente.
use_azure_cli_identity() {
  require az
  ARM_SUBSCRIPTION_ID="$(az account show --query id -o tsv 2>/dev/null)" \
    || die "ejecuta primero: az login"
  export ARM_SUBSCRIPTION_ID
  echo "Suscripcion: $(az account show --query name -o tsv) ($ARM_SUBSCRIPTION_ID)"
}
