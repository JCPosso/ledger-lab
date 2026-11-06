"""API HTTP de la billetera."""

from collections.abc import Iterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from ledger import services
from ledger.config import Settings, load_settings
from ledger.db import build_engine, init_schema
from ledger.security import create_token, decode_token

STATIC_DIR = Path(__file__).parent / "static"
bearer = HTTPBearer(auto_error=False)


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)


class TransferRequest(BaseModel):
    to_email: EmailStr
    amount_cents: int = Field(gt=0, le=100_000_000)


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings or load_settings()
    engine = build_engine(app_settings.database_url)
    session_factory = sessionmaker(engine, expire_on_commit=False)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        init_schema(engine)
        yield
        engine.dispose()

    app = FastAPI(title="Ledger", lifespan=lifespan)

    def get_session() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    SessionDep = Annotated[Session, Depends(get_session)]

    def current_user(
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    ) -> str:
        user_id = credentials and decode_token(credentials.credentials, app_settings.jwt_secret)
        if not user_id:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token invalido o vencido")
        return user_id

    UserDep = Annotated[str, Depends(current_user)]

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/healthz")
    def healthz() -> dict:
        """Liveness: no toca la base para no impedir su pausa automatica (y su costo cero)."""
        return {"status": "ok", "environment": app_settings.environment}

    @app.get("/readyz")
    def readyz(session: SessionDep) -> dict:
        try:
            session.execute(text("SELECT 1"))
        except SQLAlchemyError as error:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Sin base de datos") from error
        return {"status": "ready"}

    @app.post("/api/auth/register", status_code=status.HTTP_201_CREATED)
    def register(body: Credentials, session: SessionDep) -> dict:
        try:
            user = services.register_user(session, body.email, body.password)
        except services.EmailAlreadyRegistered as error:
            raise HTTPException(status.HTTP_409_CONFLICT, "El correo ya existe") from error
        return {"id": user.id, "email": user.email}

    @app.post("/api/auth/login")
    def login(body: Credentials, session: SessionDep) -> dict:
        user = services.authenticate(session, body.email, body.password)
        if user is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Credenciales invalidas")
        token = create_token(user.id, app_settings.jwt_secret, app_settings.jwt_minutes)
        return {"access_token": token, "token_type": "bearer"}

    @app.get("/api/account")
    def account(user_id: UserDep, session: SessionDep) -> dict:
        try:
            found = services.get_account(session, user_id)
        except services.AccountNotFound as error:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Cuenta no encontrada") from error
        entries = services.list_entries(session, found.id)
        return {
            "id": found.id,
            "balance_cents": found.balance_cents,
            "entries": [
                {
                    "transfer_id": entry.transfer_id,
                    "delta_cents": entry.delta_cents,
                    "created_at": entry.created_at.isoformat() + "Z",
                }
                for entry in entries
            ],
        }

    @app.post("/api/transfers", status_code=status.HTTP_201_CREATED)
    def create_transfer(
        body: TransferRequest,
        user_id: UserDep,
        session: SessionDep,
        idempotency_key: Annotated[str, Header(min_length=8, max_length=64)],
    ) -> dict:
        try:
            record = services.transfer(
                session, user_id, body.to_email, body.amount_cents, idempotency_key
            )
        except services.AccountNotFound as error:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Cuenta no encontrada") from error
        except services.InsufficientFunds as error:
            raise HTTPException(status.HTTP_409_CONFLICT, "Saldo insuficiente") from error
        except services.SameAccount as error:
            raise HTTPException(422, "Misma cuenta") from error
        except services.IdempotencyConflict as error:
            raise HTTPException(status.HTTP_409_CONFLICT, "Clave ya usada") from error
        return {"id": record.id, "amount_cents": record.amount_cents}

    return app
