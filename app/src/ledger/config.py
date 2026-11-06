"""Configuracion leida del entorno. En Azure los secretos llegan desde Key Vault."""

import os
from dataclasses import dataclass

MIN_JWT_SECRET_LENGTH = 32


@dataclass(frozen=True)
class Settings:
    database_url: str
    jwt_secret: str
    jwt_minutes: int = 30
    environment: str = "local"


def load_settings() -> Settings:
    database_url = os.environ.get("DATABASE_URL")
    jwt_secret = os.environ.get("JWT_SECRET")
    if not database_url:
        raise RuntimeError("Falta la variable DATABASE_URL")
    if not jwt_secret or len(jwt_secret) < MIN_JWT_SECRET_LENGTH:
        raise RuntimeError(f"JWT_SECRET debe tener al menos {MIN_JWT_SECRET_LENGTH} caracteres")
    return Settings(
        database_url=database_url,
        jwt_secret=jwt_secret,
        jwt_minutes=int(os.environ.get("JWT_MINUTES", "30")),
        environment=os.environ.get("APP_ENV", "local"),
    )
