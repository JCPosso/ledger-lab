from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine, func, select

from ledger.models import Account, LedgerEntry
from ledger.services import WELCOME_BONUS_CENTS


def send(client, headers, to, amount, key):
    return client.post(
        "/api/transfers",
        json={"to_email": to, "amount_cents": amount},
        headers={**headers, "Idempotency-Key": key},
    )


def balance(client, headers) -> int:
    return client.get("/api/account", headers=headers).json()["balance_cents"]


def test_transfer_moves_money_and_writes_both_entries(client, signup):
    ana, luis = signup("ana@example.com"), signup("luis@example.com")
    assert send(client, ana, "luis@example.com", 2_500, "clave-0001").status_code == 201
    assert balance(client, ana) == WELCOME_BONUS_CENTS - 2_500
    assert balance(client, luis) == WELCOME_BONUS_CENTS + 2_500
    deltas = [e["delta_cents"] for e in client.get("/api/account", headers=ana).json()["entries"]]
    assert deltas == [-2_500]


def test_insufficient_funds_leaves_no_trace(client, signup, database_url):
    ana, luis = signup("ana@example.com"), signup("luis@example.com")
    response = send(client, ana, "luis@example.com", WELCOME_BONUS_CENTS + 1, "clave-0001")
    assert response.status_code == 409
    assert balance(client, ana) == WELCOME_BONUS_CENTS
    assert balance(client, luis) == WELCOME_BONUS_CENTS
    with create_engine(database_url).connect() as connection:
        assert connection.scalar(select(func.count()).select_from(LedgerEntry)) == 0


def test_failed_key_can_be_retried_after_funding(client, signup):
    ana, luis = signup("ana@example.com"), signup("luis@example.com")
    too_much = WELCOME_BONUS_CENTS + 1
    assert send(client, ana, "luis@example.com", too_much, "clave-0001").status_code == 409
    assert send(client, luis, "ana@example.com", 1, "clave-0002").status_code == 201
    assert send(client, ana, "luis@example.com", too_much, "clave-0001").status_code == 201


def test_retry_with_same_key_does_not_charge_twice(client, signup):
    ana = signup("ana@example.com")
    signup("luis@example.com")
    first = send(client, ana, "luis@example.com", 1_000, "clave-0001")
    second = send(client, ana, "luis@example.com", 1_000, "clave-0001")
    assert first.json()["id"] == second.json()["id"]
    assert balance(client, ana) == WELCOME_BONUS_CENTS - 1_000


def test_reusing_key_with_other_amount_conflicts(client, signup):
    ana = signup("ana@example.com")
    signup("luis@example.com")
    send(client, ana, "luis@example.com", 1_000, "clave-0001")
    assert send(client, ana, "luis@example.com", 2_000, "clave-0001").status_code == 409


def test_transfer_to_self_is_rejected(client, signup):
    ana = signup("ana@example.com")
    assert send(client, ana, "ana@example.com", 1_000, "clave-0001").status_code == 422


def test_unknown_target_returns_404(client, signup):
    ana = signup("ana@example.com")
    assert send(client, ana, "nadie@example.com", 1_000, "clave-0001").status_code == 404


@pytest.mark.parametrize("amount", [0, -5])
def test_non_positive_amount_is_rejected(client, signup, amount):
    ana = signup("ana@example.com")
    signup("luis@example.com")
    assert send(client, ana, "luis@example.com", amount, "clave-0001").status_code == 422


def test_concurrent_transfers_cannot_overdraw(client, signup, database_url):
    """Veinte pagos de 10% en paralelo: solo diez caben en el saldo."""
    ana = signup("ana@example.com")
    signup("luis@example.com")
    amount = WELCOME_BONUS_CENTS // 10

    def pay(index: int) -> int:
        return send(client, ana, "luis@example.com", amount, f"clave-{index:04}").status_code

    with ThreadPoolExecutor(max_workers=8) as pool:
        codes = list(pool.map(pay, range(20)))

    assert codes.count(201) == 10
    assert codes.count(409) == 10
    assert balance(client, ana) == 0
    with create_engine(database_url).connect() as connection:
        assert connection.scalar(select(func.sum(LedgerEntry.delta_cents))) == 0
        total = connection.scalar(select(func.sum(Account.balance_cents)))
    assert total == 2 * WELCOME_BONUS_CENTS


def test_concurrent_retries_of_same_key_charge_once(client, signup):
    ana = signup("ana@example.com")
    signup("luis@example.com")

    def pay(_index: int):
        return send(client, ana, "luis@example.com", 1_000, "clave-unica")

    with ThreadPoolExecutor(max_workers=8) as pool:
        responses = list(pool.map(pay, range(8)))

    assert {r.status_code for r in responses} == {201}
    assert len({r.json()["id"] for r in responses}) == 1
    assert balance(client, ana) == WELCOME_BONUS_CENTS - 1_000


def test_health_endpoints(client):
    assert client.get("/healthz").json()["status"] == "ok"
    assert client.get("/readyz").json()["status"] == "ready"
