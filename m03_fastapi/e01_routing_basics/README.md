# 3.1 Routing basics

Every FastAPI feature starts with a path operation: a decorator, a path, and
a function whose type hints tell FastAPI where each parameter comes from and
how to validate it. This exercise covers the routing rules you rely on every
day, plus a few that cause bugs, such as declaration order and list query
parameters.

## Concepts

| Declaration | FastAPI reads it as |
|-------------|---------------------|
| `def f(item_id: int)` with `"/items/{item_id}"` | path parameter, converted to `int`; bad input gives `422` |
| `"/files/{file_path:path}"` | path parameter that may contain `/` |
| `provider: Provider` (a `StrEnum`) | only the enum values are accepted, and they are listed in OpenAPI |
| `q: str \| None = None`, `limit: int = 10` | optional query parameters with defaults |
| `tags: Annotated[list[str], Query(alias="tag")]` | repeated `?tag=a&tag=b`. Without `Query()`, a `list` parameter is read from the body |
| `status_code=status.HTTP_204_NO_CONTENT` | the default status for the route |
| `APIRouter(prefix="/users", tags=["users"])` | a group of routes that you include with `app.include_router(...)`. Routers can be nested |

**Order matters.** Starlette tries routes in the order they were added. If
`/users/{user_id}` comes before `/users/me`, the request `/users/me` matches
the first route and fails int validation with `422`. Declare fixed paths
before parameterised ones.

## Tasks

All tasks are in [`exercise.py`](exercise.py). The tests build the app with
`create_app()` and call it through `TestClient`. A route you have not written
yet returns `404`.

| # | Task | What you practise |
|---|------|-------------------|
| 1 | `GET /items/{item_id}`, `GET /files/{file_path:path}` | typed path parameters, the `:path` converter |
| 2 | `GET /providers/{provider}` | enum path parameters |
| 3 | `GET /documents` | optional query parameters, defaults, `bool` parsing, paging |
| 4 | `GET /tags/match` | `list[str]` query parameters, `alias`, `Literal` |
| 5 | `POST /reindex`, `DELETE /documents/{doc_id}` | `202` / `204` / `404`, `HTTPException` |
| 6 | `users_router` | `APIRouter` prefix and tags, the `/me` vs `/{id}` order pitfall |
| 7 | `/health`, `/api/v1/...` | `include_in_schema=False`, nested routers for API versions |

## Run the tests

```bash
uv run pytest m03_fastapi/e01_routing_basics
uv run pytest m03_fastapi/e01_routing_basics -k Task6   # one task only
```

## Further reading

- [Path parameters](https://fastapi.tiangolo.com/tutorial/path-params/) and [query parameters](https://fastapi.tiangolo.com/tutorial/query-params/)
- [Bigger applications: multiple files and `APIRouter`](https://fastapi.tiangolo.com/tutorial/bigger-applications/)
