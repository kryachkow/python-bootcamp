"""Exercise 1.2: function signatures, closures, and decorators.

Implement every function below. Each one says what it must do in its
docstring. Run the tests with:

    uv run pytest m01_python_core/e02_functions_and_decorators
"""

from __future__ import annotations

import functools
import time
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Any
from urllib.parse import urlencode
from uuid import UUID


# ---------------------------------------------------------------------------
# Task 1: build a URL (positional-only, *args, keyword-only, **kwargs)
# ---------------------------------------------------------------------------
def build_url(base: str, /, *segments: str | int, secure: bool = True, **query: str | int | None) -> str:
    """Build a URL from a host, path segments, and query parameters.

    The signature is already written. Read it carefully, it is the lesson:

    * ``base`` is positional-only (``/``), so a caller can still pass a
      query parameter *named* ``base``: ``build_url("h", base="x")`` puts
      ``base=x`` into the query string.
    * ``*segments`` collects any number of path parts.
    * ``secure`` is keyword-only (it comes after ``*segments``).
    * ``**query`` collects every other keyword argument.

    Rules:

    * The scheme is ``https`` when ``secure`` is true, otherwise ``http``.
    * Strip leading and trailing ``/`` from ``base`` and from every segment.
      Segments can be ints; convert them with ``str``. Skip segments that are
      empty after stripping.
    * Skip query parameters whose value is ``None``. Keep the order the
      caller passed them in, and encode them with ``urllib.parse.urlencode``.
    * Add ``?`` only when at least one query parameter is left.

    >>> build_url("api.example.com/", "/v1/", "users", 42, page=2, q="hello world")
    'https://api.example.com/v1/users/42?page=2&q=hello+world'
    >>> build_url("localhost:8000", secure=False, debug=None)
    'http://localhost:8000'
    """
    raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 2: counter factory (closures and ``nonlocal``)
# ---------------------------------------------------------------------------
def make_counter(start: int = 0, step: int = 1) -> Callable[[], int]:
    """Return a function that returns ``start``, ``start + step``, ... on each call.

    * Each call of the returned function returns the next value. The first
      call returns ``start``.
    * Counters made by separate ``make_counter`` calls are independent.
    * Raise ``ValueError`` (when ``make_counter`` is called) if ``step == 0``.
    * Keep the state in the closure, not in a global or a class.

    >>> next_id = make_counter(100, step=10)
    >>> next_id(), next_id(), next_id()
    (100, 110, 120)

    Hint: an inner function needs ``nonlocal`` to rebind a variable of the
    enclosing function.
    """
    raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 3: compose
# ---------------------------------------------------------------------------
def compose(*funcs: Callable[[Any], Any]) -> Callable[[Any], Any]:
    """Compose one-argument functions from right to left.

    * ``compose(f, g, h)(x)`` returns ``f(g(h(x)))``.
    * ``compose()`` (no functions) returns the identity function.
    * Raise ``TypeError`` when ``compose`` is called if any argument is not
      callable. Do not wait for the composed function to be called.

    >>> slugify = compose("-".join, str.split, str.lower)
    >>> slugify("Hello Big World")
    'hello-big-world'

    Hint: ``functools.reduce`` works, and so does a plain loop over
    ``reversed(funcs)``.
    """
    raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 4: functools.partial
# ---------------------------------------------------------------------------
def send_notification(channel: str, message: str, *, urgent: bool = False, retries: int = 0) -> str:
    """Pretend to send a notification. This function is given; do not change it."""
    flag = "!" if urgent else ""
    return f"[{channel}]{flag} {message} (retries={retries})"


def make_alert_sender(channel: str) -> functools.partial[str]:
    """Return ``send_notification`` with ``channel``, ``urgent=True`` and ``retries=3`` bound.

    * Return a real ``functools.partial`` object, not a lambda or a nested
      function: a partial keeps ``.func``, ``.args``, and ``.keywords``,
      which makes it easy to inspect and log.
    * The caller passes only the message. The caller can still override the
      bound keywords, for example ``sender("disk full", retries=0)``.

    >>> page_ops = make_alert_sender("ops")
    >>> page_ops("disk full")
    '[ops]! disk full (retries=3)'
    """
    raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 5: a decorator that counts calls
# ---------------------------------------------------------------------------
def count_calls[**P, R](func: Callable[P, R]) -> Callable[P, R]:
    """Decorator: count how many times the decorated function was called.

    * The wrapper passes all positional and keyword arguments through and
      returns the original return value.
    * The wrapper has a ``calls`` attribute (an ``int``, starting at 0). Add 1
      *before* calling the original function, so a call that raises still
      counts.
    * Use ``functools.wraps``, so the wrapper keeps ``__name__``,
      ``__doc__``, and ``__wrapped__`` of the original.

    >>> @count_calls
    ... def greet(name):
    ...     return f"hi {name}"
    >>> greet("ann"), greet.calls, greet.__name__
    ('hi ann', 1, 'greet')
    """
    raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 6: memoize
# ---------------------------------------------------------------------------
def memoize[R](func: Callable[..., R]) -> Callable[..., R]:
    """Decorator: cache results by the call arguments.

    * The cache key is ``(args, tuple(sorted(kwargs.items())))``, so
      ``f(a=1, b=2)`` and ``f(b=2, a=1)`` share one cache entry.
    * The wrapper exposes the cache as a ``cache`` attribute (a ``dict``
      from key to result) and has a ``cache_clear()`` function attribute that
      empties it.
    * If an argument is unhashable (for example a list), call the function
      without caching. Do not raise, and do not hide a ``TypeError`` that the
      function itself raises.
    * Exceptions are not cached.
    * Use ``functools.wraps``.

    >>> @memoize
    ... def square(x):
    ...     return x * x
    >>> square(4), square(4), len(square.cache)
    (16, 16, 1)

    Hint: build the key, then call ``hash(key)`` inside ``try`` to find out
    whether it is hashable. Call ``func`` outside that ``try``.
    """
    raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 7: retry, a decorator with parameters
# ---------------------------------------------------------------------------
def retry[**P, R](
    *,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
    attempts: int = 3,
    delay: float = 0.0,
    backoff: float = 2.0,
    sleep: Callable[[float], None] = time.sleep,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator factory: retry the decorated function when it raises.

    Use it as ``@retry(exceptions=(ConnectionError,), attempts=4, delay=0.1)``.

    * Call the function at most ``attempts`` times in total.
    * Retry only when it raises one of ``exceptions``. Any other exception
      propagates at once, without retrying.
    * Between attempts, call ``sleep(delay * backoff ** n)``, where ``n`` is
      0 before the 2nd attempt, 1 before the 3rd, and so on. Do not sleep
      after the last attempt. (``sleep`` is a parameter so that tests and
      callers can inject a fake. Never call ``time.sleep`` directly.)
    * When every attempt fails, re-raise the last exception unchanged.
    * Raise ``ValueError`` when ``retry(...)`` is called with
      ``attempts < 1``, before any function is decorated.
    * The wrapper must use ``functools.wraps``.

    Example: with ``attempts=4, delay=0.1`` and a function that always fails,
    ``sleep`` is called with 0.1, 0.2, and 0.4, then the error is raised.
    """
    raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 8: functools.singledispatch
# ---------------------------------------------------------------------------
@functools.singledispatch
def to_jsonable(value: Any) -> Any:
    """Convert ``value`` into something ``json.dumps`` accepts.

    This is what a JSON encoder (FastAPI's ``jsonable_encoder``, for example)
    does internally. Write the generic case here, and register one
    implementation per type with ``@to_jsonable.register`` below.

    * ``str``, ``int``, ``float``, ``bool``, and ``None`` are returned as they
      are (generic case).
    * Anything else that has no registered implementation raises
      ``TypeError("Object of type Foo is not JSON serializable")``, with the
      real type name instead of ``Foo`` (generic case).

    Register implementations for:

    * ``Decimal`` and ``UUID``: ``str(value)``.
    * ``date`` (this also covers ``datetime``, a subclass): ``value.isoformat()``.
    * ``Enum``: convert ``value.value`` recursively.
    * ``list`` and ``tuple``: a list with every item converted.
    * ``set`` and ``frozenset``: a list of the converted items, sorted.
    * ``dict``: a dict with ``str(key)`` keys and converted values.

    >>> to_jsonable({"id": UUID(int=1), "tags": {"b", "a"}, "price": Decimal("9.90")})
    {'id': '00000000-0000-0000-0000-000000000001', 'tags': ['a', 'b'], 'price': '9.90'}

    Hint: ``register`` can take the type from the annotation of the first
    parameter, or as an argument: ``@to_jsonable.register(tuple)``. You can
    stack ``register`` decorators.
    """
    raise NotImplementedError("TODO: implement this task")


# Register the type-specific implementations of ``to_jsonable`` here.
# (your @to_jsonable.register implementations go here)

