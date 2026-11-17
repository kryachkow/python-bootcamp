import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.orm.exc import DetachedInstanceError, StaleDataError

from m04_sqlalchemy.e05_sessions_and_transactions.exercise import (
    Account,
    AccountRepository,
    Base,
    create_account_or_none,
    create_pending,
    load_twice,
    make_api_session_factory,
    open_account_for_response,
    open_accounts,
    transfer,
)


@pytest.fixture
def engine(tmp_path):
    """A file database, so separate sessions really use separate connections."""
    eng = create_engine(f"sqlite:///{tmp_path / 'bank.db'}")
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        s.add_all([Account(owner="ann", balance=100), Account(owner="bob", balance=50)])
        s.commit()
    yield eng
    eng.dispose()


@pytest.fixture
def factory(engine):
    return sessionmaker(bind=engine)


@pytest.fixture
def session(factory):
    with factory() as s:
        yield s


@pytest.fixture
def sql(engine):
    statements: list[str] = []
    event.listen(engine, "before_cursor_execute", lambda c, cur, stmt, *a: statements.append(stmt))
    return statements


def balances(engine) -> dict[str, int]:
    with Session(engine) as s:
        return dict(s.execute(select(Account.owner, Account.balance)).all())


def owners(engine) -> list[str]:
    with Session(engine) as s:
        return list(s.scalars(select(Account.owner).order_by(Account.owner)))


class TestTask1IdentityMap:
    def test_same_object(self, session):
        a, b = load_twice(session, 1)
        assert a is b
        assert a.owner == "ann"

    def test_change_visible_through_both(self, session):
        a, b = load_twice(session, 2)
        a.balance = 999
        assert b.balance == 999

    def test_get_after_load_needs_no_sql(self, session, sql):
        a, _ = load_twice(session, 1)
        sql.clear()
        assert session.get(Account, 1) is a
        assert sql == []

    def test_missing(self, session):
        with pytest.raises(LookupError):
            load_twice(session, 999)


class TestTask2FlushVsCommit:
    def test_id_assigned_by_flush(self, session):
        account_id = create_pending(session, "cy")
        assert isinstance(account_id, int)
        assert session.get(Account, account_id).owner == "cy"
        assert not session.new, "after a flush the object is no longer pending"

    def test_not_committed(self, engine, session):
        create_pending(session, "cy")
        assert session.in_transaction()
        assert "cy" not in owners(engine)

    def test_rollback_discards(self, engine, session):
        account_id = create_pending(session, "cy")
        session.rollback()
        assert session.get(Account, account_id) is None
        assert owners(engine) == ["ann", "bob"]


class TestTask3Transfer:
    def test_moves_money(self, engine, factory):
        transfer(factory, 1, 2, 30)
        assert balances(engine) == {"ann": 70, "bob": 80}

    def test_insufficient_funds_changes_nothing(self, engine, factory):
        with pytest.raises(ValueError):
            transfer(factory, 2, 1, 51)
        assert balances(engine) == {"ann": 100, "bob": 50}

    def test_missing_account_changes_nothing(self, engine, factory):
        with pytest.raises(LookupError):
            transfer(factory, 1, 999, 10)
        assert balances(engine) == {"ann": 100, "bob": 50}

    @pytest.mark.parametrize("amount", [0, -5])
    def test_non_positive_amount(self, engine, factory, amount):
        with pytest.raises(ValueError):
            transfer(factory, 1, 2, amount)
        assert balances(engine) == {"ann": 100, "bob": 50}

    def test_exact_balance_allowed(self, engine, factory):
        transfer(factory, 2, 1, 50)
        assert balances(engine) == {"ann": 150, "bob": 0}


class TestTask4CreateAccountOrNone:
    def test_creates(self, engine, session):
        account = create_account_or_none(session, "cy", 10)
        assert account.id == 3
        assert balances(engine)["cy"] == 10

    def test_duplicate_returns_none_and_session_usable(self, session):
        assert create_account_or_none(session, "ann") is None
        assert session.scalar(select(func.count()).select_from(Account)) == 2
        assert create_account_or_none(session, "cy") is not None

    def test_check_violation_also_returns_none(self, engine, session):
        assert create_account_or_none(session, "cy", balance=-1) is None
        assert session.get(Account, 1).owner == "ann"
        assert owners(engine) == ["ann", "bob"]


class TestTask5Savepoints:
    def test_skips_duplicates(self, engine, session):
        assert open_accounts(session, ["cy", "bob", "dee", "cy"]) == ["cy", "dee"]
        assert owners(engine) == ["ann", "bob", "cy", "dee"]

    def test_outer_pending_work_survives(self, engine, session):
        session.get(Account, 1).balance = 1
        session.add(Account(owner="zed"))
        open_accounts(session, ["ann", "cy"])
        assert owners(engine) == ["ann", "bob", "cy", "zed"]
        assert balances(engine)["ann"] == 1

    def test_uses_savepoints(self, session, sql):
        open_accounts(session, ["cy", "ann"])
        assert any(s.upper().startswith("SAVEPOINT") for s in sql)
        assert any("ROLLBACK TO SAVEPOINT" in s.upper() for s in sql)

    def test_empty(self, session):
        assert open_accounts(session, []) == []


class TestTask6Repository:
    def test_add_and_get(self, session):
        repo = AccountRepository(session)
        account = repo.add(Account(owner="cy", balance=5))
        assert account.id is not None
        assert repo.get(account.id) is account
        assert repo.get(999) is None

    def test_get_by_owner(self, session):
        repo = AccountRepository(session)
        assert repo.get_by_owner("bob").balance == 50
        assert repo.get_by_owner("nobody") is None

    def test_list_ordered_and_paginated(self, session):
        repo = AccountRepository(session)
        repo.add(Account(owner="aaron"))
        assert [a.owner for a in repo.list()] == ["aaron", "ann", "bob"]
        assert [a.owner for a in repo.list(limit=1, offset=1)] == ["ann"]

    def test_delete(self, session):
        repo = AccountRepository(session)
        assert repo.delete(1) is True
        assert repo.delete(1) is False
        assert [a.owner for a in repo.list()] == ["bob"]

    def test_never_commits(self, engine, session):
        repo = AccountRepository(session)
        repo.add(Account(owner="cy"))
        repo.delete(2)
        session.rollback()
        assert owners(engine) == ["ann", "bob"]


class TestTask7OptimisticLocking:
    def test_version_increments(self, session):
        account = session.get(Account, 1)
        assert account.version == 1
        account.balance += 1
        session.commit()
        assert account.version == 2

    def test_concurrent_update_raises_stale_data(self, engine, factory):
        with factory() as s1, factory() as s2:
            a1, a2 = s1.get(Account, 1), s2.get(Account, 1)
            a1.balance = 10
            s1.commit()
            a2.balance = 20
            with pytest.raises(StaleDataError):
                s2.commit()
        assert balances(engine)["ann"] == 10, "the first writer's change must survive"

    def test_update_sql_checks_version(self, session, sql):
        session.get(Account, 2).balance = 0
        session.commit()
        (update_sql,) = [s for s in sql if s.upper().startswith("UPDATE")]
        assert "version" in update_sql.split("WHERE", 1)[1]


class TestTask8ExpireOnCommit:
    def test_factory(self, engine):
        factory = make_api_session_factory(engine)
        assert factory.kw["expire_on_commit"] is False
        with factory() as s:
            assert s.get_bind() is engine

    def test_object_usable_after_close(self, engine):
        account = open_account_for_response(make_api_session_factory(engine), "cy", 7)
        assert (account.id, account.owner, account.balance) == (3, "cy", 7)
        assert balances(engine)["cy"] == 7

    def test_default_factory_would_fail(self, engine):
        """The same function with a default factory shows why Task 8 exists."""
        account = open_account_for_response(sessionmaker(bind=engine), "cy", 7)
        with pytest.raises(DetachedInstanceError):
            _ = account.balance
