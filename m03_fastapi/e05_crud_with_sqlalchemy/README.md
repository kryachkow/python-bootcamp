# 3.5 CRUD with SQLAlchemy

A complete resource, `/datasets`, with create, list (filters and
pagination), read, partial update, and delete, backed by the SQLAlchemy 2.x
ORM. It includes the production details that tutorials often skip: the
database enforces uniqueness, `PATCH` uses `exclude_unset`, and a `null` that
clears a field is handled differently from a missing field.

## Concepts

| Concern | Idiom |
|---------|-------|
| one session per request | a `yield` dependency: `with sessionmaker() as session: yield session` |
| engine lifecycle | create it in `lifespan`, `dispose()` at shutdown; keep the sessionmaker on `app.state` |
| in-memory SQLite shared across requests | `poolclass=StaticPool`, `check_same_thread=False` |
| ORM object → response | `DatasetOut` with `ConfigDict(from_attributes=True)` |
| uniqueness | the `UNIQUE` column plus `except IntegrityError: rollback(); 409`, with no SELECT-then-INSERT race |
| paging metadata | `select(func.count()).select_from(Dataset).where(*conditions)` |
| partial update | `payload.model_dump(exclude_unset=True)`, then `setattr` each field |
| "optional but not nullable" | `name: str = Field(default=None)`: a field you may leave out, but cannot set to `null` |

### Why sync SQLAlchemy here?

The async ORM (`AsyncSession`, `create_async_engine("sqlite+aiosqlite://")`)
needs the `greenlet` package. Since SQLAlchemy 2.1, `greenlet` is installed
only with the `sqlalchemy[asyncio]` extra, and this repo installs plain
`sqlalchemy` (`aiosqlite` is a dependency, `greenlet` is not). Without
`greenlet`, `import sqlalchemy.ext.asyncio` fails. So this exercise uses the
sync ORM. FastAPI runs plain `def` endpoints in a threadpool, which is why
the engine needs `check_same_thread=False`.

The FastAPI side (dependency, status codes, schemas) is the same either way.
Only the session calls change:

| sync (this exercise) | async (`AsyncSession`) |
|----------------------|------------------------|
| `def get_session(...)`: `with sm() as s: yield s` | `async def get_session(...)`: `async with sm() as s: yield s` |
| `session.get(Dataset, id)` | `await session.get(Dataset, id)` |
| `session.scalars(stmt)` / `session.scalar(stmt)` | `await session.scalars(stmt)` / `await session.scalar(stmt)` |
| `session.commit()` / `rollback()` | `await session.commit()` / `await session.rollback()` |
| `session.delete(obj)` | `await session.delete(obj)` |
| `session.add(obj)` | `session.add(obj)` (no `await`) |

With async, also keep `expire_on_commit=False`. Reading an expired attribute
outside an `await` raises `MissingGreenlet`. Theme `m04_sqlalchemy` covers the
ORM itself in depth.

## Tasks

All tasks are in [`exercise.py`](exercise.py). The ORM model, `lifespan`, and
`create_app` are given. Tasks 3-7 build on Tasks 1-2.

| # | Task | What you practise |
|---|------|-------------------|
| 1 | `DatasetCreate`, `DatasetUpdate`, `DatasetOut` | create, patch, and output schemas; `from_attributes`; optional vs nullable |
| 2 | `get_session` | a `yield` session dependency |
| 3 | `POST /datasets` | `201`, `IntegrityError` → rollback → `409` |
| 4 | `GET /datasets/{id}` | `session.get`, `404` |
| 5 | `GET /datasets` | filters, `icontains(autoescape=True)`, `limit`/`offset`, `total` count |
| 6 | `PATCH /datasets/{id}` | `exclude_unset` partial updates, `null` clearing a field, rename conflict |
| 7 | `DELETE /datasets/{id}` | `204`, `404` |

## Run the tests

```bash
uv run pytest m03_fastapi/e05_crud_with_sqlalchemy
uv run pytest m03_fastapi/e05_crud_with_sqlalchemy -k Task6   # one task only
```

## Further reading

- [FastAPI: SQL (relational) databases](https://fastapi.tiangolo.com/tutorial/sql-databases/)
- [SQLAlchemy 2.0 ORM querying guide](https://docs.sqlalchemy.org/en/20/orm/queryguide/index.html)
- [SQLAlchemy asyncio extension](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
