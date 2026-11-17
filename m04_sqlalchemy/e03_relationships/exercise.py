"""Exercise 4.3: relationships, cascades, and loading strategies.

Three classic shapes, then the queries that load them without the N+1
problem:

* one-to-many: ``Author`` 1 -> * ``Book``
* many-to-many: ``Post`` * <-> * ``Tag`` through a plain association table
* association object: ``Order`` 1 -> * ``OrderLine`` * -> 1 ``Product``, where
  the link row carries data (quantity, unit price)

Run the tests with:

    uv run pytest m04_sqlalchemy/e03_relationships

The model classes start as plain placeholders so the module imports. Replace
each placeholder with the real mapped class.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal

from sqlalchemy import Column, ForeignKey, Numeric, String, Table, select
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    joinedload,
    mapped_column,
    relationship,
    selectinload,
)


class Base(DeclarativeBase):
    """Declarative base for this exercise (given)."""


class Product(Base):
    """A product that can be ordered (given, used by Task 3)."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))


# ---------------------------------------------------------------------------
# Task 1: one-to-many with back_populates and delete-orphan
# ---------------------------------------------------------------------------
# ``Author`` (table "authors"):
#   * id: Mapped[int] primary key; name: Mapped[str], String(100), unique
#   * books: Mapped[list["Book"]] = relationship(
#         back_populates="author", cascade="all, delete-orphan", order_by="Book.title")
#
# ``Book`` (table "books"):
#   * id: Mapped[int] primary key; title: Mapped[str], String(200)
#   * author_id: Mapped[int], ForeignKey("authors.id"), NOT NULL
#   * author: Mapped["Author"] = relationship(back_populates="books")
#
# ``back_populates`` keeps both sides in sync in Python, before any flush:
# ``book.author = a`` also appends ``book`` to ``a.books``.
# ``cascade="all, delete-orphan"``: deleting an author deletes their books, and
# a book removed from ``author.books`` is deleted (it cannot exist without one).

class Author(Base):
    __tablename__ = "authors"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    books: Mapped[list[Book]] = relationship(
        back_populates="author", cascade="all, delete-orphan", order_by="Book.title"
    )


class Book(Base):
    __tablename__ = "books"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    author_id: Mapped[int] = mapped_column(ForeignKey("authors.id"))
    author: Mapped[Author] = relationship(back_populates="books")


# ---------------------------------------------------------------------------
# Task 2: many-to-many through an association table
# ---------------------------------------------------------------------------
# ``post_tags``: a Core ``Table("post_tags", Base.metadata, ...)`` with two columns,
#   both part of the composite primary key:
#   * post_id -> ForeignKey("posts.id", ondelete="CASCADE")
#   * tag_id  -> ForeignKey("tags.id", ondelete="CASCADE")
#
# ``Post`` (table "posts"): id, title String(200),
#   tags: Mapped[list["Tag"]] = relationship(secondary=post_tags, back_populates="posts")
# ``Tag`` (table "tags"): id, name String(50) unique,
#   posts: Mapped[list["Post"]] = relationship(secondary=post_tags, back_populates="tags")
#
# Do not map ``post_tags`` as a class: with ``secondary=`` the ORM inserts and
# deletes its rows for you when you change ``post.tags``.

post_tags = Table(
    "post_tags",
    Base.metadata,
    Column("post_id", ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    tags: Mapped[list[Tag]] = relationship(secondary=post_tags, back_populates="posts")


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    posts: Mapped[list[Post]] = relationship(secondary=post_tags, back_populates="tags")


# ---------------------------------------------------------------------------
# Task 3: association object
# ---------------------------------------------------------------------------
# ``Order`` (table "orders"): id, customer String(100),
#   lines: Mapped[list["OrderLine"]] = relationship(
#       back_populates="order", cascade="all, delete-orphan")
#   and a read-only ``@property total -> Decimal``: the sum of
#   ``quantity * unit_price`` over all lines (``Decimal("0")`` with no lines).
#
# ``OrderLine`` (table "order_lines"), the association OBJECT, mapped as a class
# because the link carries data:
#   * order_id   ForeignKey("orders.id"),   part of the composite primary key
#   * product_id ForeignKey("products.id"), part of the composite primary key
#   * quantity: Mapped[int]
#   * unit_price: Mapped[Decimal], Numeric(10, 2): the price at order time
#   * order: Mapped["Order"] = relationship(back_populates="lines")
#   * product: Mapped["Product"] = relationship()      (one-directional)

class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer: Mapped[str] = mapped_column(String(100))
    lines: Mapped[list[OrderLine]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )

    @property
    def total(self) -> Decimal:
        return sum((line.quantity * line.unit_price for line in self.lines), Decimal("0"))


class OrderLine(Base):
    __tablename__ = "order_lines"

    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), primary_key=True)
    quantity: Mapped[int]
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    order: Mapped[Order] = relationship(back_populates="lines")
    product: Mapped[Product] = relationship()


# ---------------------------------------------------------------------------
# Task 4: get-or-create inside a many-to-many
# ---------------------------------------------------------------------------
def tag_post(session: Session, post: Post, names: Sequence[str]) -> list[Tag]:
    """Attach the tags called ``names`` to ``post`` and return ``post.tags``.

    * Reuse an existing ``Tag`` row when one with that name exists (look it up
      with ``select(Tag).where(Tag.name == name)``); otherwise create it.
    * Do not attach the same tag twice, even if ``names`` repeats a name or
      the post already has it.
    * ``session.flush()`` at the end; do not commit.

    >>> [t.name for t in tag_post(session, post, ["python", "sql", "python"])]  # doctest: +SKIP
    ['python', 'sql']
    """
    for name in names:
        if any(t.name == name for t in post.tags):
            continue
        tag = session.scalars(select(Tag).where(Tag.name == name)).one_or_none()
        if tag is None:
            tag = Tag(name=name)
        post.tags.append(tag)
    session.flush()
    return post.tags


# ---------------------------------------------------------------------------
# Task 5: build an order through the association object
# ---------------------------------------------------------------------------
def place_order(session: Session, customer: str, items: Mapping[int, int]) -> Order:
    """Create an ``Order`` with one ``OrderLine`` per ``{product_id: quantity}``.

    * Copy each product's current ``price`` into ``unit_price``: later price
      changes must not change old orders.
    * Raise ``LookupError`` if a product id does not exist, and add nothing
      to the session in that case.
    * Raise ``ValueError`` if a quantity is less than 1.
    * Add the order (lines follow through the cascade) and ``flush()``;
      do not commit.
    """
    lines: list[OrderLine] = []
    for product_id, quantity in items.items():
        if quantity < 1:
            raise ValueError(f"quantity must be >= 1, got {quantity}")
        product = session.get(Product, product_id)
        if product is None:
            raise LookupError(f"Product {product_id} not found")
        lines.append(OrderLine(product=product, quantity=quantity, unit_price=product.price))
    order = Order(customer=customer, lines=lines)
    session.add(order)
    session.flush()
    return order


# ---------------------------------------------------------------------------
# Task 6: selectinload for collections
# ---------------------------------------------------------------------------
def authors_with_books(session: Session) -> list[Author]:
    """Return all authors ordered by name, with ``books`` already loaded.

    Looping over the authors and touching ``author.books`` must not run any
    more SQL: the whole call runs exactly 2 statements (authors, then all
    their books with one ``IN`` query), however many authors there are.

    Hint: ``select(Author).options(selectinload(Author.books))``.
    ``selectinload`` is the usual best choice for one-to-many collections.
    """
    stmt = select(Author).options(selectinload(Author.books)).order_by(Author.name)
    return list(session.scalars(stmt))


# ---------------------------------------------------------------------------
# Task 7: joinedload for many-to-one
# ---------------------------------------------------------------------------
def books_with_authors(session: Session) -> list[Book]:
    """Return all books ordered by title, each with ``book.author`` loaded.

    Exactly 1 SQL statement in total (a ``LEFT OUTER JOIN``).

    Hint: ``joinedload(Book.author)``. ``joinedload`` suits many-to-one; for a
    collection it multiplies rows (then you would need ``.unique()``).
    """
    stmt = select(Book).options(joinedload(Book.author)).order_by(Book.title)
    return list(session.scalars(stmt))


# ---------------------------------------------------------------------------
# Task 8: chained loader options
# ---------------------------------------------------------------------------
def orders_with_details(session: Session) -> list[Order]:
    """Return all orders ordered by id with ``lines`` AND each line's
    ``product`` loaded, in at most 3 SQL statements in total.

    Hint: chain the options along the path:
    ``selectinload(Order.lines).joinedload(OrderLine.product)``.
    """
    stmt = (
        select(Order)
        .options(selectinload(Order.lines).joinedload(OrderLine.product))
        .order_by(Order.id)
    )
    return list(session.scalars(stmt))
