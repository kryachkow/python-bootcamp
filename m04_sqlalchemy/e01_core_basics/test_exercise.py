from decimal import Decimal

import pytest
from sqlalchemy import (
    Boolean,
    DateTime,
    Integer,
    Numeric,
    String,
    create_engine,
    event,
    inspect,
    insert,
    select,
    text,
)
from sqlalchemy.exc import IntegrityError, OperationalError

from m04_sqlalchemy.e01_core_basics import exercise as ex
from m04_sqlalchemy.e01_core_basics.exercise import (
    create_sqlite_engine,
    deactivate_user,
    execute_in_transaction,
    find_user_by_email,
    insert_users,
    list_active_users,
    purge_inactive_users,
    upsert_user,
)


@pytest.fixture
def raw_engine():
    """A fresh in-memory engine with FKs on, independent of Task 1."""
    engine = create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _record):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    yield engine
    engine.dispose()


@pytest.fixture
def conn(raw_engine):
    """A connection inside a transaction, rolled back after the test."""
    with raw_engine.connect() as connection:
        with connection.begin():
            yield connection


def create_tables(conn):
    """Create the Task 4 tables (called inside tests, not at import time)."""
    ex.metadata.create_all(conn)
    assert ex.users is not None and ex.orders is not None, "define the Task 4 tables"


def seed_users(conn):
    create_tables(conn)
    conn.execute(
        insert(ex.users),
        [
            {"email": "ann@example.com", "name": "Ann", "is_active": True},
            {"email": "bob@example.com", "name": "Bob", "is_active": True},
            {"email": "al@example.com", "name": "Al", "is_active": False},
            {"email": "amy@example.com", "name": "Amy", "is_active": True},
        ],
    )


class TestTask1CreateSqliteEngine:
    def test_in_memory_engine(self):
        engine = create_sqlite_engine()
        assert engine.dialect.name == "sqlite"
        assert engine.url.database in (None, "", ":memory:")
        with engine.connect() as c:
            assert c.execute(text("SELECT 1 + 1")).scalar_one() == 2

    def test_foreign_keys_pragma_on(self):
        engine = create_sqlite_engine()
        with engine.connect() as c:
            assert c.execute(text("PRAGMA foreign_keys")).scalar_one() == 1

    def test_file_database(self, tmp_path):
        db = tmp_path / "app.db"
        engine = create_sqlite_engine(db)
        with engine.begin() as c:
            c.execute(text("CREATE TABLE t (x INTEGER)"))
            assert c.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
        engine.dispose()
        assert db.exists()

    def test_echo_passed_through(self):
        assert create_sqlite_engine(echo=True).echo is True


class TestTask2ExecuteInTransaction:
    def test_commits_all_statements(self, raw_engine):
        n = execute_in_transaction(
            raw_engine,
            ["CREATE TABLE t (x INTEGER)", "INSERT INTO t VALUES (1)", "INSERT INTO t VALUES (2)"],
        )
        assert n == 3
        with raw_engine.connect() as c:
            assert c.execute(text("SELECT count(*) FROM t")).scalar_one() == 2

    def test_rolls_back_everything_on_error(self, raw_engine):
        with raw_engine.begin() as c:
            c.execute(text("CREATE TABLE t (x INTEGER UNIQUE)"))
        with pytest.raises(IntegrityError):
            execute_in_transaction(
                raw_engine,
                ["INSERT INTO t VALUES (1)", "INSERT INTO t VALUES (2)", "INSERT INTO t VALUES (1)"],
            )
        with raw_engine.connect() as c:
            assert c.execute(text("SELECT count(*) FROM t")).scalar_one() == 0

    def test_syntax_error_propagates(self, raw_engine):
        with pytest.raises(OperationalError):
            execute_in_transaction(raw_engine, ["SELEKT 1"])

    def test_empty_script(self, raw_engine):
        assert execute_in_transaction(raw_engine, []) == 0


class TestTask3FindUserByEmail:
    @pytest.fixture
    def users_conn(self, conn):
        conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT, name TEXT)"))
        conn.execute(
            text("INSERT INTO users (email, name) VALUES (:e, :n)"),
            [{"e": "ann@example.com", "n": "Ann"}, {"e": "bob@example.com", "n": "Bob"}],
        )
        return conn

    def test_found_as_plain_dict(self, users_conn):
        row = find_user_by_email(users_conn, "bob@example.com")
        assert row == {"id": 2, "email": "bob@example.com", "name": "Bob"}
        assert type(row) is dict

    def test_not_found(self, users_conn):
        assert find_user_by_email(users_conn, "nobody@example.com") is None

    @pytest.mark.parametrize(
        "evil", ["' OR '1'='1", "x' OR 1=1 --", "'; DROP TABLE users; --"]
    )
    def test_sql_injection_is_harmless(self, users_conn, evil):
        assert find_user_by_email(users_conn, evil) is None
        assert users_conn.execute(text("SELECT count(*) FROM users")).scalar_one() == 2

    def test_quotes_in_value_work(self, users_conn):
        users_conn.execute(text("INSERT INTO users (email, name) VALUES ('o''neil@x.io', 'O''Neil')"))
        assert find_user_by_email(users_conn, "o'neil@x.io")["name"] == "O'Neil"


class TestTask4Tables:
    def test_tables_registered_on_metadata(self):
        assert set(ex.metadata.tables) == {"users", "orders"}

    def test_user_columns(self, conn):
        create_tables(conn)
        cols = {c["name"]: c for c in inspect(conn).get_columns("users")}
        assert set(cols) == {"id", "email", "name", "is_active", "created_at"}
        assert isinstance(ex.users.c.email.type, String) and ex.users.c.email.type.length == 255
        assert isinstance(ex.users.c.is_active.type, Boolean)
        assert isinstance(ex.users.c.created_at.type, DateTime)
        assert not any(cols[n]["nullable"] for n in ("email", "name", "is_active", "created_at"))
        assert cols["is_active"]["default"] is not None, "is_active needs a server_default"
        assert cols["created_at"]["default"] is not None, "created_at needs a server_default"

    def test_order_columns_and_fk(self, conn):
        create_tables(conn)
        assert isinstance(ex.orders.c.amount.type, Numeric)
        assert isinstance(ex.orders.c.user_id.type, Integer)
        (fk,) = inspect(conn).get_foreign_keys("orders")
        assert fk["referred_table"] == "users"
        assert fk["options"].get("ondelete") == "CASCADE"
        assert any(ix["column_names"] == ["user_id"] for ix in inspect(conn).get_indexes("orders"))

    def test_email_unique(self, conn):
        create_tables(conn)
        conn.execute(insert(ex.users).values(email="a@x.io", name="A"))
        with pytest.raises(IntegrityError):
            conn.execute(insert(ex.users).values(email="a@x.io", name="B"))

    def test_server_defaults_fill_raw_inserts(self, conn):
        create_tables(conn)
        conn.execute(text("INSERT INTO users (email, name) VALUES ('raw@x.io', 'Raw')"))
        row = conn.execute(text("SELECT is_active, created_at FROM users")).one()
        assert row.is_active == 1 and row.created_at is not None


class TestTask5InsertUsers:
    def test_returns_ids_in_input_order(self, conn):
        create_tables(conn)
        ids = insert_users(
            conn, [{"email": f"u{i}@x.io", "name": f"U{i}"} for i in range(5)]
        )
        assert ids == [1, 2, 3, 4, 5]
        emails = conn.execute(select(ex.users.c.email).order_by(ex.users.c.id)).scalars().all()
        assert emails == [f"u{i}@x.io" for i in range(5)]

    def test_defaults_applied(self, conn):
        create_tables(conn)
        insert_users(conn, [{"email": "a@x.io", "name": "A"}])
        row = conn.execute(select(ex.users)).mappings().one()
        assert row["is_active"] is True and row["created_at"] is not None

    def test_empty(self, conn):
        create_tables(conn)
        assert insert_users(conn, []) == []

    def test_does_not_commit(self, raw_engine):
        with raw_engine.begin() as c:
            create_tables(c)
        with raw_engine.connect() as c:
            insert_users(c, [{"email": "a@x.io", "name": "A"}])
            c.rollback()
            assert c.execute(select(ex.users.c.id)).first() is None


class TestTask6ListActiveUsers:
    def test_only_active_ordered_by_id(self, conn):
        seed_users(conn)
        rows = list_active_users(conn)
        assert [r["name"] for r in rows] == ["Ann", "Bob", "Amy"]
        assert rows[0] == {"id": 1, "email": "ann@example.com", "name": "Ann"}
        assert all(type(r) is dict for r in rows)

    def test_name_prefix(self, conn):
        seed_users(conn)
        assert [r["name"] for r in list_active_users(conn, "A")] == ["Ann", "Amy"]

    def test_prefix_no_match(self, conn):
        seed_users(conn)
        assert list_active_users(conn, "Zed") == []


class TestTask7DeactivateUser:
    def test_deactivates(self, conn):
        seed_users(conn)
        assert deactivate_user(conn, 2) is True
        active = conn.execute(select(ex.users.c.is_active).where(ex.users.c.id == 2)).scalar_one()
        assert active is False

    def test_other_rows_untouched(self, conn):
        seed_users(conn)
        deactivate_user(conn, 2)
        rows = conn.execute(
            select(ex.users.c.id).where(ex.users.c.is_active).order_by(ex.users.c.id)
        ).scalars().all()
        assert rows == [1, 4]

    def test_missing_user(self, conn):
        seed_users(conn)
        assert deactivate_user(conn, 999) is False


class TestTask8PurgeInactiveUsers:
    def test_deletes_inactive_only(self, conn):
        seed_users(conn)
        assert purge_inactive_users(conn) == 1
        names = conn.execute(select(ex.users.c.name).order_by(ex.users.c.id)).scalars().all()
        assert names == ["Ann", "Bob", "Amy"]

    def test_cascades_to_orders(self, conn):
        seed_users(conn)
        conn.execute(
            insert(ex.orders),
            [
                {"user_id": 3, "amount": Decimal("9.99")},
                {"user_id": 3, "amount": Decimal("1.00")},
                {"user_id": 1, "amount": Decimal("5.00")},
            ],
        )
        purge_inactive_users(conn)
        remaining = conn.execute(select(ex.orders.c.user_id)).scalars().all()
        assert remaining == [1]

    def test_nothing_to_delete(self, conn):
        create_tables(conn)
        assert purge_inactive_users(conn) == 0


class TestTask9UpsertUser:
    def test_inserts_new(self, conn):
        create_tables(conn)
        assert upsert_user(conn, "new@x.io", "New") == 1
        assert conn.execute(select(ex.users.c.name)).scalar_one() == "New"

    def test_updates_existing_and_keeps_id(self, conn):
        seed_users(conn)
        assert upsert_user(conn, "bob@example.com", "Robert") == 2
        name = conn.execute(select(ex.users.c.name).where(ex.users.c.id == 2)).scalar_one()
        assert name == "Robert"
        assert conn.execute(select(ex.users.c.id).order_by(ex.users.c.id)).scalars().all() == [1, 2, 3, 4]

    def test_single_statement(self, raw_engine):
        with raw_engine.begin() as c:
            create_tables(c)
        statements = []

        @event.listens_for(raw_engine, "before_cursor_execute")
        def _count(conn, cursor, statement, *args):
            statements.append(statement)

        with raw_engine.begin() as c:
            upsert_user(c, "a@x.io", "A")
            upsert_user(c, "a@x.io", "B")
        assert len(statements) == 2
        assert all("ON CONFLICT" in s.upper() for s in statements)
