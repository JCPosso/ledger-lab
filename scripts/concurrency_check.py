"""Prueba de concurrencia contra el ambiente desplegado (Azure SQL real)."""
import collections
import json
import secrets
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

BASE = sys.argv[1].rstrip("/")
BONUS = 100_000


def call(method, path, body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        BASE + path, data=data, method=method,
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode()[:200]


run = secrets.token_hex(4)
password = secrets.token_urlsafe(18)
sender, receiver = f"conc-a-{run}@example.com", f"conc-b-{run}@example.com"
for email in (sender, receiver):
    assert call("POST", "/api/auth/register", {"email": email, "password": password})[0] == 201
token = call("POST", "/api/auth/login", {"email": sender, "password": password})[1]["access_token"]
auth = {"Authorization": f"Bearer {token}"}


def pay(amount, key):
    return call("POST", "/api/transfers", {"to_email": receiver, "amount_cents": amount},
                {**auth, "Idempotency-Key": key})


# Misma clave en paralelo: solo un cobro.
with ThreadPoolExecutor(8) as pool:
    same = list(pool.map(lambda _: pay(1_000, f"misma-{run}"), range(8)))
codes = collections.Counter(code for code, _ in same)
ids = {body["id"] for code, body in same if code == 201}
balance = call("GET", "/api/account", headers=auth)[1]["balance_cents"]
print("misma clave:", dict(codes), "ids_distintos:", len(ids), "saldo:", balance)
same_ok = codes == {201: 8} and len(ids) == 1 and balance == BONUS - 1_000
if not same_ok:
    print("  respuestas:", [body for code, body in same if code != 201][:3])

# Claves distintas: el saldo restante alcanza exactamente para 9 de 20 pagos.
start = time.time()
with ThreadPoolExecutor(10) as pool:
    results = list(pool.map(lambda i: pay(11_000, f"pago-{run}-{i:02}"), range(20)))
codes = collections.Counter(code for code, _ in results)
account = call("GET", "/api/account", headers=auth)[1]
print(f"saldo limite ({time.time() - start:.1f}s):", dict(codes), "saldo:", account["balance_cents"])
others = [body for code, body in results if code not in (201, 409)]
if others:
    print("  otras respuestas:", others[:3])
limit_ok = codes == {201: 9, 409: 11} and account["balance_cents"] == 0
print("RESULTADO:", "OK" if same_ok and limit_ok else "FALLA")
sys.exit(0 if same_ok and limit_ok else 1)
