"""Exercise 4.2: ORM mapping with ``DeclarativeBase``, ``Mapped`` and ``mapped_column``.

You write the models of a tiny shop (users and products) the way a 2.x
codebase does it: typed annotations decide the column type and nullability,
``mapped_column()`` adds what the annotation cannot say. Then you write a few
session helpers on top. Run the tests with:

    uv run pytest m04_sqlalchemy/e02_orm_mapping

Note: the model classes below start life as plain placeholder classes, so the
module imports before you have written them. Replace each placeholder with the
real mapped class.
"""

from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Engine,
    Enum,
    Index,
    Numeric,
    String,
    func,
    true,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


class ProductStatus(enum.StrEnum):
    """Lifecycle of a product. Given: you do not need to change it."""

    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


# ---------------------------------------------------------------------------
# Task 1: the declarative base and its type map
# ---------------------------------------------------------------------------
class Base(DeclarativeBase):
    """The declarative base every model of this exercise inherits from.

    Give it a ``type_annotation_map`` so annotations map to these types
    without repeating them on every column:

    * ``dict[str, Any]``  -> ``JSON``
    * ``datetime``        -> ``DateTime(timezone=True)``
    * ``ProductStatus``   -> ``Enum(ProductStatus, ...)`` that stores the enum
      *values* (``"draft"``), not the member names (``"DRAFT"``, the default),
      as a ``VARCHAR(20)`` with no native database enum type. Pass
      ``native_enum=False``, ``length=20`` and
      ``values_callable=lambda e: [m.value for m in e]``.

    Why values? The value is what your API and other services see. Storing
    the Python member name couples the database to your variable names.

    ``int``, ``str``, ``bool``, ``Decimal`` already have default mappings.
    ``X | None`` makes a column nullable; plain ``X`` makes it ``NOT NULL``.
    """

    pass


# ---------------------------------------------------------------------------
# Task 2: a timestamp mixin
# ---------------------------------------------------------------------------
class TimestampMixin:
    """A plain mixin (NOT a subclass of ``Base``) that adds two columns.

    * ``created_at: Mapped[datetime]``: NOT NULL, ``server_default=func.now()``.
      The database fills it, so it is known only after a flush plus a refresh.
    * ``updated_at: Mapped[datetime | None]``: nullable, ``onupdate=func.now()``.
      SQLAlchemy sets it in every UPDATE it emits for the row; it stays
      ``None`` until the first update.

    Use it as ``class User(TimestampMixin, Base): ...``.
    """

    pass


# ---------------------------------------------------------------------------
# Task 3: the User model
# ---------------------------------------------------------------------------
# Write ``class User(TimestampMixin, Base)`` with ``__tablename__ = "users"``:
#
#   * id         Mapped[int], primary key
#   * email      Mapped[str], String(255), unique, indexed
#   * full_name  Mapped[str], String(100)
#   * nickname   Mapped[str | None], String(50)   -> nullable because of `| None`
#   * is_active  Mapped[bool], default=True AND server_default=true()
#
# and a ``__repr__`` returning exactly ``User(id=1, email='ann@example.com')``
# (use ``!r`` for the email). Do not touch other attributes in ``__repr__``:
# a repr that triggers lazy loads is a classic source of surprise queries.

pass
class User:  # TODO: replace with the mapped User model
    pass


# ---------------------------------------------------------------------------
# Task 4: the Product model
# ---------------------------------------------------------------------------
# Write ``class Product(Base)`` with ``__tablename__ = "products"``:
#
#   * id          Mapped[int], primary key
#   * sku         Mapped[str], String(32), unique
#   * name        Mapped[str], String(200)
#   * price       Mapped[Decimal], Numeric(10, 2)
#   * stock       Mapped[int], default=0, server_default="0"
#   * status      Mapped[ProductStatus], default=ProductStatus.DRAFT
#                 (the column type comes from Base.type_annotation_map)
#   * attributes  Mapped[dict[str, Any]], default=dict   <- a callable, so every
#                 row gets its own new dict. ``default={}`` would share one!
#
# ``__table_args__`` (a tuple) with:
#   * CheckConstraint("price >= 0", name="ck_products_price_non_negative")
#   * CheckConstraint("stock >= 0", name="ck_products_stock_non_negative")
#   * Index("ix_products_status_name", "status", "name")

pass
class Product:  # TODO: replace with the mapped Product model
    pass


# ---------------------------------------------------------------------------
# Task 5: create the schema, build a session factory
# ---------------------------------------------------------------------------
def init_db(engine: Engine) -> sessionmaker[Session]:
    """Create all tables of ``Base.metadata`` on ``engine`` and return a factory.

    * ``create_all`` is idempotent: calling ``init_db`` twice must not fail.
    * Return ``sessionmaker(bind=engine)``; ``factory()`` then gives a new
      ``Session`` bound to ``engine``.

    In a real service, Alembic migrations create the schema; ``create_all``
    is for tests and scripts.
    """
    raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 6: create a user
# ---------------------------------------------------------------------------
def create_user(
    session: Session, email: str, full_name: str, nickname: str | None = None
) -> User:
    """Create, commit, and return a new ``User``.

    * Normalise the email: strip surrounding whitespace and lowercase it.
    * Raise ``ValueError`` (before touching the session) if the normalised
      email has no ``"@"``.
    * ``session.add(...)``, ``session.commit()``, then ``session.refresh(user)``
      so server-generated values (``id``, ``created_at``) are loaded.
    """
    raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 7: get by primary key
# ---------------------------------------------------------------------------
def get_user_or_raise(session: Session, user_id: int) -> User:
    """Return the user with primary key ``user_id``.

    Raise ``LookupError(f"User {user_id} not found")`` if there is none.

    Hint: ``session.get(User, pk)`` looks in the identity map first and only
    queries the database on a miss. (``session.query(...)`` is the legacy
    1.x API; do not use it.)
    """
    raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 8: constraint violations
# ---------------------------------------------------------------------------
def add_product(
    session: Session,
    *,
    sku: str,
    name: str,
    price: Decimal,
    attributes: dict[str, Any] | None = None,
) -> Product:
    """Insert and commit a product; let the database enforce the rules.

    * Do not validate ``price`` in Python: the ``CHECK`` constraint does it.
    * ``attributes=None`` means "use the column default" (an empty dict).
    * If the commit raises ``IntegrityError`` (duplicate sku, negative price),
      call ``session.rollback()`` and re-raise the same exception. After a
      failed flush the session refuses all work until it is rolled back, so
      leaving it un-rolled-back breaks the caller's next query.
    """
    raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 9: updating a JSON column
# ---------------------------------------------------------------------------
def set_product_attribute(session: Session, product_id: int, key: str, value: Any) -> Product:
    """Set ``product.attributes[key] = value`` and commit.

    * Raise ``LookupError`` if the product does not exist.
    * Keep the other keys.
    * Gotcha: a plain ``JSON`` column does not track in-place mutation.
      ``product.attributes[key] = value`` changes the Python dict, but the ORM
      never notices, so nothing is written. Assign a NEW dict instead
      (``{**old, key: value}``). (``sqlalchemy.ext.mutable.MutableDict`` is the
      alternative when you control the model.)
    """
    raise NotImplementedError("TODO: implement this task")
