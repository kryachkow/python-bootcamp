# 3.4 Errors, middleware, and lifespan

Before a service has its first feature, it needs a shell: one error format
for every failure, a request ID on every response, shared clients created
at startup and closed at shutdown, and CORS for the browser. This exercise
builds that shell around a few given endpoints.

## Concepts

| Piece | Where it runs |
|-------|---------------|
| `HTTPException(status, detail, headers=...)` | raised in endpoints and dependencies; FastAPI's default handler renders `{"detail": ...}` |
| `app.add_exception_handler(DomainError, handler)` | `ExceptionMiddleware`. It maps your own exceptions, and their subclasses, to responses, so the service layer never imports FastAPI |
| `RequestValidationError` handler | replaces FastAPI's default `422` body |
| `Exception` handler | `ServerErrorMiddleware`, the outermost layer. It answers `500` and then re-raises |
| `app.middleware("http")` | wraps each request: `response = await call_next(request)` |
| `lifespan` async context manager | code before `yield` runs once at startup, code after it runs at shutdown. Put shared clients on `app.state` |
| `CORSMiddleware` | answers browser preflight `OPTIONS` requests and adds `Access-Control-*` headers |

Middleware order: each `add_middleware` call wraps the existing stack, so the
middleware added last runs first. `create_app` adds CORS last, which puts it
outside everything else, so even error responses get CORS headers.

The lifespan runs only while a `TestClient` is used as a context manager:

```python
with TestClient(create_app()) as client:   # startup runs here
    client.get("/...")
# shutdown runs here
```

> `@app.on_event("startup")` is deprecated. Use `lifespan`. The lifespan can
> also `yield {"llm": client}`, and Starlette then exposes the dict as
> `request.state.llm`. This exercise uses `app.state`, which you will see more
> often in existing code.

## Tasks

All tasks are in [`exercise.py`](exercise.py).

| # | Task | What you practise |
|---|------|-------------------|
| 1 | `GET /protected` | `HTTPException` with `WWW-Authenticate` |
| 2 | `domain_error_handler` | a domain exception hierarchy mapped to a JSON error envelope, with forwarded headers (`Retry-After`) |
| 3 | `validation_error_handler` | reformatting `RequestValidationError` into the same envelope |
| 4 | `unhandled_error_handler` | a catch-all `500` that does not leak internals |
| 5 | `request_context_middleware` | `X-Request-ID` (propagated or generated, and validated), `X-Process-Time`, `request.state` |
| 6 | `lifespan` | startup and shutdown, `app.state`, closing clients in `finally` |
| 7 | `configure_cors` | allowed origins, credentials, exposed headers, preflight caching |

## Run the tests

```bash
uv run pytest m03_fastapi/e04_errors_middleware_lifespan
uv run pytest m03_fastapi/e04_errors_middleware_lifespan -k Task5   # one task only
```

## Further reading

- [Handling errors](https://fastapi.tiangolo.com/tutorial/handling-errors/)
- [Lifespan events](https://fastapi.tiangolo.com/advanced/events/)
- [CORS](https://fastapi.tiangolo.com/tutorial/cors/)
