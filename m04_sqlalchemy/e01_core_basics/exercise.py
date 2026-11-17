"""Exercise 4.1: SQLAlchemy Core: engines, connections, ``text()``, tables, CRUD.

Core is the SQL layer that the ORM is built on. You use it directly for
migrations, bulk jobs, reporting queries, and anywhere an ORM object per row
would be wasteful. Implement every task below. Run the tests with:

    uv run pytest m04_sqlalchemy/e01_core_basics
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from sqlalchemy import (
    Boolean,
    Column,
    Connection,
    DateTime,
    Engine,
    ForeignKey,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    create_engine,
    delete,
    event,
    func,
    insert,
    select,
    text,
    true,
    update,
)
from sqlalchemy.dialects.sqlite import insert as sqlite_insert


# ---------------------------------------------------------------------------
# Task 1: create an engine
# ---------------------------------------------------------------------------
def create_sqlite_engine(path: Path | None = None, *, echo: bool = False) -> Engine:
    """Create a SQLite engine with foreign-key enforcement switched on.

    * ``path is None``: an in-memory database (URL ``"sqlite://"``).
    * Otherwise: a file database at ``path`` (URL ``f"sqlite:///{path}"``).
    * Pass ``echo`` through to ``create_engine``.
    * SQLite ignores ``FOREIGN KEY`` constraints unless every new DBAPI
      connection runs ``PRAGMA foreign_keys=ON``. Register a listener for the
      engine's ``"connect"`` event that does this, so every pooled connection
      enforces foreign keys.

    >>> engine = create_sqlite_engine()
    >>> with engine.connect() as conn:
    ...     conn.execute(text("PRAGMA foreign_keys")).scalar_one()
    1

    Hint: ``@event.listens_for(engine, "connect")`` receives
    ``(dbapi_connection, connection_record)``; use ``dbapi_connection.cursor()``.
    """
    url = "sqlite://" if path is None else f"sqlite:///{path}"
    engine = create_engine(url, echo=echo)

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection: Any, _record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


# ---------------------------------------------------------------------------
# Task 2: all-or-nothing script
# ---------------------------------------------------------------------------
def execute_in_transaction(engine: Engine, statements: Iterable[str]) -> int:
    """Run raw SQL ``statements`` in ONE transaction and return how many ran.

    * Wrap each string in ``text()`` and execute it in order.
    * If any statement fails, nothing from this call may be kept: the whole
      transaction is rolled back and the original exception propagates.
    * On success the transaction is committed.

    Hint: ``with engine.begin() as conn:`` commits on normal exit and rolls
    back if the block raises. ``engine.connect()`` does neither for you.
    """
    count = 0
    with engine.begin() as conn:
        for sql in statements:
            conn.execute(text(sql))
            count += 1
    return count


# ---------------------------------------------------------------------------
# Task 3: bound parameters
# ---------------------------------------------------------------------------
def find_user_by_email(conn: Connection, email: str) -> dict[str, Any] | None:
    """Return the row of table ``users`` whose ``email`` equals ``email``.

    The table already exists and has the columns ``id``, ``email``, ``name``.

    * Use ``text()`` with a *bound parameter* (``:email``). Never build SQL with
      f-strings or ``%``: the input ``"' OR '1'='1"`` must find nothing, not
      every user.
    * Return the row as a plain ``dict`` (``{"id": 1, "email": ..., "name": ...}``),
      or ``None`` when there is no match.

    Hint: ``conn.execute(stmt, {"email": email}).mappings().first()`` gives a
    ``RowMapping`` (or ``None``); ``dict(row)`` turns it into a dict.
    """
    row = (
        conn.execute(
            text("SELECT id, email, name FROM users WHERE email = :email"),
            {"email": email},
        )
        .mappings()
        .first()
    )
    return dict(row) if row is not None else None


# ---------------------------------------------------------------------------
# Task 4: tables
# ---------------------------------------------------------------------------
metadata = MetaData()
"""All tables of this exercise live in this ``MetaData``."""

# Define two ``Table`` objects on ``metadata`` (``Table(name, metadata, *columns)``):
#
# ``users`` (table name "users"):
#   * id         Integer, primary key
#   * email      String(255), NOT NULL, unique
#   * name       String(100), NOT NULL
#   * is_active  Boolean, NOT NULL, Python-side default True AND server_default true()
#   * created_at DateTime, NOT NULL, server_default func.now()
#
# ``orders`` (table name "orders"):
#   * id       Integer, primary key
#   * user_id  Integer, NOT NULL, ForeignKey("users.id", ondelete="CASCADE"), indexed
#   * amount   Numeric(10, 2), NOT NULL
#   * status   String(20), NOT NULL, default "new"
#
# ``default=`` is applied by SQLAlchemy when YOUR code inserts a row;
# ``server_default=`` becomes part of the DDL, so the database fills it even for
# rows inserted by other tools.

users = Table(
    "users",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("email", String(255), nullable=False, unique=True),
    Column("name", String(100), nullable=False),
    Column("is_active", Boolean, nullable=False, default=True, server_default=true()),
    Column("created_at", DateTime, nullable=False, server_default=func.now()),
)

orders = Table(
    "orders",
    metadata,
    Column("id", Integer, primary_key=True),
    Column(
        "user_id",
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("amount", Numeric(10, 2), nullable=False),
    Column("status", String(20), nullable=False, default="new"),
)


# ---------------------------------------------------------------------------
# Task 5: insert many, get the ids back
# ---------------------------------------------------------------------------
def insert_users(conn: Connection, rows: Iterable[Mapping[str, Any]]) -> list[int]:
    """Insert ``rows`` (dicts with ``email`` and ``name``) into ``users``.

    * Use ONE ``insert(users)`` statement executed with the list of rows.
    * Return the new primary keys in the same order as ``rows``.
    * An empty ``rows`` returns ``[]`` without touching the database.
    * Do not commit: the caller owns the transaction.

    Hint: ``insert(users).returning(users.c.id, sort_by_parameter_order=True)``
    makes SQLAlchemy 2.x return the ids of a multi-row insert in input order.
    Then ``.scalars().all()``.
    """
    params = [dict(row) for row in rows]
    if not params:
        return []
    stmt = insert(users).returning(users.c.id, sort_by_parameter_order=True)
    return list(conn.execute(stmt, params).scalars().all())


# ---------------------------------------------------------------------------
# Task 6: select as mappings
# ---------------------------------------------------------------------------
def list_active_users(conn: Connection, name_prefix: str | None = None) -> list[dict[str, Any]]:
    """Return active users as dicts with keys ``id``, ``email``, ``name``.

    * Only rows with ``is_active`` true.
    * If ``name_prefix`` is given, keep only names that start with it
      (case-sensitive is fine; use ``.startswith()`` or ``.like(prefix + "%")``).
    * Order by ``id``.

    >>> list_active_users(conn, "A")  # doctest: +SKIP
    [{'id': 1, 'email': 'ann@example.com', 'name': 'Ann'}]
    """
    stmt = (
        select(users.c.id, users.c.email, users.c.name)
        .where(users.c.is_active.is_(True))
        .order_by(users.c.id)
    )
    if name_prefix is not None:
        stmt = stmt.where(users.c.name.startswith(name_prefix, autoescape=True))
    return [dict(row) for row in conn.execute(stmt).mappings()]


# ---------------------------------------------------------------------------
# Task 7: update
# ---------------------------------------------------------------------------
def deactivate_user(conn: Connection, user_id: int) -> bool:
    """Set ``is_active = False`` for user ``user_id``.

    Return ``True`` if a row was updated, ``False`` if no user has that id.

    Hint: ``update(users).where(...).values(...)``; the result has ``.rowcount``.
    """
    result = conn.execute(update(users).where(users.c.id == user_id).values(is_active=False))
    return result.rowcount == 1


# ---------------------------------------------------------------------------
# Task 8: delete
# ---------------------------------------------------------------------------
def purge_inactive_users(conn: Connection) -> int:
    """Delete every inactive user and return how many users were deleted.

    Their orders must disappear too. Do not delete them by hand: the
    ``ON DELETE CASCADE`` foreign key from Task 4 (with the PRAGMA from Task 1)
    does it in the database.
    """
    result = conn.execute(delete(users).where(users.c.is_active.is_(False)))
    return result.rowcount


# ---------------------------------------------------------------------------
# Task 9: upsert
# ---------------------------------------------------------------------------
def upsert_user(conn: Connection, email: str, name: str) -> int:
    """Insert a user, or update the name if ``email`` already exists.

    Return the user's id in both cases. Use a single statement (no
    "SELECT first, then INSERT or UPDATE": that races under concurrency).

    Hint: ``sqlalchemy.dialects.sqlite.insert(users).values(...)
    .on_conflict_do_update(index_elements=[users.c.email], set_={...})``.
    ``stmt.excluded.name`` refers to the value you tried to insert. Add
    ``.returning(users.c.id)``. (PostgreSQL has the same API in
    ``sqlalchemy.dialects.postgresql``.)
    """
    stmt = sqlite_insert(users).values(email=email, name=name)
    stmt = stmt.on_conflict_do_update(
        index_elements=[users.c.email],
        set_={"name": stmt.excluded.name},
    ).returning(users.c.id)
    return conn.execute(stmt).scalar_one()
