"""Exercise 3.5: a CRUD service with SQLAlchemy 2.x.

A ``/datasets`` resource, the kind of metadata service that sits next to a
RAG pipeline, backed by the SQLAlchemy 2.x ORM on in-memory SQLite. The
endpoints are plain ``def``, which FastAPI runs in its threadpool. The README
explains why this exercise uses sync SQLAlchemy and shows how each line maps
to ``AsyncSession``.

Given: the ORM model, the engine and sessionmaker lifecycle (``lifespan``),
and the ``create_app`` factory. You write the Pydantic schemas, the session
dependency, and the five endpoints. Tasks 3-7 build on Tasks 1-2.

Run the tests with:

    uv run pytest m03_fastapi/e05_crud_with_sqlalchemy
"""

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Integer, String, Text, create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool

DatasetKind = Literal["text", "tabular", "image"]


# ---------------------------------------------------------------------------
# Given: ORM model
# ---------------------------------------------------------------------------
class Base(DeclarativeBase):
    pass


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(20))
    row_count: Mapped[int] = mapped_column(Integer, default=0)


# ---------------------------------------------------------------------------
# Given: engine lifecycle
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create the engine and tables at startup, and dispose of the engine at shutdown.

    * ``StaticPool`` keeps one connection for the whole app. Each new
      connection to an in-memory SQLite database would otherwise get its own
      empty database.
    * ``check_same_thread=False``: sync endpoints run on threadpool threads,
      not on the thread that opened the connection.
    * ``expire_on_commit=False`` keeps ORM attributes loaded after
      ``commit()``, so you can return the object without a reload query.
      With ``AsyncSession`` this matters even more: a lazy reload there raises
      ``MissingGreenlet``.
    """
    engine = create_engine(
        app.state.database_url,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    app.state.sessionmaker = sessionmaker(engine, expire_on_commit=False)
    try:
        yield
    finally:
        engine.dispose()


# ---------------------------------------------------------------------------
# Task 1: API schemas
# ---------------------------------------------------------------------------
# Define three Pydantic models:
#
# ``DatasetCreate`` (POST body):
#   * ``name: str``, 1-100 characters
#   * ``description: str | None = None``, at most 500 characters
#   * ``kind: DatasetKind``
#   * ``row_count: int = 0``, ``>= 0``
#
# ``DatasetUpdate`` (PATCH body). Every field may be left out:
#   * ``name``, ``kind`` and ``row_count`` have the same rules as above, but
#     their default is ``None``. An explicit JSON ``null`` for them must give
#     ``422``, because the columns are NOT NULL. The idiom is
#     ``name: str = Field(default=None, min_length=1, max_length=100)``:
#     Pydantic does not validate defaults, but a null sent by the client is
#     validated against ``str`` and fails.
#   * ``description: str | None = None``, at most 500 characters. Here
#     ``null`` is allowed and means "clear the description".
#
# ``DatasetOut`` (responses): ``id``, ``name``, ``description``, ``kind``,
# ``row_count``, with ``model_config = ConfigDict(from_attributes=True)``, so
# it can be built from a ``Dataset`` ORM object.
#
# TODO: replace the placeholder classes below with the real models
class DatasetCreate(BaseModel):
    pass


class DatasetUpdate(BaseModel):
    pass


class DatasetOut(BaseModel):
    pass


class DatasetPage(BaseModel):
    """Given: the list response."""

    total: int
    items: list[DatasetOut]


# ---------------------------------------------------------------------------
# Task 2: the session dependency
# ---------------------------------------------------------------------------
def get_session(request: Request) -> Iterator[Session]:
    """Yield one ``Session`` per request.

    Open it from ``request.app.state.sessionmaker`` with ``with`` and
    ``yield`` it inside that block. The context manager closes the session
    when the request ends, and that rolls back anything not committed, even
    if the endpoint raised.

    Endpoints commit explicitly: ``session.commit()``. (The async version is
    the same with ``async def``, ``async with``, and ``AsyncSession``.)
    """
    raise NotImplementedError("TODO: implement this task")


SessionDep = Annotated[Session, Depends(get_session)]
router = APIRouter(prefix="/datasets", tags=["datasets"])


# ---------------------------------------------------------------------------
# Task 3: create (201 / 409)
# ---------------------------------------------------------------------------
# ``POST /datasets`` takes a ``DatasetCreate`` body and returns a
# ``DatasetOut`` with status ``201``.
#
# * Build ``Dataset(**payload.model_dump())``, ``session.add`` it, and
#   ``session.commit()``.
# * The ``name`` column is UNIQUE, so a duplicate makes ``commit()`` raise
#   ``sqlalchemy.exc.IntegrityError``. Catch it, ``session.rollback()``,
#   and raise ``409`` with ``detail=f"Dataset '{name}' already exists"``.
#   Let the database enforce uniqueness rather than doing SELECT-then-INSERT,
#   which has a race condition.
#
# TODO: implement this task (see the spec above)


# ---------------------------------------------------------------------------
# Task 4: read one (404)
# ---------------------------------------------------------------------------
# ``GET /datasets/{dataset_id}`` returns the dataset as ``DatasetOut``.
# If it does not exist, raise ``404`` with
# ``detail=f"Dataset {dataset_id} not found"``.
#
# Hint: ``session.get(Dataset, dataset_id)`` returns ``None`` when the
# row is missing. Tasks 6 and 7 need the same lookup, so a small helper pays off.
#
# TODO: implement this task (see the spec above)


# ---------------------------------------------------------------------------
# Task 5: list with filters and pagination
# ---------------------------------------------------------------------------
# ``GET /datasets`` returns a ``DatasetPage``. Query parameters:
#
# * ``kind: DatasetKind | None = None``: exact match.
# * ``q: str | None = None``: the name contains ``q``, ignoring case. Use
#   ``Dataset.name.icontains(q, autoescape=True)``, so ``%`` and ``_`` in ``q``
#   are matched literally rather than as wildcards.
# * ``limit``: 1-100, default 20. ``offset``: ``>= 0``, default 0.
#
# ``total`` counts every row that matches the filters (ignoring
# limit/offset). ``items`` is the requested page, ordered by ``id``.
#
# Hint: build a list of conditions once, then use it in two statements:
# ``select(func.count()).select_from(Dataset).where(*conditions)`` and
# ``select(Dataset).where(*conditions).order_by(Dataset.id).limit(...).offset(...)``.
# Run them with ``session.scalar(...)`` and ``session.scalars(...)``.
#
# TODO: implement this task (see the spec above)


# ---------------------------------------------------------------------------
# Task 6: partial update
# ---------------------------------------------------------------------------
# ``PATCH /datasets/{dataset_id}`` takes a ``DatasetUpdate`` body and returns
# the updated ``DatasetOut``.
#
# * ``404`` as in Task 4.
# * Apply only the fields the client actually sent:
#   ``payload.model_dump(exclude_unset=True)``, then ``setattr`` each one on
#   the ORM object. A field left out stays as it is. ``"description": null``
#   clears the description. (This is why ``exclude_none`` would be wrong here.)
# * Commit. Renaming to a name that is already taken gives ``409``, with the
#   same detail as in Task 3 (the name that was sent).
#
# TODO: implement this task (see the spec above)


# ---------------------------------------------------------------------------
# Task 7: delete
# ---------------------------------------------------------------------------
# ``DELETE /datasets/{dataset_id}`` deletes the row and responds ``204`` with
# no body. ``404`` as in Task 4.
#
# Hint: ``session.delete(obj)``, then commit. (On ``AsyncSession``, ``delete``
# is a coroutine, so you would write ``await session.delete(obj)``.)
#
# TODO: implement this task (see the spec above)


def create_app(database_url: str = "sqlite://") -> FastAPI:
    """Build the application (given). Use it with ``with TestClient(create_app()) as client:``."""
    app = FastAPI(title="Datasets CRUD", lifespan=lifespan)
    app.state.database_url = database_url
    app.include_router(router)
    return app
