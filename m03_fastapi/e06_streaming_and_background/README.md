# 3.6 Streaming, background tasks, and WebSockets

An LLM backend rarely sends one JSON response and stops. It streams tokens
as they arrive, kicks off indexing after it has answered, calls several
services at once, accepts uploads, and keeps chat sockets open. This exercise
covers each of these with deterministic fakes.

## Concepts

| Need | Tool |
|------|------|
| send a body in chunks | `StreamingResponse(async_gen(), media_type=...)` |
| token streaming to browsers | Server-Sent Events: `text/event-stream`, events of `field: value` lines, each ended by a blank line |
| SSE without hand-formatting | `response_class=EventSourceResponse` and `yield ServerSentEvent(...)` (built into recent FastAPI) |
| read a stream in tests | `with client.stream("GET", url) as r: r.iter_lines()`, or `httpx.AsyncClient(transport=ASGITransport(app))` |
| work after the response | `background_tasks.add_task(func, *args)` (sync or async functions) |
| fan out to many async calls | `await asyncio.gather(*coros)` or `asyncio.TaskGroup` |
| large uploads | `async for chunk in request.stream()`, which never loads the whole body |
| two-way channel | `@router.websocket(...)`, `accept()` / `receive_json()` / `send_json()` / `close(code)` |

An SSE event on the wire:

```text
id: 3
event: token
data: {"token": " world"}

```

> **`UploadFile` and multipart.** `UploadFile` and `Form` need the
> `python-multipart` package, which is not a dependency of this repo (FastAPI
> raises an error at import time without it). Task 7 reads the raw request
> body instead. That is also the better choice for large single-file uploads
> (`PUT`/`POST` with `Content-Type: text/plain`). With `python-multipart`
> installed, the multipart version is
> `async def upload(file: UploadFile): data = await file.read()`, and the
> same size and line logic applies.

`BackgroundTasks` run in the same process, after the response is sent. If
the process dies, the work is lost. Use them for best-effort work such as
notifications or cache warming, and use a real queue for anything that must
happen.

## Tasks

All tasks are in [`exercise.py`](exercise.py).

| # | Task | What you practise |
|---|------|-------------------|
| 1 | `GET /count` | `StreamingResponse` with an async generator; `client.stream`; `httpx.AsyncClient` + `ASGITransport` |
| 2 | `format_sse` | the SSE wire format (`id`, `event`, multi-line `data`) |
| 3 | `POST /chat/stream` | hand-rolled SSE token streaming, `[DONE]` sentinel, anti-buffering headers |
| 4 | `GET /chat/events` | FastAPI's `EventSourceResponse` + `ServerSentEvent` |
| 5 | `index_document`, `notify_indexed`, `POST /documents` | `BackgroundTasks` with sync and async jobs, `202 Accepted` |
| 6 | `GET /enrich` | concurrent awaits with `asyncio.gather`, keeping request order |
| 7 | `POST /files/stats` | streamed raw-body upload, `413` / `415` / `400` |
| 8 | `WS /ws/chat` | WebSocket auth (close `1008`), a JSON protocol, normal close `1000` |

## Run the tests

```bash
uv run pytest m03_fastapi/e06_streaming_and_background
uv run pytest m03_fastapi/e06_streaming_and_background -k Task3   # one task only
```

## Further reading

- [Custom responses: `StreamingResponse`](https://fastapi.tiangolo.com/advanced/custom-response/) and the [SSE spec](https://html.spec.whatwg.org/multipage/server-sent-events.html)
- [Background tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/)
- [WebSockets](https://fastapi.tiangolo.com/advanced/websockets/)
