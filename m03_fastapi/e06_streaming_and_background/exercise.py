"""Exercise 3.6: streaming, background work, async I/O, uploads, and WebSockets.

These are the parts of FastAPI an LLM backend leans on: token streaming over
Server-Sent Events, fire-and-forget indexing after a response, fan-out to
several async services at once, streamed uploads, and a WebSocket chat
channel.

The "LLM" and the "metadata service" are deterministic fakes (given).

Run the tests with:

    uv run pytest m03_fastapi/e06_streaming_and_background
"""

import asyncio
import json
from collections.abc import AsyncIterable, AsyncIterator
from typing import Annotated, Any

from fastapi import (
    APIRouter,
    BackgroundTasks,
    FastAPI,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.responses import StreamingResponse
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Given: fakes and shared state (tests reset these)
# ---------------------------------------------------------------------------
INDEX_LOG: list[str] = []  # Task 5 background tasks append here
FETCH_STATS = {"in_flight": 0, "max_in_flight": 0, "calls": 0}  # Task 6
METADATA = {1: {"id": 1, "title": "FastAPI tutorial"}, 2: {"id": 2, "title": "RAG notes"}, 3: {"id": 3, "title": "Evals"}}
MAX_UPLOAD_BYTES = 1_000
WS_TOKEN = "secret"


async def fake_llm_stream(prompt: str) -> AsyncIterator[str]:
    """Stream the reply ``"Echo: <prompt>"`` one word at a time.

    Every token after the first starts with a space, so ``"".join(tokens)``
    rebuilds the text exactly: ``"Echo:"``, ``" hello"``, ``" world"``.
    """
    for i, word in enumerate(f"Echo: {prompt}".split()):
        await asyncio.sleep(0)  # yield control, like a real network read
        yield word if i == 0 else " " + word


async def fetch_metadata(doc_id: int) -> dict[str, Any] | None:
    """A slow remote lookup. It returns ``None`` for unknown ids and tracks concurrency."""
    FETCH_STATS["calls"] += 1
    FETCH_STATS["in_flight"] += 1
    FETCH_STATS["max_in_flight"] = max(FETCH_STATS["max_in_flight"], FETCH_STATS["in_flight"])
    try:
        await asyncio.sleep(0.01)
        return METADATA.get(doc_id)
    finally:
        FETCH_STATS["in_flight"] -= 1


class ChatIn(BaseModel):
    prompt: str = Field(min_length=1)


class DocumentIn(BaseModel):
    id: str
    text: str


router = APIRouter()


# ---------------------------------------------------------------------------
# Task 1: a plain-text StreamingResponse
# ---------------------------------------------------------------------------
# ``GET /count?n=3`` streams ``"1\n"``, ``"2\n"``, ``"3\n"`` as separate chunks.
#
# * ``n: Annotated[int, Query(ge=1, le=100)]`` (required).
# * Return ``StreamingResponse(<async generator>, media_type="text/plain")``.
#   Call ``await asyncio.sleep(0)`` between chunks, as a real producer would.
#
# The client side looks like this:
# ``with client.stream("GET", "/count", params={"n": 3}) as r: r.iter_lines()``.
#
# TODO: implement this task (see the spec above)


# ---------------------------------------------------------------------------
# Task 2: the SSE wire format
# ---------------------------------------------------------------------------
def format_sse(data: str, event: str | None = None, id: str | None = None) -> str:
    """Encode one Server-Sent Event.

    Write the fields in this order, one ``field: value`` line each:

    1. ``id: <id>``, only if ``id`` is given
    2. ``event: <event>``, only if ``event`` is given
    3. one ``data: <line>`` per line of ``data``. A multi-line payload
       becomes several ``data:`` lines, which the browser joins back with
       ``\\n``. Use ``data.split("\\n")``, so empty data gives one ``data: `` line.

    End the event with a blank line, so the result ends with ``"\\n\\n"``.

    >>> format_sse("hi")
    'data: hi\\n\\n'
    >>> format_sse("a\\nb", event="done", id="7")
    'id: 7\\nevent: done\\ndata: a\\ndata: b\\n\\n'
    """
    raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 3: stream LLM tokens as SSE by hand
# ---------------------------------------------------------------------------
# ``POST /chat/stream`` takes a ``ChatIn`` body and streams ``fake_llm_stream(prompt)``:
#
# * For every token, send ``format_sse(json.dumps({"token": token}))``.
# * Finish with ``format_sse("[DONE]", event="done")``. This is the OpenAI
#   convention, and it lets clients tell "finished" from "connection dropped".
# * ``media_type="text/event-stream"``, plus the headers
#   ``Cache-Control: no-cache`` and ``X-Accel-Buffering: no``. The second one
#   stops nginx from buffering the stream into one late blob.
#
# TODO: implement this task (see the spec above)


# ---------------------------------------------------------------------------
# Task 4: the same with FastAPI's built-in SSE support
# ---------------------------------------------------------------------------
# Recent FastAPI versions encode SSE for you. Declare
# ``response_class=EventSourceResponse`` and make the path operation an
# async *generator* that yields ``fastapi.sse.ServerSentEvent`` objects.
#
# ``GET /chat/events?prompt=...`` (``prompt``: a required query string):
#
# * for token number ``i`` (from 0), yield
#   ``ServerSentEvent(data={"token": token}, event="token", id=str(i))``.
#   ``data`` is JSON-encoded for you.
# * finish with ``ServerSentEvent(raw_data="[DONE]", event="done")``.
#   ``raw_data`` is sent as is, not JSON-encoded.
#
# FastAPI sets ``text/event-stream`` and the no-cache headers itself.
# Annotate the return type as ``AsyncIterable[ServerSentEvent]``.
#
# TODO: implement this task (see the spec above)


# ---------------------------------------------------------------------------
# Task 5: background tasks
# ---------------------------------------------------------------------------
def index_document(doc_id: str, text: str) -> None:
    """Background job (sync): append ``f"indexed:{doc_id}:{<word count>}"`` to ``INDEX_LOG``.

    Words are whitespace-separated, so ``"a b  c"`` has 3.
    """
    raise NotImplementedError("TODO: implement this task")


async def notify_indexed(doc_id: str) -> None:
    """Background job (async): ``await asyncio.sleep(0)``, then append
    ``f"notified:{doc_id}"`` to ``INDEX_LOG``."""
    raise NotImplementedError("TODO: implement this task")


# ``POST /documents`` takes a ``DocumentIn`` body and a ``BackgroundTasks``
# parameter.
#
# * Schedule ``index_document(id, text)`` and then ``notify_indexed(id)``
#   with ``background_tasks.add_task(func, *args)``. They run in that order,
#   after the response has been sent.
# * Respond ``202`` with ``{"id": <id>, "status": "queued"}``.
#
# ``TestClient`` waits for background tasks before it returns, so the tests
# can check ``INDEX_LOG`` straight away. ``BackgroundTasks`` runs in the same
# process, so use a real queue (Celery, arq, SQS) for work that must survive
# a crash.
#
# TODO: implement this task (see the spec above)


# ---------------------------------------------------------------------------
# Task 6: concurrent async calls
# ---------------------------------------------------------------------------
# ``GET /enrich?id=1&id=2&id=9`` looks up every id with ``fetch_metadata``
# *concurrently*. Use ``asyncio.gather`` or an ``asyncio.TaskGroup``, not a
# sequential ``for`` loop with ``await``. With 3 ids the calls overlap, so
# ``FETCH_STATS["max_in_flight"]`` reaches 3.
#
# * Take ``ids: Annotated[list[int], Query(alias="id", min_length=1)]``.
# * Return ``{"items": [<found metadata, in request order>], "missing": [<ids that returned None>]}``.
#
# TODO: implement this task (see the spec above)


# ---------------------------------------------------------------------------
# Task 7: a streamed upload
# ---------------------------------------------------------------------------
# ``POST /files/stats`` receives a file as the raw request body (no
# multipart; see the README) and reports on it without holding it all in
# memory.
#
# * The ``Content-Type`` header must start with ``"text/"``. Otherwise raise
#   ``415`` with ``detail="Only text/* uploads are supported"``.
# * Read the body chunk by chunk with ``async for chunk in request.stream()``.
#   Count the bytes and the ``b"\n"`` characters. Once the total passes
#   ``MAX_UPLOAD_BYTES``, raise ``413`` with
#   ``detail=f"Upload exceeds {MAX_UPLOAD_BYTES} bytes"`` straight away.
# * An empty body: ``400`` with ``detail="Empty upload"``.
# * ``lines`` is the number of newlines, plus 1 if the last byte is not a
#   newline (``b"a\nb"`` has 2 lines, and so does ``b"a\nb\n"``).
# * The filename comes from the ``X-Filename`` header (default ``"upload.txt"``).
#
# Return ``{"filename": ..., "size_bytes": ..., "lines": ...}``.
#
# TODO: implement this task (see the spec above)


# ---------------------------------------------------------------------------
# Task 8: a WebSocket chat channel
# ---------------------------------------------------------------------------
# ``WS /ws/chat?token=...`` with a small JSON protocol:
#
# * If the ``token`` query parameter is not ``WS_TOKEN``, close with code
#   ``1008`` (``status.WS_1008_POLICY_VIOLATION``) *without* accepting.
#   Declare ``token: str | None = None`` as a function parameter, just like
#   in HTTP routes.
# * Otherwise ``accept()`` and loop over ``await websocket.receive_json()``:
#   * ``{"type": "message", "text": t}``: reply ``{"type": "echo", "text": t, "n": <messages so far>}``,
#     where ``n`` counts message frames on this connection, starting at 1.
#   * ``{"type": "ping"}``: reply ``{"type": "pong"}``.
#   * ``{"type": "bye"}``: close with code ``1000`` and stop.
#   * any other type: reply ``{"type": "error", "detail": "unknown message type"}`` and keep going.
# * If the client disconnects, ``receive_json`` raises ``WebSocketDisconnect``.
#   Catch it and return quietly.
#
# TODO: implement this task (see the spec above)


def create_app() -> FastAPI:
    """Build the application (given)."""
    app = FastAPI(title="Streaming and background work")
    app.include_router(router)
    return app
