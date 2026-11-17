import itertools
from datetime import datetime
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import JSON, DateTime, Enum, String, create_engine, event, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column

from m04_sqlalchemy.e02_orm_mapping import exercise as ex
from m04_sqlalchemy.e02_orm_mapping.exercise import (
    Base,
    ProductStatus,
    add_product,
    create_user,
    get_user_or_raise,
    init_db,
    set_product_attribute,
)

_probe_ids = itertools.count()


def probe_name() -> str:
    """Unique class/table names for throwaway models defined inside tests."""
    return f"probe_{next(_probe_ids)}"


@pytest.fixture
def engine():
    eng = create_engine("sqlite://")
    yield eng
    eng.dispose()


@pytest.fixture
def session(engine):
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def make_product(session, sku="SKU-1", price="9.99", **kw):
    product = ex.Product(sku=sku, name=kw.pop("name", "Widget"), price=Decimal(price), **kw)
    session.add(product)
    session.commit()
    return product


class TestTask1TypeAnnotationMap:
    def test_json_and_tz_datetime(self):
        name = probe_name()
        Probe = type(
            name,
            (Base,),
            {
                "__tablename__": name,
                "__annotations__": {
                    "id": Mapped[int],
                    "payload": Mapped[dict[str, Any]],
                    "seen_at": Mapped[datetime | None],
                },
                "id": mapped_column(primary_key=True),
            },
        )
        cols = Probe.__table__.c
        assert isinstance(cols.payload.type, JSON)
        assert isinstance(cols.seen_at.type, DateTime) and cols.seen_at.type.timezone is True
        assert cols.seen_at.nullable is True and cols.payload.nullable is False

    def test_enum_stores_values(self, engine):
        name = probe_name()
        Probe = type(
            name,
            (Base,),
            {
                "__tablename__": name,
                "__annotations__": {"id": Mapped[int], "status": Mapped[ProductStatus]},
                "id": mapped_column(primary_key=True),
            },
        )
        col_type = Probe.__table__.c.status.type
        assert isinstance(col_type, Enum)
        assert col_type.enums == ["draft", "active", "archived"]
        assert col_type.native_enum is False and col_type.length == 20
        Base.metadata.create_all(engine)
        with Session(engine) as s:
            s.add(Probe(status=ProductStatus.ACTIVE))
            s.commit()
            assert s.execute(text(f"SELECT status FROM {name}")).scalar_one() == "active"
            assert s.scalars(select(Probe)).one().status is ProductStatus.ACTIVE


class TestTask2TimestampMixin:
    def _probe(self):
        name = probe_name()
        return type(
            name,
            (ex.TimestampMixin, Base),
            {
                "__tablename__": name,
                "__annotations__": {"id": Mapped[int], "label": Mapped[str]},
                "id": mapped_column(primary_key=True),
            },
        )

    def test_columns(self):
        cols = self._probe().__table__.c
        assert cols.created_at.server_default is not None and cols.created_at.nullable is False
        assert cols.updated_at.onupdate is not None and cols.updated_at.nullable is True

    def test_created_by_server_updated_on_update(self, engine):
        Probe = self._probe()
        Base.metadata.create_all(engine)
        with Session(engine) as s:
            row = Probe(label="a")
            s.add(row)
            s.commit()
            assert isinstance(row.created_at, datetime)
            assert row.updated_at is None
            row.label = "b"
            s.commit()
            assert isinstance(row.updated_at, datetime)


class TestTask3UserModel:
    def test_table_and_columns(self):
        table = ex.User.__table__
        assert table.name == "users"
        assert set(table.c.keys()) == {
            "id", "email", "full_name", "nickname", "is_active", "created_at", "updated_at"
        }
        assert table.c.email.type.length == 255 and table.c.email.unique and table.c.email.index
        assert isinstance(table.c.full_name.type, String) and table.c.full_name.type.length == 100
        assert table.c.nickname.nullable is True
        assert table.c.full_name.nullable is False and table.c.email.nullable is False

    def test_defaults(self, session):
        user = ex.User(email="ann@example.com", full_name="Ann")
        session.add(user)
        session.commit()
        assert user.is_active is True and user.nickname is None
        assert ex.User.__table__.c.is_active.server_default is not None

    def test_repr(self, session):
        user = ex.User(email="ann@example.com", full_name="Ann")
        session.add(user)
        session.flush()
        assert repr(user) == "User(id=1, email='ann@example.com')"

    def test_unique_email(self, session):
        session.add_all(
            [ex.User(email="a@x.io", full_name="A"), ex.User(email="a@x.io", full_name="B")]
        )
        with pytest.raises(IntegrityError):
            session.commit()


class TestTask4ProductModel:
    def test_defaults(self, session):
        p = make_product(session)
        assert p.stock == 0 and p.status is ProductStatus.DRAFT and p.attributes == {}
        assert p.price == Decimal("9.99")

    def test_default_dict_not_shared(self, session):
        a, b = make_product(session, "A"), make_product(session, "B")
        assert a.attributes is not b.attributes

    def test_constraints_and_index(self, engine, session):
        insp = inspect(engine)
        checks = {c["name"] for c in insp.get_check_constraints("products")}
        assert {"ck_products_price_non_negative", "ck_products_stock_non_negative"} <= checks
        ix = {i["name"]: i["column_names"] for i in insp.get_indexes("products")}
        assert ix.get("ix_products_status_name") == ["status", "name"]

    @pytest.mark.parametrize("kw", [{"price": "-1"}, {"stock": -5}])
    def test_check_constraint_enforced(self, session, kw):
        with pytest.raises(IntegrityError):
            make_product(session, **kw)

    def test_status_stored_as_value(self, session):
        make_product(session, status=ProductStatus.ARCHIVED)
        assert session.execute(text("SELECT status FROM products")).scalar_one() == "archived"


class TestTask5InitDb:
    def test_creates_tables(self, engine):
        init_db(engine)
        assert {"users", "products"} <= set(inspect(engine).get_table_names())

    def test_idempotent(self, engine):
        init_db(engine)
        init_db(engine)

    def test_returns_bound_factory(self, engine):
        factory = init_db(engine)
        with factory() as s:
            assert isinstance(s, Session)
            assert s.get_bind() is engine


class TestTask6CreateUser:
    def test_normalises_and_loads_server_values(self, session):
        user = create_user(session, "  Ann@Example.COM ", "Ann")
        assert user.email == "ann@example.com"
        assert user.id == 1
        assert "created_at" in user.__dict__, "refresh() the user so server defaults are loaded"
        assert isinstance(user.created_at, datetime)

    def test_committed(self, engine, session):
        create_user(session, "bob@example.com", "Bob", nickname="bobby")
        with Session(engine) as other:
            row = other.scalars(select(ex.User)).one()
            assert (row.email, row.nickname, row.is_active) == ("bob@example.com", "bobby", True)

    def test_invalid_email(self, session):
        with pytest.raises(ValueError):
            create_user(session, "not-an-email", "X")
        assert not session.new


def add_user(session, email="a@x.io"):
    user = ex.User(email=email, full_name="A")
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


class TestTask7GetUserOrRaise:
    def test_found(self, session):
        user = add_user(session)
        assert get_user_or_raise(session, user.id) is user

    def test_missing(self, session):
        with pytest.raises(LookupError, match="User 42 not found"):
            get_user_or_raise(session, 42)

    def test_uses_identity_map(self, engine, session):
        user = add_user(session)
        statements = []
        event.listen(engine, "before_cursor_execute", lambda *a: statements.append(a[2]))
        get_user_or_raise(session, user.id)
        get_user_or_raise(session, user.id)
        assert statements == []


class TestTask8AddProduct:
    def test_adds_with_default_attributes(self, session):
        p = add_product(session, sku="S1", name="Mug", price=Decimal("4.50"))
        assert p.id == 1 and p.attributes == {}

    def test_attributes_saved(self, engine, session):
        add_product(session, sku="S1", name="Mug", price=Decimal("4.50"), attributes={"color": "red"})
        with Session(engine) as other:
            assert other.scalars(select(ex.Product)).one().attributes == {"color": "red"}

    def test_negative_price_rolls_back_and_session_still_usable(self, session):
        with pytest.raises(IntegrityError):
            add_product(session, sku="S1", name="Mug", price=Decimal("-1"))
        p = add_product(session, sku="S2", name="Cup", price=Decimal("1"))
        assert p.sku == "S2"

    def test_duplicate_sku(self, session):
        add_product(session, sku="S1", name="Mug", price=Decimal("1"))
        with pytest.raises(IntegrityError):
            add_product(session, sku="S1", name="Mug 2", price=Decimal("1"))
        assert session.scalars(select(ex.Product.name)).all() == ["Mug"]


class TestTask9SetProductAttribute:
    def test_persists_and_keeps_other_keys(self, engine, session):
        p = make_product(session, attributes={"color": "red"})
        set_product_attribute(session, p.id, "size", "XL")
        with Session(engine) as other:
            assert other.get(ex.Product, p.id).attributes == {"color": "red", "size": "XL"}

    def test_overwrites_key(self, engine, session):
        p = make_product(session, attributes={"color": "red"})
        set_product_attribute(session, p.id, "color", "blue")
        with Session(engine) as other:
            assert other.get(ex.Product, p.id).attributes == {"color": "blue"}

    def test_missing_product(self, session):
        with pytest.raises(LookupError):
            set_product_attribute(session, 99, "k", "v")
