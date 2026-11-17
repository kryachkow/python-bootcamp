# 3.3 Dependencies

`Depends` is how FastAPI shares code between endpoints: parsing parameters,
opening a database session, authenticating a caller, checking permissions.
A dependency is any callable. FastAPI resolves its parameters the same way it
resolves an endpoint's, caches the result for the rest of the request, and
lets tests replace it through `app.dependency_overrides`. In this exercise,
the cross-cutting parts of a notes API all become dependencies.

## Concepts

| Pattern | Example |
|---------|---------|
| function dependency | `spec: Annotated[SortSpec, Depends(parse_sort)]` |
| class dependency | `paging: Annotated[Pagination, Depends()]`: the `__init__` parameters become query parameters |
| `yield` dependency | code before `yield` is setup, code after it is teardown. An exception from the endpoint is raised at the `yield` |
| sub-dependencies | `require_admin` → `get_current_user` → `get_api_key` → the `X-API-Key` header |
| `Annotated` alias | `CurrentUser = Annotated[User, Depends(get_current_user)]`, reused in every signature |
| router-level | `APIRouter(dependencies=[Depends(require_admin)])` guards every route on the router |
| per-request cache | a dependency needed twice in one request runs once (`use_cache=True` is the default) |
| overrides | `app.dependency_overrides[get_current_user] = lambda: fake_user` |

Return `401` when the caller is not authenticated (credentials are missing or
wrong) and `403` when the caller is authenticated but not allowed. Always
send a `WWW-Authenticate` header with a `401`.

## Tasks

All tasks are in [`exercise.py`](exercise.py). Each task is a dependency
plus the route that uses it.

| # | Task | What you practise |
|---|------|-------------------|
| 1 | `parse_sort` + `GET /notes` | a function dependency that validates and raises `400` |
| 2 | `Pagination` + `GET /notes/page` | a class-based dependency with `Query` constraints |
| 3 | `get_session` + `POST /notes` | a `yield` dependency with commit, rollback, and close |
| 4 | `get_api_key`, `get_current_user` + `GET /me` | header auth, `401` with `WWW-Authenticate`, sub-dependencies |
| 5 | `require_admin` + `DELETE /notes/{id}` | layering authorisation (`403`) on top of authentication (`401`) |
| 6 | `record_audit`, `admin_router` | router-level `dependencies=[...]`, side-effect-only dependencies |
| 7 | `override_user` | a test helper around `app.dependency_overrides` that restores state correctly |

## Run the tests

```bash
uv run pytest m03_fastapi/e03_dependencies
uv run pytest m03_fastapi/e03_dependencies -k Task3   # one task only
```

## Further reading

- [Dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/) and [dependencies with yield](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/)
- [Testing dependencies with overrides](https://fastapi.tiangolo.com/advanced/testing-dependencies/)
