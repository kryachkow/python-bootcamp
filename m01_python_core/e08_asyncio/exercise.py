"""Exercise 1.8: asyncio for backend developers.

Implement every coroutine and class below. Each one says what it must do in
its docstring. The tests use tiny sleeps and check *ordering* and *maximum
concurrency*, not exact timings. Run them with:

    uv run pytest m01_python_core/e08_asyncio
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable, Mapping
from contextlib import aclosing, asynccontextmanager
from types import TracebackType
from typing import Any, Self


# ---------------------------------------------------------------------------
# Task 1: run coroutines concurrently with gather
# ---------------------------------------------------------------------------
async def fetch_all[T](keys: Iterable[str], fetch: Callable[[str], Awaitable[T]]) -> list[T]:
    """Call ``fetch(key)`` for every key **concurrently** and return the results in key order.

    * All calls run at the same time. Do not ``await`` them one by one in a
      loop: that would take the sum of their durations instead of the
      longest one.
    * The result order matches ``keys``, whatever order the calls finish in.
    * If any call raises, the exception propagates.
    * No keys: return ``[]``.

    Hint: ``asyncio.gather(*coros)`` returns a list in argument order.
    """
    return list(await asyncio.gather(*(fetch(k) for k in keys)))


# ---------------------------------------------------------------------------
# Task 2: collect failures instead of failing fast
# ---------------------------------------------------------------------------
async def fetch_all_settled[T](
    keys: Iterable[str], fetch: Callable[[str], Awaitable[T]]
) -> tuple[dict[str, T], dict[str, Exception]]:
    """Like ``fetch_all``, but one failure does not stop the others.

    Return ``(successes, failures)``: ``{key: result}`` and
    ``{key: exception}``. Both dicts keep the order of ``keys``. Keys are
    unique.

    Use this when one bad tool or retriever should not sink the whole LLM
    request.

    Hint: ``asyncio.gather(..., return_exceptions=True)`` puts exceptions
    in the result list instead of raising.
    """
    keys = list(keys)
    results = await asyncio.gather(*(fetch(k) for k in keys), return_exceptions=True)
    successes: dict[str, T] = {}
    failures: dict[str, Exception] = {}
    for key, result in zip(keys, results, strict=True):
        if isinstance(result, Exception):
            failures[key] = result
        elif isinstance(result, BaseException):
            raise result
        else:
            successes[key] = result
    return successes, failures


# ---------------------------------------------------------------------------
# Task 3: limit concurrency with a Semaphore
# ---------------------------------------------------------------------------
async def map_concurrently[T, R](func: Callable[[T], Awaitable[R]], items: Iterable[T], *, limit: int) -> list[R]:
    """Apply ``func`` to every item, with at most ``limit`` calls running at once.

    * Return the results in input order.
    * Raise ``ValueError`` if ``limit < 1``.
    * A rate-limited API (an LLM provider, for example) returns HTTP 429 if
      you send 500 requests at once. A semaphore keeps you under the limit
      and still runs ``limit`` calls in parallel.

    Hint: create one ``asyncio.Semaphore(limit)``, wrap each call in
    ``async with sem:``, then ``gather`` the wrapped calls.
    """
    if limit < 1:
        raise ValueError("limit must be >= 1")
    sem = asyncio.Semaphore(limit)

    async def run(item: T) -> R:
        async with sem:
            return await func(item)

    return list(await asyncio.gather(*(run(i) for i in items)))


# ---------------------------------------------------------------------------
# Task 4: timeouts
# ---------------------------------------------------------------------------
async def call_with_timeout[T](func: Callable[[], Awaitable[T]], *, timeout: float, fallback: T) -> T:
    """Await ``func()``. If it takes longer than ``timeout`` seconds, return ``fallback``.

    * Use ``async with asyncio.timeout(timeout):`` (3.11+). When the time is
      up, the inner coroutine is **cancelled** (it sees ``CancelledError``)
      and the ``async with`` raises ``TimeoutError``. Catch that and return
      ``fallback``.
    * Other exceptions from ``func`` propagate unchanged.
    """
    try:
        async with asyncio.timeout(timeout):
            return await func()
    except TimeoutError:
        return fallback


# ---------------------------------------------------------------------------
# Task 5: structured concurrency with TaskGroup
# ---------------------------------------------------------------------------
class LoaderError(Exception):
    """Given: raised by ``load_all`` when loaders fail.

    ``failed`` maps each failed loader name to its exception.
    """

    def __init__(self, failed: dict[str, Exception]) -> None:
        super().__init__(f"loader(s) failed: {', '.join(failed)}")
        self.failed = failed


async def load_all(loaders: Mapping[str, Callable[[], Awaitable[Any]]]) -> dict[str, Any]:
    """Run all loaders concurrently in an ``asyncio.TaskGroup``, as a dashboard endpoint would.

    * Success: return ``{name: result}`` in the order of ``loaders``.
    * If a loader raises an ``Exception``, the TaskGroup **cancels** the
      loaders still running, waits for them, and raises an
      ``ExceptionGroup``. Catch it with ``except* Exception as eg`` and
      raise ``LoaderError(failed)`` **from** ``eg``. ``failed`` maps the name
      of every loader that *raised* to its exception. Loaders that were only
      cancelled are not failures.

    Unlike ``gather``, a TaskGroup never leaves orphan tasks running after
    an error.

    Hint: wrap each loader in a small coroutine that records
    ``failed[name] = exc`` before re-raising.
    """
    failed: dict[str, Exception] = {}

    async def run(name: str, loader: Callable[[], Awaitable[Any]]) -> Any:
        try:
            return await loader()
        except Exception as exc:
            failed[name] = exc
            raise

    try:
        async with asyncio.TaskGroup() as tg:
            tasks = {name: tg.create_task(run(name, loader)) for name, loader in loaders.items()}
    except* Exception as eg:
        raise LoaderError(failed) from eg
    return {name: task.result() for name, task in tasks.items()}


# ---------------------------------------------------------------------------
# Task 6: async generators
# ---------------------------------------------------------------------------
async def paginate[T](fetch_page: Callable[[str | None], Awaitable[tuple[list[T], str | None]]]) -> AsyncIterator[T]:
    """Async generator: yield every item of a cursor-paginated async API.

    ``await fetch_page(cursor)`` returns ``(items, next_cursor)``. Start with
    ``None`` and stop after a page whose ``next_cursor`` is ``None``. Fetch
    a page only when the consumer needs its items (lazily).

    Consumers use ``async for item in paginate(...)`` or an async
    comprehension: ``[x async for x in paginate(...)]``.
    """
    cursor: str | None = None
    while True:
        items, cursor = await fetch_page(cursor)
        for item in items:
            yield item
        if cursor is None:
            return


async def take[T](source: AsyncIterator[T], n: int) -> list[T]:
    """Return the first ``n`` items of an async generator and then **close** it.

    * Stop pulling after ``n`` items (``n <= 0`` returns ``[]`` without
      pulling anything).
    * Close ``source``, even when you stop early, so its ``finally`` blocks
      run *now* (an HTTP stream gets released, for example). Breaking out of
      ``async for`` does **not** close an async generator by itself.

    Hint: ``async with contextlib.aclosing(source):``.
    """
    result: list[T] = []
    async with aclosing(source):  # type: ignore[type-var]
        if n <= 0:
            return result
        async for item in source:
            result.append(item)
            if len(result) >= n:
                break
    return result


# ---------------------------------------------------------------------------
# Task 7: async context managers (a connection pool)
# ---------------------------------------------------------------------------
class ConnectionPool:
    """A fixed-size pool of connections, like the one behind SQLAlchemy's async engine.

    Usage::

        async with ConnectionPool(connect, size=2) as pool:
            async with pool.acquire() as conn:
                ...

    * ``connect`` is an async factory: ``conn = await connect()``. Every
      connection has an ``async close()`` method.
    * ``__aenter__``: open ``size`` connections, put them in an
      ``asyncio.Queue``, mark the pool open, and return ``self``.
    * ``__aexit__``: ``await conn.close()`` for every connection the pool
      opened, mark the pool closed, and do not suppress exceptions.
    * ``acquire()`` is an ``@asynccontextmanager``. Raise ``RuntimeError`` if
      the pool is not open. Otherwise take a connection from the queue,
      waiting if all of them are borrowed, yield it, and **always** put it
      back, also when the body raised.
    * ``in_use`` (property): how many connections are borrowed right now.
    """

    def __init__(self, connect: Callable[[], Awaitable[Any]], *, size: int = 5) -> None:
        self._connect = connect
        self.size = size
        self._idle: asyncio.Queue[Any] = asyncio.Queue()
        self._all: list[Any] = []
        self._open = False

    async def __aenter__(self) -> Self:
        for _ in range(self.size):
            conn = await self._connect()
            self._all.append(conn)
            self._idle.put_nowait(conn)
        self._open = True
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._open = False
        for conn in self._all:
            await conn.close()

    @property
    def in_use(self) -> int:
        return len(self._all) - self._idle.qsize()

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[Any]:
        if not self._open:
            raise RuntimeError("pool is not open")
        conn = await self._idle.get()
        try:
            yield conn
        finally:
            self._idle.put_nowait(conn)


# ---------------------------------------------------------------------------
# Task 8: producer / consumer with asyncio.Queue
# ---------------------------------------------------------------------------
async def run_workers[T, R](
    items: Iterable[T],
    handle: Callable[[T], Awaitable[R]],
    *,
    workers: int = 3,
    queue_size: int = 10,
) -> list[R | Exception]:
    """Process ``items`` with a fixed number of worker tasks reading from a bounded queue.

    * Raise ``ValueError`` if ``workers < 1``.
    * Use ``asyncio.Queue(maxsize=queue_size)``. A **producer** puts
      ``(index, item)`` pairs into it. When the queue is full, ``await
      queue.put`` waits (backpressure), so a huge input is never all in
      memory at once.
    * Start ``workers`` **consumer** tasks. Each one loops: get a pair,
      ``await handle(item)``, store the result (or the ``Exception`` it
      raised) under its index, and call ``queue.task_done()`` in a
      ``finally``.
    * When the producer has finished and ``await queue.join()`` returns,
      cancel the workers and wait for them to finish.
    * Return the results in input order. A failed item has its exception in
      its place, and the other items are still processed.

    This is the shape of an ingestion job: read documents, embed them with
    N workers, write the vectors.
    """
    if workers < 1:
        raise ValueError("workers must be >= 1")
    queue: asyncio.Queue[tuple[int, T]] = asyncio.Queue(maxsize=queue_size)
    results: dict[int, R | Exception] = {}

    async def produce() -> None:
        for pair in enumerate(items):
            await queue.put(pair)

    async def consume() -> None:
        while True:
            index, item = await queue.get()
            try:
                results[index] = await handle(item)
            except Exception as exc:
                results[index] = exc
            finally:
                queue.task_done()

    consumers = [asyncio.create_task(consume()) for _ in range(workers)]
    try:
        await produce()
        await queue.join()
    finally:
        for task in consumers:
            task.cancel()
        await asyncio.gather(*consumers, return_exceptions=True)
    return [results[i] for i in range(len(results))]


# ---------------------------------------------------------------------------
# Task 9: blocking code without blocking the event loop
# ---------------------------------------------------------------------------
async def run_blocking[T, R](func: Callable[[T], R], items: Iterable[T]) -> list[R]:
    """Run a **blocking** function (file I/O, a sync SDK, CPU-light parsing) for each item.

    * Calling ``func`` directly inside a coroutine freezes the whole event
      loop: no other request is served until it returns. Run each call in a
      worker thread with ``asyncio.to_thread(func, item)`` instead.
    * The calls run concurrently. Return the results in input order.
    """
    return list(await asyncio.gather(*(asyncio.to_thread(func, item) for item in items)))
