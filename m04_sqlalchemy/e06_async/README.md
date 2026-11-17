# 4.6 Async SQLAlchemy

`AsyncEngine` and `AsyncSession` wrap the same Core and ORM you used in the
previous exercises; you `await` every call that can do I/O. The catch is lazy
loading: in async code an attribute access cannot await, so touching an
unloaded relationship raises `MissingGreenlet`. You load what you need up
front, keep objects readable after commit, and give every concurrent task its
own session. This is the data layer of an async FastAPI service.

## Concepts

| Sync | Async |
|------|-------|
| `create_engine("sqlite:///x.db")` | `create_async_engine("sqlite+aiosqlite:///x.db")` |
| `sessionmaker(engine)` | `async_sessionmaker(engine, expire_on_commit=False)` |
| `with Session() as s:` | `async with factory() as s:` |
| `s.execute / scalars / scalar / get / commit` | the same names, `await`-ed |
| `s.delete(obj)` | `await s.delete(obj)` (`s.add(obj)` stays sync) |
| `metadata.create_all(conn)` | `await conn.run_sync(metadata.create_all)` |
| lazy load on attribute access | `MissingGreenlet`: use `selectinload` or `await obj.awaitable_attrs.x` |
| iterate a large result | `await s.stream_scalars(stmt)` + `async for` |
| one session per thread | one session per task; never share an `AsyncSession` in `asyncio.gather` |

## Tasks

All tasks are in [`exercise.py`](exercise.py). The models are given.

| # | Task | What you practise |
|---|------|-------------------|
| 1 | `make_session_factory` | `async_sessionmaker`, `expire_on_commit=False` |
| 2 | `init_models` | `engine.begin()`, `run_sync(create_all)` |
| 3 | `create_conversation` | async create and commit |
| 4 | `get_conversation` | `selectinload` instead of lazy loading (`MissingGreenlet`) |
| 5 | `add_message` | adding a child without loading the collection |
| 6 | `conversation_summaries` | aggregate query with `await session.execute` |
| 7 | `delete_conversation` | `await session.delete`, cascades |
| 8 | `fetch_titles_concurrently` | `asyncio.gather` with one session per task |
| 9 | `stream_contents` | `stream_scalars`, async generators |

## Run the tests

```bash
uv run pytest m04_sqlalchemy/e06_async
uv run pytest m04_sqlalchemy/e06_async -k Task4   # one task only
```

The async tests use pytest-asyncio in `auto` mode (configured in
`pyproject.toml`), so `async def test_...` functions and async fixtures just
work. SQLAlchemy 2.1 no longer installs `greenlet` automatically; the async
extension needs it, so the project depends on `sqlalchemy[asyncio]`.

## Further reading

- [Asynchronous I/O (asyncio) extension](https://docs.sqlalchemy.org/en/21/orm/extensions/asyncio.html)
- [Preventing implicit I/O when using AsyncSession](https://docs.sqlalchemy.org/en/21/orm/extensions/asyncio.html#asyncio-orm-avoid-lazyloads)
