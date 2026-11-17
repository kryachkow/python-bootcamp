"""Exercise 3.4: errors, middleware, lifespan, and CORS.

This is the application "shell" that every production service needs before
it has a single feature: one error format, request IDs and timing, startup
and shutdown of shared clients, and CORS for the browser front end.

The path operations are given and already raise the right exceptions. You
write the handlers, the middleware, the lifespan, and the CORS setup, then
wire them into ``create_app``.

Run the tests with:

    uv run pytest m03_fastapi/e04_errors_middleware_lifespan
"""

import re
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import APIRouter, FastAPI, Header, HTTPException, Query, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
EXHAUSTED_TENANTS = {"acme"}
LIFECYCLE_EVENTS: list[str] = []  # Task 6 writes "startup" / "shutdown" here


# ---------------------------------------------------------------------------
# Given: domain exceptions (the service layer raises these, never HTTPException)
# ---------------------------------------------------------------------------
class DomainError(Exception):
    """Base class for errors that have a well-defined HTTP mapping."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "domain_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message
        self.headers: dict[str, str] | None = None


class NotFoundError(DomainError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"


class QuotaExceededError(DomainError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "quota_exceeded"

    def __init__(self, message: str, retry_after: int) -> None:
        super().__init__(message)
        self.headers = {"Retry-After": str(retry_after)}


# ---------------------------------------------------------------------------
# Given: a fake LLM client that must be created once and closed on shutdown
# ---------------------------------------------------------------------------
class FakeLLMClient:
    def __init__(self, model: str) -> None:
        self.model = model
        self.closed = False

    async def complete(self, prompt: str) -> str:
        if self.closed:
            raise RuntimeError("client is closed")
        return f"[{self.model}] {prompt}"

    async def aclose(self) -> None:
        self.closed = True


# ---------------------------------------------------------------------------
# Given: path operations
# ---------------------------------------------------------------------------
router = APIRouter()
DOCUMENTS = {1: "FastAPI tutorial", 2: "Prompt engineering notes"}


class CompletionIn(BaseModel):
    template: str
    text: str = Field(min_length=1)


@router.get("/documents/{doc_id}")
def read_document(doc_id: int) -> dict[str, Any]:
    if doc_id not in DOCUMENTS:
        raise NotFoundError(f"Document {doc_id} not found")
    return {"id": doc_id, "title": DOCUMENTS[doc_id]}


@router.post("/generate/{tenant}")
def generate(tenant: str) -> dict[str, str]:
    if tenant in EXHAUSTED_TENANTS:
        raise QuotaExceededError(f"Tenant '{tenant}' is out of tokens", retry_after=60)
    return {"tenant": tenant, "status": "generated"}


@router.get("/search")
def search(q: Annotated[str, Query(min_length=2)], limit: Annotated[int, Query(ge=1, le=50)] = 10) -> dict[str, Any]:
    return {"q": q, "limit": limit}


@router.get("/crash")
def crash() -> None:
    raise ValueError("db password is hunter2")  # must never reach the client


@router.get("/request-id")
def read_request_id(request: Request) -> dict[str, str]:
    return {"request_id": request.state.request_id}


@router.post("/complete")
async def complete(body: CompletionIn, request: Request) -> dict[str, str]:
    prompts: dict[str, str] = request.app.state.prompts
    if body.template not in prompts:
        raise NotFoundError(f"Prompt template '{body.template}' not found")
    llm: FakeLLMClient = request.app.state.llm
    return {"completion": await llm.complete(prompts[body.template].format(text=body.text))}


# ---------------------------------------------------------------------------
# Task 1: HTTPException with headers
# ---------------------------------------------------------------------------
# Add ``GET /protected`` to ``router``. It takes
# ``authorization: Annotated[str | None, Header()] = None``.
#
# * If the header is exactly ``"Bearer secret-token"``, return ``{"ok": True}``.
# * Otherwise raise ``HTTPException`` with ``401``,
#   ``detail="Not authenticated"``, and ``headers={"WWW-Authenticate": "Bearer"}``.
#   RFC 9110 requires that header on every 401.
#
# TODO: implement this task (see the spec above)


# ---------------------------------------------------------------------------
# Task 2: domain exception -> JSON error envelope
# ---------------------------------------------------------------------------
async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    """Turn any ``DomainError`` into the API's standard error envelope.

    * The status code is ``exc.status_code``.
    * The body is ``{"error": {"code": exc.code, "message": exc.message}}``.
    * Pass ``exc.headers`` on to the response. ``QuotaExceededError`` uses
      this to send ``Retry-After``.

    Register it in ``create_app`` with ``app.add_exception_handler(DomainError, ...)``.
    A handler registered for a base class also catches its subclasses.
    """
    raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 3: custom validation error format
# ---------------------------------------------------------------------------
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Reformat FastAPI's ``422`` into the same envelope as Task 2.

    Respond ``422`` with::

        {"error": {
            "code": "validation_error",
            "message": "Request validation failed",
            "details": [{"field": "query.limit", "message": "<pydantic msg>"}, ...]
        }}

    Build one ``details`` entry per item of ``exc.errors()``, in order.
    ``field`` is the error's ``loc`` with its parts joined by ``"."``, using
    ``str()`` on each part: ``("body", "items", 0)`` becomes ``"body.items.0"``.
    ``message`` is the error's ``msg``.
    """
    raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 4: catch-all handler for unexpected errors
# ---------------------------------------------------------------------------
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Answer ``500`` with
    ``{"error": {"code": "internal_error", "message": "Internal server error"}}``.

    Never put ``str(exc)`` in the response: exception messages leak internals
    such as SQL, file paths, and secrets. (A real service would log the
    exception here.)

    Register it for ``Exception``. Starlette runs it in its outermost
    ``ServerErrorMiddleware``. It sends your response, then re-raises the
    exception so servers and test clients still see it.
    """
    raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 5: request-ID and timing middleware
# ---------------------------------------------------------------------------
async def request_context_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """HTTP middleware that tags every request and response.

    1. Request ID: if the incoming ``X-Request-ID`` header matches
       ``REQUEST_ID_PATTERN``, reuse it, so one ID follows a call across
       services. If it is missing or invalid (it could be a log-injection
       attempt), generate ``uuid.uuid4().hex``.
    2. Store it on ``request.state.request_id`` before calling
       ``await call_next(request)``.
    3. On the response, set ``X-Request-ID`` to the ID and ``X-Process-Time``
       to the elapsed time in milliseconds, formatted with two decimals
       (``f"{ms:.2f}"``). Measure with ``time.perf_counter()``.

    Register it in ``create_app`` with ``app.middleware("http")(request_context_middleware)``.
    Error responses from Tasks 2-3 pass through it too, so they get the
    headers as well.
    """
    raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 6: lifespan
# ---------------------------------------------------------------------------
# Write ``lifespan(app)``, an ``@asynccontextmanager`` async generator that
# ``create_app`` passes to ``FastAPI(lifespan=...)``.
#
# Startup (before ``yield``):
#   * append ``"startup"`` to ``LIFECYCLE_EVENTS``
#   * ``app.state.llm = FakeLLMClient(model="fake-1")``
#   * ``app.state.prompts = {"summarize": "Summarize: {text}",
#                            "translate": "Translate to French: {text}"}``
# Shutdown (after ``yield``, even if the app crashed, so use ``try/finally``):
#   * ``await app.state.llm.aclose()``
#   * append ``"shutdown"`` to ``LIFECYCLE_EVENTS``
#
# The lifespan runs only when the ``TestClient`` is used as a context
# manager (``with TestClient(app) as client:``), like a real server process.
#
# TODO: replace the placeholder lifespan below (it only yields)
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield


# ---------------------------------------------------------------------------
# Task 7: CORS
# ---------------------------------------------------------------------------
def configure_cors(app: FastAPI, origins: list[str]) -> None:
    """Add ``CORSMiddleware`` so the browser front end at ``origins`` can call the API.

    * ``allow_origins=origins``. Never use ``"*"`` together with credentials.
    * ``allow_credentials=True`` (cookies and the Authorization header)
    * ``allow_methods=["GET", "POST"]``
    * ``allow_headers=["Authorization", "Content-Type", "X-Request-ID"]``
    * ``expose_headers=["X-Request-ID", "X-Process-Time"]``. Browsers hide
      response headers from JavaScript unless they are listed here.
    * ``max_age=600``: browsers may cache a preflight answer for 10 minutes.

    ``create_app`` calls this last, which makes CORS the outermost
    middleware, so its headers are present even on error responses.
    """
    # TODO: add CORSMiddleware (until then this function does nothing)


def create_app(cors_origins: list[str] | None = None) -> FastAPI:
    """Assemble the application.

    Register the handlers from Tasks 2-4 and the middleware from Task 5
    where marked. The lifespan (Task 6) and CORS (Task 7) are already wired in.
    """
    app = FastAPI(title="Errors, middleware, lifespan", lifespan=lifespan)
    app.include_router(router)
    # Tasks 2-4: register the exception handlers.
    # TODO: implement this task
    # Task 5: register the HTTP middleware.
    # TODO: implement this task
    configure_cors(app, cors_origins or ["https://app.example.com"])
    return app
