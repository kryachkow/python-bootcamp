"""Exercise 3.1: routing basics.

You build a small read-mostly API over an in-memory document catalogue:
typed path parameters, enum paths, query parameters, status codes, and
``APIRouter`` composition. The tests talk to the app through
``fastapi.testclient.TestClient(create_app())``.

Every route lives on one of the routers in this module. A route you have not
written yet simply does not exist, so its tests fail with ``404``.

Run the tests with:

    uv run pytest m03_fastapi/e01_routing_basics
"""

from enum import StrEnum
from typing import Annotated, Any, Literal

from fastapi import APIRouter, FastAPI, HTTPException, Query, status

# In-memory "database". Tests restore it after every test, so routes may mutate it.
DOCUMENTS: list[dict[str, Any]] = [
    {"id": 1, "title": "FastAPI tutorial", "tags": ["python", "web"], "archived": False},
    {"id": 2, "title": "Pydantic v2 migration guide", "tags": ["python", "pydantic"], "archived": False},
    {"id": 3, "title": "Prompt engineering notes", "tags": ["llm"], "archived": False},
    {"id": 4, "title": "Legacy Flask app", "tags": ["python", "web"], "archived": True},
    {"id": 5, "title": "RAG with LangChain", "tags": ["llm", "python"], "archived": False},
]

USERS: dict[int, dict[str, Any]] = {
    1: {"id": 1, "name": "alice"},
    2: {"id": 2, "name": "bob"},
}
CURRENT_USER_ID = 1  # pretend authentication already happened

# Tasks 1-5 and 7 register their routes on this router. ``create_app`` includes it.
router = APIRouter()


# ---------------------------------------------------------------------------
# Task 1: typed path parameters
# ---------------------------------------------------------------------------
# Add two routes to ``router``:
#
# * ``GET /items/{item_id}``: ``item_id`` is an ``int``. Return
#   ``{"item_id": item_id}`` (the JSON value must be a number, not a string).
#   A non-integer such as ``/items/abc`` must give ``422``. FastAPI does that
#   for you once the parameter is annotated.
# * ``GET /files/{file_path:path}``: the ``:path`` converter lets the
#   parameter contain slashes. Return ``{"file_path": file_path}``, so
#   ``/files/reports/2024/q1.csv`` gives ``{"file_path": "reports/2024/q1.csv"}``.
#
@router.get("/items/{item_id}")
def read_item(item_id: int) -> dict[str, int]:
    return {"item_id": item_id}


@router.get("/files/{file_path:path}")
def read_file(file_path: str) -> dict[str, str]:
    return {"file_path": file_path}


# ---------------------------------------------------------------------------
# Task 2: enum path parameter
# ---------------------------------------------------------------------------
class Provider(StrEnum):
    """LLM providers the API knows about (given, do not change)."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"


# ``GET /providers/{provider}``, where ``provider`` is annotated as ``Provider``.
#
# * Return ``{"provider": <value>, "local": <bool>}``. ``local`` is ``True``
#   only for ``Provider.OLLAMA`` (it runs on your machine).
# * An unknown provider such as ``/providers/cohere`` gives ``422``.
#   FastAPI validates enum values for you, and the docs list the allowed values.
#
@router.get("/providers/{provider}")
def read_provider(provider: Provider) -> dict[str, Any]:
    return {"provider": provider.value, "local": provider is Provider.OLLAMA}


# ---------------------------------------------------------------------------
# Task 3: optional query parameters with defaults
# ---------------------------------------------------------------------------
# ``GET /documents`` lists ``DOCUMENTS`` (in their stored order) and takes these
# query parameters:
#
# * ``q: str | None = None``: if given, keep only documents whose ``title``
#   contains ``q``, ignoring case.
# * ``include_archived: bool = False``: archived documents are hidden unless
#   this is true. FastAPI accepts ``true/false/1/0/yes/no``.
# * ``limit: int = 10`` and ``offset: int = 0``: paging, applied after filtering.
#
# Return ``{"total": <number of matches before paging>, "items": [<documents>]}``.
#
# Example: ``GET /documents?q=FASTAPI&limit=5`` returns
# ``{"total": 1, "items": [{"id": 1, "title": "FastAPI tutorial", ...}]}``.
#
@router.get("/documents")
def list_documents(
    q: str | None = None,
    include_archived: bool = False,
    limit: int = 10,
    offset: int = 0,
) -> dict[str, Any]:
    matches = [
        doc
        for doc in DOCUMENTS
        if (include_archived or not doc["archived"])
        and (q is None or q.lower() in doc["title"].lower())
    ]
    return {"total": len(matches), "items": matches[offset : offset + limit]}


# ---------------------------------------------------------------------------
# Task 4: list query parameters
# ---------------------------------------------------------------------------
# ``GET /tags/match?tag=python&tag=web&mode=all`` finds documents by tag.
#
# * A repeated ``tag`` query parameter becomes a Python list. Name the
#   function parameter ``tags`` and map it to the query key with
#   ``Annotated[list[str], Query(alias="tag")]``. It is required: a request
#   with no ``tag`` at all gives ``422``.
# * ``mode: Literal["any", "all"] = "any"``. ``"any"`` matches documents with
#   at least one of the tags, and ``"all"`` matches documents with every tag.
#   Any other value gives ``422``.
# * Search all documents, archived included, and keep their stored order.
#
# Return ``{"tags": tags, "mode": mode, "ids": [<matching document ids>]}``.
#
# Hint: a ``list[...]`` parameter without ``Query()`` would be read from the
# request body, not from the query string.
#
@router.get("/tags/match")
def match_tags(
    tags: Annotated[list[str], Query(alias="tag")],
    mode: Literal["any", "all"] = "any",
) -> dict[str, Any]:
    wanted = set(tags)
    check = wanted.issubset if mode == "all" else wanted.intersection
    ids = [doc["id"] for doc in DOCUMENTS if check(doc["tags"])]
    return {"tags": tags, "mode": mode, "ids": ids}


# ---------------------------------------------------------------------------
# Task 5: status codes
# ---------------------------------------------------------------------------
# * ``POST /reindex``: starts a (pretend) background reindex. Respond
#   ``202 Accepted`` with ``{"status": "accepted"}``.
# * ``DELETE /documents/{doc_id}``: remove the document from ``DOCUMENTS`` and
#   respond ``204 No Content`` with an empty body. If no document has that id,
#   raise ``HTTPException`` with status ``404`` and
#   ``detail=f"Document {doc_id} not found"``.
#
# Use ``status_code=`` on the decorator and the ``fastapi.status`` constants,
# not bare numbers.
#
@router.post("/reindex", status_code=status.HTTP_202_ACCEPTED)
def reindex() -> dict[str, str]:
    return {"status": "accepted"}


@router.delete("/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(doc_id: int) -> None:
    for index, doc in enumerate(DOCUMENTS):
        if doc["id"] == doc_id:
            del DOCUMENTS[index]
            return
    raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Document {doc_id} not found")


# ---------------------------------------------------------------------------
# Task 6: a users router (prefix, tags, and path order)
# ---------------------------------------------------------------------------
# Create ``users_router`` with ``prefix="/users"`` and ``tags=["users"]`` and
# give it two routes:
#
# * ``GET /users/me`` returns ``USERS[CURRENT_USER_ID]``.
# * ``GET /users/{user_id}`` (an ``int``) returns ``USERS[user_id]``, or raises
#   ``404`` with ``detail=f"User {user_id} not found"``.
#
# Routes are matched in the order they are declared. If ``/{user_id}`` comes
# first, ``/users/me`` matches it, fails int validation, and gives ``422``.
# Declare ``/me`` first.
#
# Then include ``users_router`` in the app (see ``create_app``).
#
users_router = APIRouter(prefix="/users", tags=["users"])


@users_router.get("/me")
def read_me() -> dict[str, Any]:
    return USERS[CURRENT_USER_ID]


@users_router.get("/{user_id}")
def read_user(user_id: int) -> dict[str, Any]:
    if user_id not in USERS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"User {user_id} not found")
    return USERS[user_id]


# ---------------------------------------------------------------------------
# Task 7: versioned API and hidden routes
# ---------------------------------------------------------------------------
# * Add ``GET /health`` to ``router``. It returns ``{"status": "ok"}`` and is
#   left out of the OpenAPI schema (``include_in_schema=False``), so load
#   balancers can call it but API docs do not list it.
# * In ``create_app``, also serve the users routes under ``/api/v1``: create
#   ``APIRouter(prefix="/api/v1")``, include ``users_router`` in it, then
#   include that router in the app. ``/api/v1/users/me`` and ``/users/me``
#   must both work.
#
@router.get("/health", include_in_schema=False)
def health() -> dict[str, str]:
    return {"status": "ok"}


def create_app() -> FastAPI:
    """Build the application (the tests call this for every test)."""
    app = FastAPI(title="Routing basics")
    app.include_router(router)
    # Task 6: include ``users_router`` here.
    app.include_router(users_router)
    # Task 7: serve ``users_router`` under ``/api/v1`` too.
    api_v1 = APIRouter(prefix="/api/v1")
    api_v1.include_router(users_router)
    app.include_router(api_v1)
    return app
