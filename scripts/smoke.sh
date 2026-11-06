#!/usr/bin/env bash
# Recorre el flujo real de la aplicacion sobre un ambiente desplegado.
# Uso: scripts/smoke.sh <url>
set -euo pipefail
die() { echo "Error: $*" >&2; exit 1; }
BASE="${1:-}"
[[ "$BASE" == https://* || "$BASE" == http://* ]] || die "uso: $0 <url>"
command -v curl >/dev/null && command -v jq >/dev/null || die "se requieren curl y jq"

RUN="$(date +%s)"
PASSWORD="smoke-$RUN-$RANDOM-$RANDOM"
SENDER="smoke-a-$RUN@example.com"
RECEIVER="smoke-b-$RUN@example.com"

request() {
  curl --silent --show-error --fail-with-body --max-time 120 \
    -H 'Content-Type: application/json' "$@"
}

echo "Esperando la app (arranque en frio y reanudacion de la base)..."
for attempt in {1..20}; do
  curl --silent --fail --max-time 60 "$BASE/readyz" >/dev/null && break
  [[ "$attempt" == 20 ]] && die "la app no quedo lista en $BASE"
  sleep 15
done

body() { jq -n --arg email "$1" --arg password "$PASSWORD" '{email: $email, password: $password}'; }
request -X POST "$BASE/api/auth/register" -d "$(body "$SENDER")" >/dev/null
request -X POST "$BASE/api/auth/register" -d "$(body "$RECEIVER")" >/dev/null
TOKEN="$(request -X POST "$BASE/api/auth/login" -d "$(body "$SENDER")" | jq -r .access_token)"
AUTH="Authorization: Bearer $TOKEN"

CODE="$(curl --silent --output /dev/null --write-out '%{http_code}' "$BASE/api/account")"
[[ "$CODE" == 401 ]] || die "la API acepto una solicitud sin token ($CODE)"

BEFORE="$(request -H "$AUTH" "$BASE/api/account" | jq .balance_cents)"
PAYLOAD="$(jq -n --arg to "$RECEIVER" '{to_email: $to, amount_cents: 100}')"
KEY="smoke-$RUN"
FIRST="$(request -X POST -H "$AUTH" -H "Idempotency-Key: $KEY" "$BASE/api/transfers" -d "$PAYLOAD" | jq -r .id)"
SECOND="$(request -X POST -H "$AUTH" -H "Idempotency-Key: $KEY" "$BASE/api/transfers" -d "$PAYLOAD" | jq -r .id)"
[[ "$FIRST" == "$SECOND" ]] || die "el reintento creo otra transferencia"

AFTER="$(request -H "$AUTH" "$BASE/api/account" | jq .balance_cents)"
[[ "$AFTER" == "$((BEFORE - 100))" ]] || die "saldo inesperado: $BEFORE -> $AFTER"

echo "Prueba de humo correcta en $BASE"
