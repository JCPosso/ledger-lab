import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from ledger.config import Settings
from ledger.main import create_app
from ledger.models import Base

SECRET = "clave-de-pruebas-con-mas-de-32-caracteres"
PASSWORD = "contrasena-segura"


@pytest.fixture
def database_url(tmp_path) -> str:
    return os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{tmp_path / 'ledger.db'}"


@pytest.fixture
def client(database_url):
    # Con TEST_DATABASE_URL la base persiste entre pruebas; cada una debe partir de cero.
    engine = create_engine(database_url)
    Base.metadata.drop_all(engine)
    engine.dispose()
    settings = Settings(database_url=database_url, jwt_secret=SECRET)
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.fixture
def signup(client):
    """Registra un usuario y devuelve los encabezados con su token."""

    def _signup(email: str) -> dict:
        body = {"email": email, "password": PASSWORD}
        assert client.post("/api/auth/register", json=body).status_code == 201
        token = client.post("/api/auth/login", json=body).json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    return _signup
