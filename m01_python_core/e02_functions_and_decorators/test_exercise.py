import functools
import json
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

import pytest

from m01_python_core.e02_functions_and_decorators.exercise import (
    build_url,
    compose,
    count_calls,
    make_alert_sender,
    make_counter,
    memoize,
    retry,
    send_notification,
    to_jsonable,
)


class TestTask1BuildUrl:
    def test_full_example(self):
        url = build_url("api.example.com/", "/v1/", "users", 42, page=2, q="hello world")
        assert url == "https://api.example.com/v1/users/42?page=2&q=hello+world"

    def test_insecure_and_none_query_values(self):
        assert build_url("localhost:8000", secure=False, debug=None) == "http://localhost:8000"

    def test_empty_segments_are_skipped(self):
        assert build_url("h", "", "/", "a") == "https://h/a"

    def test_base_is_positional_only_so_it_can_be_a_query_key(self):
        assert build_url("h", base="x") == "https://h?base=x"
        with pytest.raises(TypeError):
            build_url(base="h")

    def test_secure_is_keyword_only(self):
        # a bool passed positionally is just another path segment
        assert build_url("h", False) == "https://h/False"


class TestTask2MakeCounter:
    def test_counts_from_start_by_step(self):
        next_id = make_counter(100, step=10)
        assert [next_id(), next_id(), next_id()] == [100, 110, 120]

    def test_defaults(self):
        counter = make_counter()
        assert [counter(), counter()] == [0, 1]

    def test_counters_are_independent(self):
        a, b = make_counter(), make_counter()
        a()
        a()
        assert b() == 0
        assert a() == 2

    def test_negative_step(self):
        countdown = make_counter(3, step=-1)
        assert [countdown() for _ in range(4)] == [3, 2, 1, 0]

    def test_zero_step_raises(self):
        with pytest.raises(ValueError):
            make_counter(step=0)


class TestTask3Compose:
    def test_right_to_left(self):
        assert compose(lambda x: x + 1, lambda x: x * 10)(2) == 21

    def test_slugify_example(self):
        assert compose("-".join, str.split, str.lower)("Hello Big World") == "hello-big-world"

    def test_no_functions_is_identity(self):
        sentinel = object()
        assert compose()(sentinel) is sentinel

    def test_non_callable_raises_eagerly(self):
        with pytest.raises(TypeError):
            compose(str.lower, "not a function")


class TestTask4MakeAlertSender:
    def test_binds_channel_and_keywords(self):
        assert make_alert_sender("ops")("disk full") == "[ops]! disk full (retries=3)"

    def test_returns_a_real_partial(self):
        sender = make_alert_sender("ops")
        assert isinstance(sender, functools.partial)
        assert sender.func is send_notification
        assert sender.args == ("ops",)
        assert sender.keywords == {"urgent": True, "retries": 3}

    def test_keywords_can_be_overridden(self):
        assert make_alert_sender("db")("slow query", retries=0) == "[db]! slow query (retries=0)"


class TestTask5CountCalls:
    def test_counts_and_passes_arguments(self):
        @count_calls
        def add(a, b=0, *, c=0):
            return a + b + c

        assert add.calls == 0
        assert add(1, 2, c=3) == 6
        assert add(1) == 1
        assert add.calls == 2

    def test_preserves_metadata(self):
        def greet(name):
            """Say hi."""
            return f"hi {name}"

        wrapped = count_calls(greet)
        assert wrapped.__name__ == "greet"
        assert wrapped.__doc__ == "Say hi."
        assert wrapped.__wrapped__ is greet

    def test_failing_call_still_counts(self):
        @count_calls
        def boom():
            raise RuntimeError

        with pytest.raises(RuntimeError):
            boom()
        assert boom.calls == 1

    def test_each_decorated_function_has_its_own_counter(self):
        f = count_calls(lambda: 1)
        g = count_calls(lambda: 2)
        f()
        assert (f.calls, g.calls) == (1, 0)


class TestTask6Memoize:
    def test_caches_results(self):
        calls = []

        @memoize
        def square(x):
            calls.append(x)
            return x * x

        assert square(4) == 16
        assert square(4) == 16
        assert calls == [4]
        assert len(square.cache) == 1

    def test_kwargs_order_does_not_matter(self):
        calls = []

        @memoize
        def f(a, b):
            calls.append((a, b))
            return a - b

        assert f(a=5, b=2) == 3
        assert f(b=2, a=5) == 3
        assert len(calls) == 1

    def test_unhashable_args_bypass_the_cache(self):
        @memoize
        def total(values):
            return sum(values)

        assert total([1, 2]) == 3
        assert total([1, 2]) == 3
        assert total.cache == {}

    def test_type_error_from_function_is_not_hidden(self):
        @memoize
        def bad(x):
            raise TypeError("from inside")

        with pytest.raises(TypeError, match="from inside"):
            bad(1)

    def test_cache_clear_and_recursion(self):
        @memoize
        def fib(n):
            return n if n < 2 else fib(n - 1) + fib(n - 2)

        assert fib(80) == 23416728348467685  # fast only if cached
        assert fib.__name__ == "fib"
        fib.cache_clear()
        assert fib.cache == {}


class FlakyError(ConnectionError):
    pass


def make_flaky(failures, exc=FlakyError, result="ok"):
    state = {"calls": 0}

    def func(*args, **kwargs):
        state["calls"] += 1
        if state["calls"] <= failures:
            raise exc(f"failure {state['calls']}")
        return result, args, kwargs

    return func, state


class TestTask7Retry:
    def test_succeeds_after_retries_with_backoff(self):
        sleeps = []
        func, state = make_flaky(2)
        wrapped = retry(exceptions=(ConnectionError,), attempts=3, delay=0.5, sleep=sleeps.append)(func)
        assert wrapped(1, x=2) == ("ok", (1,), {"x": 2})
        assert state["calls"] == 3
        assert sleeps == [0.5, 1.0]

    def test_reraises_last_error_after_all_attempts(self):
        sleeps = []
        func, state = make_flaky(10)
        wrapped = retry(exceptions=(FlakyError,), attempts=4, delay=0.1, sleep=sleeps.append)(func)
        with pytest.raises(FlakyError, match="failure 4"):
            wrapped()
        assert state["calls"] == 4
        assert sleeps == pytest.approx([0.1, 0.2, 0.4])

    def test_other_exceptions_are_not_retried(self):
        sleeps = []
        func, state = make_flaky(1, exc=KeyError)
        wrapped = retry(exceptions=(ConnectionError,), attempts=5, sleep=sleeps.append)(func)
        with pytest.raises(KeyError):
            wrapped()
        assert state["calls"] == 1
        assert sleeps == []

    def test_invalid_attempts_raise_at_decoration_time(self):
        with pytest.raises(ValueError):
            retry(attempts=0)

    def test_preserves_metadata(self):
        def fetch_user():
            """Fetch."""

        wrapped = retry(sleep=lambda s: None)(fetch_user)
        assert wrapped.__name__ == "fetch_user"
        assert wrapped.__wrapped__ is fetch_user


class Color(Enum):
    RED = "red"


class TestTask8ToJsonable:
    def test_primitives_pass_through(self):
        assert [to_jsonable(v) for v in ("a", 1, 1.5, True, None)] == ["a", 1, 1.5, True, None]

    def test_registered_types(self):
        assert to_jsonable(Decimal("9.90")) == "9.90"
        assert to_jsonable(UUID(int=1)) == "00000000-0000-0000-0000-000000000001"
        assert to_jsonable(date(2024, 5, 1)) == "2024-05-01"
        assert to_jsonable(datetime(2024, 5, 1, 12, 30, tzinfo=UTC)) == "2024-05-01T12:30:00+00:00"
        assert to_jsonable(Color.RED) == "red"

    def test_nested_containers(self):
        payload = {
            "id": UUID(int=1),
            "tags": {"b", "a"},
            "prices": (Decimal("1.00"), Decimal("2.50")),
            1: [Color.RED, frozenset({3, 1})],
        }
        result = to_jsonable(payload)
        assert result == {
            "id": "00000000-0000-0000-0000-000000000001",
            "tags": ["a", "b"],
            "prices": ["1.00", "2.50"],
            "1": ["red", [1, 3]],
        }
        json.dumps(result)  # must not raise

    def test_unknown_type_raises(self):
        with pytest.raises(TypeError, match="Object of type object is not JSON serializable"):
            to_jsonable(object())

    def test_uses_singledispatch_registry(self):
        assert to_jsonable("x") == "x"
        assert Decimal in to_jsonable.registry
        assert dict in to_jsonable.registry
