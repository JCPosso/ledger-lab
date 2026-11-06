"""Reglas de negocio transaccionales. Todo lo que se escribe aqui ocurre en una sola transaccion."""

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ledger.models import Account, LedgerEntry, Transfer, User
from ledger.security import hash_password, verify_password

WELCOME_BONUS_CENTS = 100_000


class EmailAlreadyRegistered(Exception):
    pass


class AccountNotFound(Exception):
    pass


class InsufficientFunds(Exception):
    pass


class SameAccount(Exception):
    pass


class IdempotencyConflict(Exception):
    """La clave ya se uso con otro destino o monto."""


def register_user(session: Session, email: str, password: str) -> User:
    user = User(email=email.lower(), password_hash=hash_password(password))
    session.add(user)
    try:
        session.flush()
    except IntegrityError as error:
        session.rollback()
        raise EmailAlreadyRegistered from error
    session.add(Account(user_id=user.id, balance_cents=WELCOME_BONUS_CENTS))
    session.commit()
    return user


def authenticate(session: Session, email: str, password: str) -> User | None:
    user = session.scalar(select(User).where(User.email == email.lower()))
    if user is None or not verify_password(password, user.password_hash):
        return None
    return user


def get_account(session: Session, user_id: str) -> Account:
    account = session.scalar(select(Account).where(Account.user_id == user_id))
    if account is None:
        raise AccountNotFound
    return account


def _find_existing(session: Session, source_id: str, key: str) -> Transfer | None:
    return session.scalar(
        select(Transfer).where(
            Transfer.source_account_id == source_id, Transfer.idempotency_key == key
        )
    )


def _replay(existing: Transfer, target_id: str, amount_cents: int) -> Transfer:
    if existing.target_account_id != target_id or existing.amount_cents != amount_cents:
        raise IdempotencyConflict
    return existing


def transfer(
    session: Session, source_user_id: str, target_email: str, amount_cents: int, key: str
) -> Transfer:
    """Mueve dinero de forma atomica e idempotente."""
    source = get_account(session, source_user_id)
    target_user = session.scalar(select(User).where(User.email == target_email.lower()))
    if target_user is None:
        raise AccountNotFound
    target = get_account(session, target_user.id)
    source_id, target_id = source.id, target.id
    if source_id == target_id:
        raise SameAccount

    existing = _find_existing(session, source_id, key)
    if existing is not None:
        return _replay(existing, target_id, amount_cents)

    record = Transfer(
        source_account_id=source_id,
        target_account_id=target_id,
        amount_cents=amount_cents,
        idempotency_key=key,
    )
    session.add(record)
    try:
        # El INSERT va primero: si otro reintento gano la carrera, falla sin haber tocado saldos.
        session.flush()
    except IntegrityError as error:
        session.rollback()
        winner = _find_existing(session, source_id, key)
        if winner is None:
            raise AccountNotFound from error
        return _replay(winner, target_id, amount_cents)

    # Actualizar siempre en el mismo orden evita interbloqueos entre A->B y B->A.
    deltas = {source_id: -amount_cents, target_id: amount_cents}
    for account_id in sorted(deltas):
        delta = deltas[account_id]
        statement = update(Account).where(Account.id == account_id)
        if delta < 0:
            # Verificar y descontar en una sola sentencia impide el doble gasto bajo concurrencia.
            statement = statement.where(Account.balance_cents >= -delta)
        result = session.execute(
            statement.values(balance_cents=Account.balance_cents + delta)
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:
            session.rollback()
            raise InsufficientFunds
        session.add(LedgerEntry(transfer_id=record.id, account_id=account_id, delta_cents=delta))
    session.commit()
    return record


def list_entries(session: Session, account_id: str, limit: int = 50) -> list[LedgerEntry]:
    query = (
        select(LedgerEntry)
        .where(LedgerEntry.account_id == account_id)
        .order_by(LedgerEntry.created_at.desc(), LedgerEntry.id)
        .limit(limit)
    )
    return list(session.scalars(query))
