import asyncio
import threading
import time

import pytest

from m01_python_core.e08_asyncio.exercise import (
    ConnectionPool,
    LoaderError,
    call_with_timeout,
    fetch_all,
    fetch_all_settled,
    load_all,
    map_concurrently,
    paginate,
    run_blocking,
    run_workers,
    take,
)


class Probe:
    """Counts how many calls are in flight at once and in which order they finish."""

    def __init__(self, delays=None, default_delay=0.01):
        self.delays = delays or {}
        self.default_delay = default_delay
        self.current = 0
        self.max_seen = 0
        self.finished = []

    async def __call__(self, key):
        self.current += 1
        self.max_seen = max(self.max_seen, self.current)
        try:
            await asyncio.sleep(self.delays.get(key, self.default_delay))
            if isinstance(key, str) and key.startswith("bad"):
                raise ValueError(key)
            return f"result:{key}"
        finally:
            self.current -= 1
            self.finished.append(key)


class TestTask1Gather:
    async def test_runs_concurrently_and_keeps_order(self):
        probe = Probe(delays={"a": 0.03, "b": 0.01, "c": 0.02})
        assert await fetch_all(["a", "b", "c"], probe) == ["result:a", "result:b", "result:c"]
        assert probe.max_seen == 3
        assert probe.finished == ["b", "c", "a"]

    async def test_empty(self):
        assert await fetch_all([], Probe()) == []

    async def test_error_propagates(self):
        with pytest.raises(ValueError, match="bad1"):
            await fetch_all(["ok", "bad1"], Probe())


class TestTask2GatherSettled:
    async def test_splits_successes_and_failures(self):
        probe = Probe()
        ok, failed = await fetch_all_settled(["a", "bad1", "b", "bad2"], probe)
        assert ok == {"a": "result:a", "b": "result:b"}
        assert list(failed) == ["bad1", "bad2"]
        assert all(isinstance(e, ValueError) for e in failed.values())
        assert probe.max_seen == 4

    async def test_all_ok(self):
        ok, failed = await fetch_all_settled(iter(["x"]), Probe())
        assert (ok, failed) == ({"x": "result:x"}, {})


class TestTask3Semaphore:
    async def test_respects_limit_and_order(self):
        probe = Probe(default_delay=0.005)
        items = list(range(10))
        results = await map_concurrently(probe, items, limit=3)
        assert results == [f"result:{i}" for i in items]
        assert probe.max_seen == 3

    async def test_limit_larger_than_items(self):
        probe = Probe()
        assert await map_concurrently(probe, [1, 2], limit=10) == ["result:1", "result:2"]
        assert probe.max_seen == 2

    async def test_invalid_limit(self):
        with pytest.raises(ValueError):
            await map_concurrently(Probe(), [1], limit=0)


class TestTask4Timeout:
    async def test_fast_call_returns_result(self):
        async def fast():
            await asyncio.sleep(0)
            return "fresh"

        assert await call_with_timeout(fast, timeout=1, fallback="cached") == "fresh"

    async def test_slow_call_is_cancelled_and_falls_back(self):
        state = {"cancelled": False}

        async def slow():
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                state["cancelled"] = True
                raise
            return "never"

        start = time.perf_counter()
        assert await call_with_timeout(slow, timeout=0.02, fallback="cached") == "cached"
        assert state["cancelled"]
        assert time.perf_counter() - start < 1

    async def test_other_errors_propagate(self):
        async def broken():
            raise KeyError("x")

        with pytest.raises(KeyError):
            await call_with_timeout(broken, timeout=1, fallback=None)


class TestTask5TaskGroup:
    async def test_success_keeps_order(self):
        async def make(value, delay):
            await asyncio.sleep(delay)
            return value

        loaders = {"user": lambda: make("ann", 0.02), "orders": lambda: make([1, 2], 0.0), "stats": lambda: make(3, 0.01)}
        result = await load_all(loaders)
        assert result == {"user": "ann", "orders": [1, 2], "stats": 3}
        assert list(result) == ["user", "orders", "stats"]

    async def test_failure_cancels_siblings(self):
        state = {"slow_cancelled": False, "slow_finished": False}

        async def slow():
            try:
                await asyncio.sleep(5)
                state["slow_finished"] = True
            except asyncio.CancelledError:
                state["slow_cancelled"] = True
                raise

        async def bad():
            await asyncio.sleep(0.01)
            raise ConnectionError("db down")

        with pytest.raises(LoaderError) as info:
            await load_all({"slow": slow, "bad": bad})
        assert list(info.value.failed) == ["bad"]
        assert isinstance(info.value.failed["bad"], ConnectionError)
        assert isinstance(info.value.__cause__, ExceptionGroup)
        assert state == {"slow_cancelled": True, "slow_finished": False}

    async def test_empty(self):
        assert await load_all({}) == {}


class FakePagedApi:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    async def __call__(self, cursor):
        self.calls.append(cursor)
        await asyncio.sleep(0)
        return self.pages[cursor]


class TestTask6AsyncGenerators:
    async def test_paginate_with_async_comprehension(self):
        api = FakePagedApi({None: ([1, 2], "c1"), "c1": ([], "c2"), "c2": ([3], None)})
        assert [x async for x in paginate(api)] == [1, 2, 3]
        assert api.calls == [None, "c1", "c2"]

    async def test_paginate_is_lazy(self):
        api = FakePagedApi({None: ([1, 2], "c1"), "c1": ([3], None)})
        gen = paginate(api)
        assert api.calls == []
        assert await anext(gen) == 1
        assert await anext(gen) == 2
        assert api.calls == [None]
        await gen.aclose()

    async def test_take_stops_early_and_closes(self):
        state = {"pulled": 0, "closed": False}

        async def numbers():
            try:
                for i in range(100):
                    state["pulled"] += 1
                    yield i
            finally:
                state["closed"] = True

        gen = numbers()
        assert await take(gen, 3) == [0, 1, 2]
        assert state == {"pulled": 3, "closed": True}

    async def test_take_zero_and_short_source(self):
        api = FakePagedApi({None: ([1], None)})
        assert await take(paginate(api), 0) == []
        assert api.calls == []
        assert await take(paginate(api), 5) == [1]


class FakeConnection:
    def __init__(self, n):
        self.n = n
        self.closed = False

    async def close(self):
        await asyncio.sleep(0)
        self.closed = True


def connector():
    created = []

    async def connect():
        await asyncio.sleep(0)
        conn = FakeConnection(len(created))
        created.append(conn)
        return conn

    return connect, created


class TestTask7ConnectionPool:
    async def test_opens_and_closes_connections(self):
        connect, created = connector()
        async with ConnectionPool(connect, size=2) as pool:
            assert len(created) == 2
            async with pool.acquire() as conn:
                assert isinstance(conn, FakeConnection)
                assert pool.in_use == 1
            assert pool.in_use == 0
        assert all(c.closed for c in created)

    async def test_borrowers_wait_when_pool_is_exhausted(self):
        connect, _ = connector()
        peak = 0

        async with ConnectionPool(connect, size=2) as pool:

            async def job():
                nonlocal peak
                async with pool.acquire():
                    peak = max(peak, pool.in_use)
                    await asyncio.sleep(0.005)

            await asyncio.gather(*(job() for _ in range(6)))
            assert peak == 2
            assert pool.in_use == 0

    async def test_connection_returned_on_error(self):
        connect, _ = connector()
        async with ConnectionPool(connect, size=1) as pool:
            with pytest.raises(KeyError):
                async with pool.acquire():
                    raise KeyError
            assert pool.in_use == 0
            async with pool.acquire() as conn:
                assert conn.n == 0

    async def test_acquire_requires_open_pool(self):
        connect, created = connector()
        pool = ConnectionPool(connect, size=1)
        with pytest.raises(RuntimeError, match="not open"):
            async with pool.acquire():
                pass
        assert created == []


class TestTask8Workers:
    async def test_processes_all_in_order_with_n_workers(self):
        probe = Probe(default_delay=0.002)
        items = list(range(20))
        results = await run_workers(items, probe, workers=4, queue_size=2)
        assert results == [f"result:{i}" for i in items]
        assert probe.max_seen == 4

    async def test_errors_are_kept_in_place(self):
        results = await run_workers(["a", "bad1", "b"], Probe(), workers=2)
        assert results[0] == "result:a" and results[2] == "result:b"
        assert isinstance(results[1], ValueError)

    async def test_lazy_producer_with_backpressure(self):
        produced = []

        def source():
            for i in range(50):
                produced.append(i)
                yield i

        seen_backlog = []

        async def handle(item):
            seen_backlog.append(len(produced) - item)
            await asyncio.sleep(0)
            return item

        assert await run_workers(source(), handle, workers=1, queue_size=3) == list(range(50))
        assert max(seen_backlog) <= 5  # the producer never runs far ahead

    async def test_edge_cases(self):
        assert await run_workers([], Probe()) == []
        with pytest.raises(ValueError):
            await run_workers([1], Probe(), workers=0)


class TestTask9ToThread:
    async def test_runs_in_threads_concurrently(self):
        main = threading.get_ident()

        # All 4 calls must be inside `blocking` at the same time to pass the
        # barrier; run sequentially, the first wait() times out instead.
        barrier = threading.Barrier(4, timeout=2)

        def blocking(x):
            barrier.wait()
            return (x * 2, threading.get_ident())

        results = await run_blocking(blocking, [1, 2, 3, 4])
        assert [r for r, _ in results] == [2, 4, 6, 8]
        assert all(tid != main for _, tid in results)

    async def test_event_loop_stays_responsive(self):
        ticks = 0
        stop = asyncio.Event()

        async def ticker():
            nonlocal ticks
            while not stop.is_set():
                ticks += 1
                await asyncio.sleep(0.005)

        task = asyncio.create_task(ticker())
        await run_blocking(time.sleep, [0.05, 0.05])
        stop.set()
        await task
        assert ticks >= 3

    async def test_empty(self):
        assert await run_blocking(str, []) == []
