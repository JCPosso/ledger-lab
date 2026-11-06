from datetime import UTC, datetime, timedelta

import jwt

from conftest import PASSWORD, SECRET
from ledger.security import decode_token, hash_password, verify_password


def test_password_hash_is_salted_and_verifiable():
    first, second = hash_password(PASSWORD), hash_password(PASSWORD)
    assert first != second
    assert verify_password(PASSWORD, first)
    assert not verify_password("otra-contrasena", first)


def test_malformed_hash_is_rejected():
    assert not verify_password(PASSWORD, "no-es-un-hash")


def test_account_requires_token(client):
    assert client.get("/api/account").status_code == 401


def test_tampered_token_is_rejected(client):
    token = jwt.encode({"sub": "x", "exp": datetime.now(UTC) + timedelta(minutes=5)}, "z" * 40)
    response = client.get("/api/account", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_expired_token_is_rejected():
    token = jwt.encode({"sub": "x", "exp": datetime.now(UTC) - timedelta(minutes=1)}, SECRET)
    assert decode_token(token, SECRET) is None


def test_alg_none_token_is_rejected():
    token = jwt.encode(
        {"sub": "x", "exp": datetime.now(UTC) + timedelta(minutes=5)}, "", algorithm="none"
    )
    assert decode_token(token, SECRET) is None


def test_duplicate_email_conflicts_ignoring_case(client, signup):
    signup("ana@example.com")
    body = {"email": "ANA@example.com", "password": PASSWORD}
    assert client.post("/api/auth/register", json=body).status_code == 409


def test_wrong_password_is_rejected(client, signup):
    signup("ana@example.com")
    body = {"email": "ana@example.com", "password": "contrasena-incorrecta"}
    assert client.post("/api/auth/login", json=body).status_code == 401


def test_short_password_is_rejected(client):
    body = {"email": "ana@example.com", "password": "corta"}
    assert client.post("/api/auth/register", json=body).status_code == 422
