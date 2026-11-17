from decimal import Decimal

import pytest
from sqlalchemy import create_engine, event, func, inspect, select
from sqlalchemy.orm import Session

from m04_sqlalchemy.e03_relationships import exercise as ex
from m04_sqlalchemy.e03_relationships.exercise import (
    Base,
    Product,
    authors_with_books,
    books_with_authors,
    orders_with_details,
    place_order,
    tag_post,
)


class StatementCounter:
    """Records every SQL statement the engine sends to the database."""

    def __init__(self, engine):
        self.statements: list[str] = []
        event.listen(engine, "before_cursor_execute", self._record)

    def _record(self, conn, cursor, statement, parameters, context, executemany):
        self.statements.append(statement)

    @property
    def count(self) -> int:
        return len(self.statements)

    def reset(self) -> None:
        self.statements.clear()


@pytest.fixture
def engine():
    eng = create_engine("sqlite://")

    @event.listens_for(eng, "connect")
    def _fk_on(dbapi_conn, _record):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    yield eng
    eng.dispose()


@pytest.fixture
def session(engine):
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture
def sql(engine):
    return StatementCounter(engine)


def count(session, model) -> int:
    return session.scalar(select(func.count()).select_from(model))


def seed_library(session, n_authors=3, books_each=2):
    for i in range(n_authors):
        author = ex.Author(name=f"Author {i}")
        author.books = [ex.Book(title=f"Book {i}-{j}") for j in range(books_each)]
        session.add(author)
    session.commit()
    session.expunge_all()


def seed_products(session):
    session.add_all(
        [
            Product(id=1, name="Mug", price=Decimal("5.00")),
            Product(id=2, name="Tea", price=Decimal("2.50")),
            Product(id=3, name="Pot", price=Decimal("20.00")),
        ]
    )
    session.commit()


class TestTask1OneToMany:
    def test_back_populates_syncs_in_python(self):
        author, book = ex.Author(name="Ann"), ex.Book(title="SQL")
        book.author = author
        assert author.books == [book]

    def test_persisted_with_fk(self, session):
        author = ex.Author(name="Ann", books=[ex.Book(title="B"), ex.Book(title="A")])
        session.add(author)
        session.commit()
        session.expire_all()
        assert [b.title for b in author.books] == ["A", "B"], "order_by Book.title"
        assert all(b.author_id == author.id for b in author.books)

    def test_delete_author_cascades(self, session):
        seed_library(session)
        session.delete(session.scalars(select(ex.Author).where(ex.Author.name == "Author 0")).one())
        session.commit()
        assert count(session, ex.Book) == 4

    def test_removed_book_is_deleted_as_orphan(self, session):
        seed_library(session, n_authors=1, books_each=3)
        author = session.scalars(select(ex.Author)).one()
        author.books.pop(0)
        session.commit()
        assert count(session, ex.Book) == 2

    def test_author_id_not_nullable(self):
        assert ex.Book.__table__.c.author_id.nullable is False


class TestTask2ManyToMany:
    def test_association_table(self, engine, session):
        assert isinstance(ex.post_tags, type(Base.metadata.tables["posts"]))
        assert {c.name for c in ex.post_tags.primary_key} == {"post_id", "tag_id"}
        fks = {fk["referred_table"]: fk for fk in inspect(engine).get_foreign_keys("post_tags")}
        assert set(fks) == {"posts", "tags"}
        assert fks["posts"]["options"].get("ondelete") == "CASCADE"

    def test_both_sides_sync(self):
        post, tag = ex.Post(title="Hi"), ex.Tag(name="python")
        post.tags.append(tag)
        assert tag.posts == [post]

    def test_rows_in_association_table(self, session):
        python, sql = ex.Tag(name="python"), ex.Tag(name="sql")
        session.add_all([ex.Post(title="A", tags=[python, sql]), ex.Post(title="B", tags=[python])])
        session.commit()
        assert count(session, ex.post_tags) == 3
        assert {p.title for p in python.posts} == {"A", "B"}

    def test_deleting_post_keeps_tags(self, session):
        post = ex.Post(title="A", tags=[ex.Tag(name="python")])
        session.add(post)
        session.commit()
        session.delete(post)
        session.commit()
        assert count(session, ex.post_tags) == 0
        assert count(session, ex.Tag) == 1


class TestTask3AssociationObject:
    def test_composite_primary_key(self):
        pk = {c.name for c in ex.OrderLine.__table__.primary_key}
        assert pk == {"order_id", "product_id"}

    def test_total(self, session):
        seed_products(session)
        mug, tea = session.get(Product, 1), session.get(Product, 2)
        order = ex.Order(
            customer="ann",
            lines=[
                ex.OrderLine(product=mug, quantity=2, unit_price=mug.price),
                ex.OrderLine(product=tea, quantity=3, unit_price=tea.price),
            ],
        )
        session.add(order)
        session.commit()
        assert order.total == Decimal("17.50")
        assert ex.Order(customer="empty").total == Decimal("0")

    def test_remove_line_and_delete_order(self, session):
        seed_products(session)
        order = ex.Order(
            customer="ann",
            lines=[
                ex.OrderLine(product=session.get(Product, pid), quantity=1, unit_price=Decimal(1))
                for pid in (1, 2, 3)
            ],
        )
        session.add(order)
        session.commit()
        order.lines.pop()
        session.commit()
        assert count(session, ex.OrderLine) == 2
        session.delete(order)
        session.commit()
        assert count(session, ex.OrderLine) == 0
        assert count(session, Product) == 3, "products must survive"


class TestTask4TagPost:
    def test_creates_tags_once(self, session):
        post = ex.Post(title="A")
        session.add(post)
        tags = tag_post(session, post, ["python", "sql", "python"])
        assert [t.name for t in tags] == ["python", "sql"]
        assert count(session, ex.Tag) == 2

    def test_reuses_existing_tags(self, session):
        a, b = ex.Post(title="A"), ex.Post(title="B")
        session.add_all([a, b])
        tag_post(session, a, ["python"])
        tag_post(session, b, ["python", "fastapi"])
        assert count(session, ex.Tag) == 2
        assert a.tags[0] is b.tags[0]

    def test_already_attached(self, session):
        post = ex.Post(title="A")
        session.add(post)
        tag_post(session, post, ["python"])
        tag_post(session, post, ["python"])
        assert count(session, ex.post_tags) == 1

    def test_flushes_but_does_not_commit(self, session):
        post = ex.Post(title="A")
        session.add(post)
        tag_post(session, post, ["python"])
        assert post.id is not None
        session.rollback()
        assert count(session, ex.Tag) == 0


class TestTask5PlaceOrder:
    def test_lines_and_prices(self, session):
        seed_products(session)
        order = place_order(session, "ann", {1: 2, 3: 1})
        assert order.id is not None
        assert sorted((line.product.name, line.quantity) for line in order.lines) == [
            ("Mug", 2),
            ("Pot", 1),
        ]
        assert order.total == Decimal("30.00")

    def test_price_snapshot(self, session):
        seed_products(session)
        order = place_order(session, "ann", {2: 4})
        session.get(Product, 2).price = Decimal("99")
        session.flush()
        session.expire(order)
        assert order.total == Decimal("10.00")

    def test_unknown_product(self, session):
        seed_products(session)
        with pytest.raises(LookupError):
            place_order(session, "ann", {1: 1, 42: 1})
        session.flush()
        assert count(session, ex.Order) == 0 and count(session, ex.OrderLine) == 0

    def test_bad_quantity(self, session):
        seed_products(session)
        with pytest.raises(ValueError):
            place_order(session, "ann", {1: 0})


class TestTask6SelectinLoad:
    def test_naive_loop_is_n_plus_one(self, session, sql):
        """Shows the problem the task solves (lazy loading, one query per author)."""
        seed_library(session, n_authors=5)
        sql.reset()
        for author in session.scalars(select(ex.Author)):
            _ = author.books
        assert sql.count == 1 + 5

    @pytest.mark.parametrize("n_authors", [2, 10])
    def test_two_statements_regardless_of_size(self, session, sql, n_authors):
        seed_library(session, n_authors=n_authors)
        sql.reset()
        authors = authors_with_books(session)
        titles = [b.title for a in authors for b in a.books]
        assert len(titles) == n_authors * 2
        assert sql.count == 2
        assert " IN " in sql.statements[1].upper()

    def test_ordered_and_usable_after_close(self, engine):
        Base.metadata.create_all(engine)
        with Session(engine) as s:
            seed_library(s, n_authors=3)
            authors = authors_with_books(s)
        assert [a.name for a in authors] == ["Author 0", "Author 1", "Author 2"]
        assert [b.title for b in authors[2].books] == ["Book 2-0", "Book 2-1"]


class TestTask7JoinedLoad:
    def test_single_statement_with_join(self, session, sql):
        seed_library(session, n_authors=4)
        sql.reset()
        books = books_with_authors(session)
        assert [b.author.name for b in books][:2] == ["Author 0", "Author 0"]
        assert len(books) == 8
        assert sql.count == 1
        assert "JOIN" in sql.statements[0].upper()

    def test_ordered_by_title(self, session):
        author = ex.Author(name="A", books=[ex.Book(title="Zeta"), ex.Book(title="Alpha")])
        session.add(author)
        session.commit()
        assert [b.title for b in books_with_authors(session)] == ["Alpha", "Zeta"]


class TestTask8ChainedOptions:
    def test_at_most_three_statements(self, session, sql):
        seed_products(session)
        for customer in ("ann", "bob", "cy"):
            place_order_rows = [
                ex.OrderLine(product=session.get(Product, pid), quantity=pid, unit_price=Decimal(pid))
                for pid in (1, 2, 3)
            ]
            session.add(ex.Order(customer=customer, lines=place_order_rows))
        session.commit()
        session.expunge_all()
        sql.reset()
        orders = orders_with_details(session)
        names = [(o.customer, line.product.name) for o in orders for line in o.lines]
        assert len(names) == 9
        assert [o.customer for o in orders] == ["ann", "bob", "cy"]
        assert sql.count <= 3

    def test_no_orders(self, session):
        assert orders_with_details(session) == []
