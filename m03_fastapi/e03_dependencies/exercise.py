"""Exercise 3.3: dependency injection with ``Depends``.

You build a small notes API whose cross-cutting concerns live in
dependencies: sorting and paging, a unit-of-work session, API-key
authentication, admin authorisation, and auditing. In the last task you write
the test helper that swaps the authenticated user through
``app.dependency_overrides``.

Run the tests with:

    uv run pytest m03_fastapi/e03_dependencies
"""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Query, Request, status
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Given: data and helpers (tests restore these lists after every test)
# ---------------------------------------------------------------------------
NOTES: list[dict[str, Any]] = [
    {"id": 1, "title": "buy milk", "owner": "alice"},
    {"id": 2, "title": "call mom", "owner": "bob"},
    {"id": 3, "title": "answer emails", "owner": "alice"},
    {"id": 4, "title": "deploy v2", "owner": "bob"},
    {"id": 5, "title": "write tests", "owner": "alice"},
]
SORTABLE_FIELDS = {"id", "title", "owner"}
SESSION_EVENTS: list[str] = []  # Task 3 writes the session lifecycle here
AUDIT_LOG: list[str] = []  # Task 6 writes audit lines here


class User(BaseModel):
    username: str
    is_admin: bool = False


API_KEYS: dict[str, User] = {
    "key-alice": User(username="alice", is_admin=True),
    "key-bob": User(username="bob"),
}


@dataclass(frozen=True)
class SortSpec:
    field: str
    descending: bool = False


class FakeSession:
    """A stand-in for a DB session: it buffers notes until ``commit()``.

    Every method call is appended to ``SESSION_EVENTS``, so the tests can
    check the lifecycle.
    """

    def __init__(self) -> None:
        self._pending: list[dict[str, Any]] = []

    def add(self, note: dict[str, Any]) -> None:
        SESSION_EVENTS.append("add")
        self._pending.append(note)

    def commit(self) -> None:
        SESSION_EVENTS.append("commit")
        NOTES.extend(self._pending)
        self._pending.clear()

    def rollback(self) -> None:
        SESSION_EVENTS.append("rollback")
        self._pending.clear()

    def close(self) -> None:
        SESSION_EVENTS.append("close")


class NoteIn(BaseModel):
    title: str
    owner: str = "anonymous"


router = APIRouter()


# ---------------------------------------------------------------------------
# Task 1: a function dependency
# ---------------------------------------------------------------------------
def parse_sort(sort: Annotated[str, Query()] = "id") -> SortSpec:
    """Turn the ``?sort=`` query parameter into a ``SortSpec``.

    * A leading ``-`` means descending: ``"-title"`` becomes
      ``SortSpec("title", descending=True)``. Without it, the sort is ascending.
    * The field must be in ``SORTABLE_FIELDS``. Otherwise raise
      ``HTTPException(400, detail=f"Cannot sort by '{field}'")``, using the
      field name without the ``-``.

    Then add ``GET /notes`` to ``router`` (below). It takes
    ``spec: Annotated[SortSpec, Depends(parse_sort)]`` and returns ``NOTES``
    sorted by ``spec``.

    >>> parse_sort("-owner")
    SortSpec(field='owner', descending=True)
    """
    raise NotImplementedError("TODO: implement this task")


# TODO: implement this task (see the spec above)


# ---------------------------------------------------------------------------
# Task 2: a class-based dependency
# ---------------------------------------------------------------------------
class Pagination:
    """Paging parameters, usable as ``Annotated[Pagination, Depends()]``.

    FastAPI reads a class's ``__init__`` signature just like a function's, so
    every ``__init__`` parameter becomes a query parameter:

    * ``page: Annotated[int, Query(ge=1)] = 1``
    * ``size: Annotated[int, Query(ge=1, le=50)] = 10``

    Store both as attributes, and add:

    * an ``offset`` property, equal to ``(page - 1) * size``;
    * ``apply(items)``, which returns the slice of ``items`` for this page.

    Then add ``GET /notes/page`` (below). It returns
    ``{"page": ..., "size": ..., "total": len(NOTES), "items": [...]}`` with
    notes in id order.

    Hint: ``Depends()`` with no argument reuses the annotated type as the
    dependency.
    """

    # TODO: implement this task


# TODO: implement this task (see the spec above)


# ---------------------------------------------------------------------------
# Task 3: a dependency with ``yield`` (unit of work)
# ---------------------------------------------------------------------------
def get_session() -> Iterator[FakeSession]:
    """Provide a ``FakeSession`` for one request, then finish it.

    1. Append ``"open"`` to ``SESSION_EVENTS`` and create a ``FakeSession``.
    2. ``yield`` it to the path operation.
    3. If the path operation raised (an ``HTTPException`` counts), call
       ``rollback()`` and re-raise. Otherwise call ``commit()``.
    4. Always call ``close()`` at the end.

    A successful request logs ``["open", "add", "commit", "close"]``.

    Then add ``POST /notes`` (below). It takes a ``NoteIn`` body and a
    ``session: Annotated[FakeSession, Depends(get_session)]``.

    * Build ``{"id": <max existing id + 1>, "title": ..., "owner": ...}`` and
      ``session.add`` it. Add first, check second: the rollback path should
      have something to undo.
    * If a note with the same title already exists, raise ``409`` with
      ``detail=f"Note '{title}' already exists"``.
    * Otherwise respond ``201`` with the new note. Do not commit in the
      endpoint: the dependency owns the transaction.

    Hint: ``try: yield ... except Exception: ...; raise`` / ``else`` / ``finally``.
    """
    raise NotImplementedError("TODO: implement this task")


# TODO: implement this task (see the spec above)


# ---------------------------------------------------------------------------
# Task 4: API-key authentication (a sub-dependency chain)
# ---------------------------------------------------------------------------
def get_api_key(x_api_key: Annotated[str | None, Header()] = None) -> str:
    """Read the ``X-API-Key`` request header and return it.

    FastAPI maps the parameter ``x_api_key`` to the header ``x-api-key``.

    If the header is missing or empty, raise ``401`` with
    ``detail="Missing API key"`` and the response header
    ``WWW-Authenticate: ApiKey``.
    """
    raise NotImplementedError("TODO: implement this task")


def get_current_user(api_key: Annotated[str, Depends(get_api_key)]) -> User:
    """Look up the ``User`` that owns ``api_key`` in ``API_KEYS``.

    If the key is unknown, raise ``401`` with ``detail="Invalid API key"`` and
    the same ``WWW-Authenticate: ApiKey`` header.

    Then add ``GET /me`` (below). It returns the current user, for example
    ``{"username": "bob", "is_admin": false}``.
    """
    raise NotImplementedError("TODO: implement this task")


CurrentUser = Annotated[User, Depends(get_current_user)]


# TODO: implement this task (see the spec above)


# ---------------------------------------------------------------------------
# Task 5: authorisation on top of authentication
# ---------------------------------------------------------------------------
def require_admin(user: CurrentUser) -> User:
    """Return ``user`` if ``user.is_admin``. Otherwise raise ``403`` with
    ``detail="Admin privileges required"``.

    Unauthenticated requests never get this far: ``get_current_user`` has
    already answered ``401``.

    Then add ``DELETE /notes/{note_id}`` (below), protected by
    ``Depends(require_admin)``. It removes the note and responds ``204``. An
    unknown id gives ``404`` with ``detail=f"Note {note_id} not found"``.
    """
    raise NotImplementedError("TODO: implement this task")


# TODO: implement this task (see the spec above)


# ---------------------------------------------------------------------------
# Task 6: router-level dependencies
# ---------------------------------------------------------------------------
def record_audit(request: Request, user: CurrentUser) -> None:
    """Append ``f"{user.username} {request.method} {request.url.path}"`` to
    ``AUDIT_LOG``, for example ``"alice GET /admin/stats"``.

    This dependency returns nothing. It runs only for its side effect.
    """
    raise NotImplementedError("TODO: implement this task")


# Create ``admin_router`` with ``prefix="/admin"``, ``tags=["admin"]``, and
# ``dependencies=[Depends(require_admin), Depends(record_audit)]``. Every route
# on it is then admin-only and audited, and no route has to repeat that.
#
# Add ``GET /admin/stats``. It returns
# ``{"notes": len(NOTES), "api_keys": len(API_KEYS)}``.
# ``create_app`` already includes ``admin_router``.
#
# Within one request, FastAPI runs ``get_current_user`` once and caches the
# result, even though both dependencies need it.
#
admin_router = APIRouter()


def create_app() -> FastAPI:
    """Build the application (given)."""
    app = FastAPI(title="Dependencies")
    app.include_router(router)
    app.include_router(admin_router)
    return app


# ---------------------------------------------------------------------------
# Task 7: dependency overrides (a test helper)
# ---------------------------------------------------------------------------
@contextmanager
def override_user(app: FastAPI, user: User) -> Iterator[None]:
    """Make every request to ``app`` act as ``user`` inside the ``with`` block.

    * Inside the block, ``app.dependency_overrides[get_current_user]`` is a
      function that returns ``user``. No API key is needed, and
      ``require_admin`` and ``record_audit`` receive ``user`` as well.
    * On exit, even if the block raised, restore whatever override was there
      before. If there was none, remove the key. Nested ``override_user``
      blocks must restore correctly.

    This is how you test protected endpoints without real credentials::

        with override_user(app, User(username="carol", is_admin=True)):
            client.get("/admin/stats")   # 200
    """
    raise NotImplementedError("TODO: implement this task")
