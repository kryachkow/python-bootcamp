# m03 FastAPI

This theme builds the HTTP layer of a modern Python backend with FastAPI.
You start with routing and request/response models. Then you move on to
dependency injection, the application shell every service needs (error
envelopes, middleware, lifespan, CORS), a full CRUD resource on SQLAlchemy,
and the streaming features an LLM backend depends on: SSE token streams,
background jobs, concurrent async calls, uploads, and WebSockets. Every
exercise runs in process through FastAPI's `TestClient`, so you need no
server, no network, and no API keys.

## Prerequisites

- Comfortable with Pydantic v2 models, `Field` constraints, and
  `model_dump` (theme [`m02_pydantic`](../m02_pydantic)).
- Basic `async`/`await`. Exercise 3.5 uses the SQLAlchemy 2.x ORM but
  explains what it needs.

## Exercises

| # | Exercise | Topics |
|---|----------|--------|
| 3.1 | [Routing basics](e01_routing_basics) | typed and enum path parameters, query parameters and lists, status codes, `APIRouter` prefix and tags, route order pitfalls |
| 3.2 | [Request and response models](e02_request_and_response_models) | body models, `response_model` filtering, `201`/`409`/`422`, `Path`/`Query` constraints, `exclude_none`, nested chat models |
| 3.3 | [Dependencies](e03_dependencies) | function, class, and `yield` dependencies, API-key auth, sub-dependencies, router-level dependencies, `dependency_overrides` |
| 3.4 | [Errors, middleware, lifespan](e04_errors_middleware_lifespan) | `HTTPException` headers, domain exception handlers, custom `422`, catch-all `500`, request-ID middleware, lifespan, CORS |
| 3.5 | [CRUD with SQLAlchemy](e05_crud_with_sqlalchemy) | session dependency, create/list/read/patch/delete, pagination and filters, `exclude_unset`, `IntegrityError` → `409` |
| 3.6 | [Streaming and background work](e06_streaming_and_background) | `StreamingResponse`, Server-Sent Events, `EventSourceResponse`, `BackgroundTasks`, `asyncio.gather`, streamed uploads, WebSockets |

## Recommended order

Work through them in order. 3.1 and 3.2 are the basics that every later
exercise assumes. 3.3 (dependencies) comes before 3.5, whose session handling
is a `yield` dependency. 3.4 and 3.6 are independent of each other, so you
can do either one after 3.3.

## Running

```bash
uv run pytest m03_fastapi                          # the whole theme
uv run pytest m03_fastapi/e03_dependencies -k Task4
```

## Notes

- No special setup. Each test builds a fresh app with `create_app()`. The
  SQLAlchemy exercise uses an in-memory SQLite database per test.
- `UploadFile`/`Form` need the extra `python-multipart` package, which this
  repo does not install. Exercise 3.6 shows a streamed raw-body upload instead
  and explains the multipart variant in its README.
- Async SQLAlchemy needs `greenlet` (the `sqlalchemy[asyncio]` extra), which
  is not installed. Exercise 3.5 uses the sync ORM and shows the async
  equivalent of each call side by side.
