"""Exercise 4.5: the ``Session``: unit of work, identity map, and transactions.

A ``Session`` is not a connection. It is a unit of work that tracks the
objects you load and change, and an identity map that holds at most one
Python object per database row. It writes your changes in a *flush*, and
makes them permanent with a *commit*. Most production ORM bugs come from
misunderstanding one of these. Run the tests with:

    uv run pytest m04_sqlalchemy/e05_sessions_and_transactions
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from sqlalchemy import CheckConstraint, Engine, String, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Task 7 (part of the model): optimistic locking
# ---------------------------------------------------------------------------
class Account(Base):
    """A bank account. Given, except for the ``__mapper_args__`` of Task 7.

    Task 7: make ``version`` a *version counter*: add
    ``__mapper_args__ = {"version_id_col": version}`` to the class body.
    With it, the ORM

    * sets ``version = 1`` on INSERT and increments it on every UPDATE, and
    * adds ``WHERE version = <the version I loaded>`` to every UPDATE and
      DELETE. If another transaction changed the row in the meantime, zero
      rows match and the flush raises ``sqlalchemy.orm.exc.StaleDataError``
      instead of silently overwriting the other change ("lost update").
    """

    __tablename__ = "accounts"
    __table_args__ = (CheckConstraint("balance >= 0", name="ck_accounts_balance"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    owner: Mapped[str] = mapped_column(String(50), unique=True)
    balance: Mapped[int] = mapped_column(default=0)
    version: Mapped[int] = mapped_column(default=1)

    __mapper_args__ = {"version_id_col": version}

    def __repr__(self) -> str:
        return f"Account(id={self.id}, owner={self.owner!r}, balance={self.balance})"


# ---------------------------------------------------------------------------
# Task 1: identity map
# ---------------------------------------------------------------------------
def load_twice(session: Session, account_id: int) -> tuple[Account, Account]:
    """Load account ``account_id`` twice, in two different ways, and return both.

    1. ``session.get(Account, account_id)``
    2. ``session.scalars(select(Account).where(Account.id == account_id)).one()``

    The test checks that both are the *same Python object* (``a is b``): the
    second query does hit the database, but the identity map hands back the
    object it already has for that primary key instead of building a new one.
    Raise ``LookupError`` if the account does not exist.
    """
    first = session.get(Account, account_id)
    if first is None:
        raise LookupError(f"Account {account_id} not found")
    second = session.scalars(select(Account).where(Account.id == account_id)).one()
    return first, second


# ---------------------------------------------------------------------------
# Task 2: flush vs commit
# ---------------------------------------------------------------------------
def create_pending(session: Session, owner: str) -> int:
    """Add a new ``Account(owner=owner)``, FLUSH (do not commit), return its id.

    ``flush()`` sends the INSERT inside the session's still-open transaction,
    so the database assigns the primary key. Nothing is permanent yet: other
    connections cannot see the row, and ``session.rollback()`` makes it
    disappear. Use flush when you need a generated id (for example to build a
    related row) before you decide whether to commit.
    """
    account = Account(owner=owner)
    session.add(account)
    session.flush()
    return account.id


# ---------------------------------------------------------------------------
# Task 3: session.begin() as a transaction boundary
# ---------------------------------------------------------------------------
def transfer(factory: sessionmaker[Session], from_id: int, to_id: int, amount: int) -> None:
    """Move ``amount`` from one account to another, atomically.

    * Use ``with factory.begin() as session:``: it opens a session, begins a
      transaction, commits on normal exit, rolls back if the block raises,
      and closes the session in both cases.
    * Raise ``ValueError`` if ``amount <= 0`` or if the source balance is
      lower than ``amount``; ``LookupError`` if either account is missing.
      In every error case neither balance changes.
    """
    if amount <= 0:
        raise ValueError("amount must be positive")
    with factory.begin() as session:
        source = session.get(Account, from_id)
        target = session.get(Account, to_id)
        if source is None or target is None:
            raise LookupError("account not found")
        if source.balance < amount:
            raise ValueError("insufficient funds")
        source.balance -= amount
        target.balance += amount


# ---------------------------------------------------------------------------
# Task 4: recover from IntegrityError
# ---------------------------------------------------------------------------
def create_account_or_none(session: Session, owner: str, balance: int = 0) -> Account | None:
    """Create and commit an account; return ``None`` if ``owner`` is taken.

    * ``owner`` is ``UNIQUE``: a duplicate makes ``commit()`` raise
      ``IntegrityError``. Catch it, call ``session.rollback()``, return ``None``.
    * After the rollback the session must be usable again: the caller's next
      query must work. Without the rollback every later operation raises
      ``PendingRollbackError``.
    * Let other exceptions propagate.
    """
    account = Account(owner=owner, balance=balance)
    session.add(account)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        return None
    return account


# ---------------------------------------------------------------------------
# Task 5: savepoints
# ---------------------------------------------------------------------------
def open_accounts(session: Session, owners: Iterable[str]) -> list[str]:
    """Create one account per owner, skipping owners that already exist.

    * Insert each account inside its own SAVEPOINT:
      ``with session.begin_nested(): session.add(...)``. Leaving the block
      flushes and releases the savepoint. If it raises ``IntegrityError``,
      only that savepoint is rolled back: the other accounts, and anything
      else the caller had pending in the session, survive.
    * Commit once at the end.
    * Return the owners actually created, in input order.

    >>> open_accounts(session, ["ann", "bob", "ann"])  # doctest: +SKIP
    ['ann', 'bob']
    """
    created: list[str] = []
    for owner in owners:
        try:
            with session.begin_nested():
                session.add(Account(owner=owner))
        except IntegrityError:
            continue
        created.append(owner)
    session.commit()
    return created


# ---------------------------------------------------------------------------
# Task 6: repository pattern
# ---------------------------------------------------------------------------
class AccountRepository:
    """Data access for ``Account``, so service code never builds queries itself.

    The repository NEVER commits: the caller (a service, or a FastAPI
    dependency that owns ``session.begin()``) decides when the unit of work
    ends. ``add`` and ``delete`` flush, so ids and constraint errors appear
    right away.

    * ``add(account) -> Account``: add, flush, return the same object.
    * ``get(account_id) -> Account | None``
    * ``get_by_owner(owner) -> Account | None``
    * ``list(*, limit=100, offset=0) -> Sequence[Account]``: ordered by owner.
    * ``delete(account_id) -> bool``: ``True`` if it existed and was deleted.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, account: Account) -> Account:
        self.session.add(account)
        self.session.flush()
        return account

    def get(self, account_id: int) -> Account | None:
        return self.session.get(Account, account_id)

    def get_by_owner(self, owner: str) -> Account | None:
        return self.session.scalars(select(Account).where(Account.owner == owner)).one_or_none()

    def list(self, *, limit: int = 100, offset: int = 0) -> Sequence[Account]:
        stmt = select(Account).order_by(Account.owner).limit(limit).offset(offset)
        return self.session.scalars(stmt).all()

    def delete(self, account_id: int) -> bool:
        account = self.session.get(Account, account_id)
        if account is None:
            return False
        self.session.delete(account)
        self.session.flush()
        return True


# ---------------------------------------------------------------------------
# Task 8: expire_on_commit
# ---------------------------------------------------------------------------
def make_api_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Return a ``sessionmaker`` bound to ``engine`` with ``expire_on_commit=False``.

    By default ``commit()`` expires every loaded object, so the next attribute
    access reloads it from the database. Once the session is closed there is
    nothing to reload from, and the access raises ``DetachedInstanceError``.
    Web handlers often commit, close, and only then serialise the objects to
    JSON, so they turn expiry off. (With ``AsyncSession`` this setting is
    practically mandatory: see the next exercise.)
    """
    return sessionmaker(bind=engine, expire_on_commit=False)


def open_account_for_response(factory: sessionmaker[Session], owner: str, balance: int) -> Account:
    """Create and commit an account in a NEW session from ``factory``, close the
    session, and return the account.

    The caller reads ``id``, ``owner``, and ``balance`` after the session has
    closed, so this only works when ``factory`` has ``expire_on_commit=False``.
    Do not call ``refresh()`` or ``expunge()`` to work around it.

    Hint: ``with factory() as session: ...`` closes the session on exit.
    """
    with factory() as session:
        account = Account(owner=owner, balance=balance)
        session.add(account)
        session.commit()
    return account
