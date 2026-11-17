# 1.8 asyncio

An async FastAPI service spends most of its time waiting: on the database,
the LLM provider, the vector store. `asyncio` lets one process wait on
thousands of such calls at once, but only if you know how to start them
concurrently, bound them, time them out, cancel them, and keep blocking code
off the event loop. This exercise covers those everyday patterns.

## Concepts

| Tool | Use it for |
|------|------------|
| `await asyncio.gather(*coros)` | run awaitables concurrently; results in argument order |
| `gather(..., return_exceptions=True)` | collect failures instead of failing on the first one |
| `asyncio.Semaphore(n)` | at most *n* operations in flight (rate limits, connection limits) |
| `async with asyncio.timeout(s)` | cancel a block that takes too long; raises `TimeoutError` |
| `asyncio.TaskGroup` | structured concurrency: one failure cancels the siblings, errors arrive as an `ExceptionGroup` |
| async generator (`async def` + `yield`) | stream items you fetch asynchronously (pages, LLM tokens) |
| `contextlib.aclosing` | close an async generator deterministically after `break` |
| `__aenter__` / `__aexit__`, `@asynccontextmanager` | async setup/teardown (pools, sessions, transactions) |
| `asyncio.Queue(maxsize=n)` | producer/consumer pipelines with backpressure |
| `asyncio.to_thread(func, ...)` | run blocking sync code without freezing the loop |

Three rules that prevent most asyncio bugs:

1. A coroutine does nothing until it is awaited or wrapped in a task.
   `fetch(x)` without `await` just creates an object (and a "never awaited"
   warning).
2. Never call blocking functions (`time.sleep`, `requests.get`, a sync DB
   driver) directly in a coroutine. Use `await asyncio.sleep`, an async
   client, or `asyncio.to_thread`.
3. Do not swallow `asyncio.CancelledError`. Catch it only to clean up, then
   re-raise.

## Tasks

All tasks are in [`exercise.py`](exercise.py).

| # | Task | What you practise |
|---|------|-------------------|
| 1 | `fetch_all` | `asyncio.gather`, concurrency vs. sequential awaits |
| 2 | `fetch_all_settled` | `return_exceptions=True`, partial failure |
| 3 | `map_concurrently` | `asyncio.Semaphore`, bounded concurrency |
| 4 | `call_with_timeout` | `asyncio.timeout`, cancellation, fallbacks |
| 5 | `load_all` | `asyncio.TaskGroup`, `except*`, sibling cancellation |
| 6 | `paginate`, `take` | async generators, async comprehensions, `aclosing` |
| 7 | `ConnectionPool` | `__aenter__`/`__aexit__`, `@asynccontextmanager`, `asyncio.Queue` as a pool |
| 8 | `run_workers` | producer/consumer, bounded `Queue`, `task_done`/`join`, cancelling workers |
| 9 | `run_blocking` | `asyncio.to_thread`, keeping the loop responsive |

## Run the tests

`pytest-asyncio` is configured with `asyncio_mode = "auto"`, so every
`async def test_...` runs in an event loop automatically.

```bash
uv run pytest m01_python_core/e08_asyncio
uv run pytest m01_python_core/e08_asyncio -k Task5   # one task only
```

## Further reading

- [asyncio: coroutines and tasks (gather, TaskGroup, timeout, to_thread)](https://docs.python.org/3/library/asyncio-task.html)
- [asyncio queues](https://docs.python.org/3/library/asyncio-queue.html)
- [Developing with asyncio (debug mode, blocking calls)](https://docs.python.org/3/library/asyncio-dev.html)
