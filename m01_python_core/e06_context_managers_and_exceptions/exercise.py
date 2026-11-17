"""Exercise 1.6: exceptions, context managers, and exception groups.

Implement every task below. Each one says what it must do in its docstring.
Run the tests with:

    uv run pytest m01_python_core/e06_context_managers_and_exceptions
"""

from __future__ import annotations

import copy
import json
import time
from collections.abc import Callable, Iterable, Iterator, Mapping, MutableMapping
from contextlib import AbstractContextManager, ContextDecorator, ExitStack, contextmanager, suppress
from pathlib import Path
from types import TracebackType
from typing import Any, ClassVar, Self


# ---------------------------------------------------------------------------
# Task 1: a custom exception hierarchy
# ---------------------------------------------------------------------------
class AppError(Exception):
    """Base class of every domain error in the app.

    Write the class body:

    * Class attributes ``code: ClassVar[str] = "app_error"`` and
      ``status_code: ClassVar[int] = 500``.
    * ``__init__(self, message: str, *, details: Mapping[str, Any] | None = None)``:
      call ``super().__init__(message)`` (so ``str(exc) == message``), then
      store ``self.message`` and ``self.details`` (a new ``dict``, empty when
      ``None``).
    * ``to_dict()`` returns ``{"code": ..., "message": ..., "details": ...}``.

    An API layer can then turn *any* domain error into a JSON response with
    one exception handler, instead of one ``try/except`` per route.
    """

    pass


class NotFoundError(AppError):
    """``code = "not_found"``, ``status_code = 404``."""

    pass


class InvalidInputError(AppError):
    """``code = "invalid_input"``, ``status_code = 422``."""

    pass


class ConflictError(AppError):
    """``code = "conflict"``, ``status_code = 409``."""

    pass


def error_response(exc: Exception) -> tuple[int, dict[str, Any]]:
    """Map an exception to ``(status_code, body)``, as a FastAPI exception handler would.

    * An ``AppError`` (any subclass) gives ``(exc.status_code, exc.to_dict())``.
    * Any other exception gives ``(500, {"code": "internal_error", "message":
      "Internal server error", "details": {}})``. Never leak the original
      message: it may contain SQL, file paths, or secrets.
    """
    raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 2: exception chaining (raise ... from ...)
# ---------------------------------------------------------------------------
def parse_payload(raw: str | bytes) -> dict[str, Any]:
    """Parse a JSON object that must contain an ``"id"`` key.

    * Malformed JSON: raise ``InvalidInputError("malformed JSON",
      details={"position": err.pos})`` **from** the original
      ``json.JSONDecodeError``, so ``__cause__`` keeps the low-level error
      for the logs.
    * Valid JSON that is not an object (a list, a number, ...): raise
      ``InvalidInputError("payload must be a JSON object")``.
    * No ``"id"`` key: look it up with ``payload["id"]`` inside
      ``try/except KeyError``, and raise ``InvalidInputError("missing field:
      id")`` **from None**. The ``KeyError`` is an implementation detail, and
      ``from None`` hides it from the traceback (``__suppress_context__``).
    * Otherwise return the dict.
    """
    raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 3: @contextmanager
# ---------------------------------------------------------------------------
@contextmanager
def temporary_env(env: MutableMapping[str, str], **values: str | None) -> Iterator[MutableMapping[str, str]]:
    """Temporarily set (or, with ``None``, remove) keys of ``env``, then restore them.

    * On enter: for every ``key=value``, set ``env[key] = value``, or remove
      the key if the value is ``None`` (a missing key is fine). Yield ``env``.
    * On exit, **even if the body raised**: put every touched key back the
      way it was. Restore the old value, or delete the key if it did not
      exist before. Keys you did not touch stay as they are.
    * Do not swallow the exception.

    Pass ``os.environ`` in real code. The tests pass a plain dict.

    >>> env = {"MODE": "prod"}
    >>> with temporary_env(env, MODE="test", DEBUG="1"):
    ...     env
    {'MODE': 'test', 'DEBUG': '1'}
    >>> env
    {'MODE': 'prod'}

    Hint: ``try: yield ... finally: restore``.
    """
    raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 4: a class-based context manager that is also a decorator
# ---------------------------------------------------------------------------
class Timer(ContextDecorator):
    """Measure how long a block takes: ``with Timer() as t: ...; t.elapsed``.

    * ``clock`` returns the current time in seconds. Inject a fake in tests.
    * ``elapsed`` is ``None`` before the first use. ``__enter__`` records
      the start time, resets ``elapsed`` to ``None``, and returns ``self``.
    * ``__exit__`` sets ``elapsed = clock() - start``, **also when the block
      raised**. It must not suppress exceptions: return ``None`` or
      ``False``.
    * ``ContextDecorator`` (already a base class) makes ``@Timer()`` work on
      functions too. Each call of the decorated function enters and exits
      the timer.
    * The same instance can be used again. Every ``with`` starts a new
      measurement.
    """

    def __init__(self, clock: Callable[[], float] = time.perf_counter) -> None:
        self._clock = clock
        pass

    def __enter__(self) -> Self:
        raise NotImplementedError("TODO: implement this task")

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 5: __exit__ return value and exception suppression
# ---------------------------------------------------------------------------
class Catch:
    """Catch the listed exception types and keep the caught one, like ``pytest.raises`` without the assertion.

    ``Catch(*exc_types)`` raises ``TypeError`` if no types are given.

    * ``__enter__`` returns ``self``.
    * ``__exit__``: if the block raised an instance of one of ``exc_types``
      (subclasses included), store it in ``self.exception`` and return
      ``True``. Returning a true value *suppresses* the exception. For any
      other exception, return ``False``, so it propagates. If nothing was
      raised, ``self.exception`` stays ``None``.

    >>> with Catch(KeyError, IndexError) as caught:
    ...     {}["missing"]
    >>> type(caught.exception).__name__
    'KeyError'
    """

    def __init__(self, *exc_types: type[BaseException]) -> None:
        raise NotImplementedError("TODO: implement this task")

    def __enter__(self) -> Self:
        raise NotImplementedError("TODO: implement this task")

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool:
        raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 6: contextlib.suppress
# ---------------------------------------------------------------------------
def delete_quietly(path: Path) -> bool:
    """Delete a file. Return ``True`` if it was deleted, ``False`` if it did not exist.

    Use ``contextlib.suppress(FileNotFoundError)``. Other errors, such as
    trying to delete a directory, still propagate.
    """
    raise NotImplementedError("TODO: implement this task")


def parse_ints(values: Iterable[str]) -> list[int]:
    """Parse the values that are valid integers and skip the rest, using ``suppress(ValueError)``.

    >>> parse_ints(["1", "x", " 2 ", "3.5"])
    [1, 2]
    """
    raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 7: ExitStack, a dynamic number of context managers
# ---------------------------------------------------------------------------
@contextmanager
def acquire_all[T](factories: Iterable[Callable[[], AbstractContextManager[T]]]) -> Iterator[list[T]]:
    """Enter one context manager per factory and yield the list of their values.

    * Call each factory to get a context manager, enter it, and collect what
      ``__enter__`` returned, in order.
    * On exit, exit them all in **reverse** order.
    * If a factory, or an ``__enter__``, raises halfway, the managers already
      entered must still be exited (in reverse order) before the error
      propagates.
    * If the body raises, all of them are exited and the error propagates.

    Use it to open N files, or N database connections, chosen at run time.
    A ``with a, b, c:`` statement cannot do that, because the number of
    managers is not known when you write the code.

    Hint: ``with ExitStack() as stack: stack.enter_context(cm)`` handles every
    case above.
    """
    raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 8: a transaction-style context manager that rolls back
# ---------------------------------------------------------------------------
@contextmanager
def transaction(store: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Make the changes to ``store`` inside the block all-or-nothing.

    * On enter, take a **deep** copy of ``store`` (nested lists and dicts
      included) and yield ``store`` itself.
    * If the block finishes normally, keep the changes (commit).
    * If the block raises anything (``BaseException``), restore ``store``
      **in place** to the snapshot (rollback). Other code may hold a
      reference to the dict, so do not rebind it; use ``clear()`` and
      ``update()``. Then re-raise.

    This is what ``async with session.begin():`` does for a SQLAlchemy
    session.
    """
    raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 9: ExceptionGroup and except*
# ---------------------------------------------------------------------------
def run_all[T](jobs: Mapping[str, Callable[[], T]]) -> dict[str, T]:
    """Run every job, even if some fail, and report every failure together.

    * Call the jobs in order. Collect results as ``{name: result}``.
    * If a job raises an ``Exception``, call ``exc.add_note(f"job: {name}")``,
      collect it, and go on with the next job.
    * At the end, if there were failures, raise
      ``ExceptionGroup(f"{n} of {total} job(s) failed", failures)``.
      Otherwise return the results.

    A single ``raise`` would report only the first failure.
    ``ExceptionGroup`` (3.11+) carries all of them, the same way
    ``asyncio.TaskGroup`` does.
    """
    raise NotImplementedError("TODO: implement this task")


def count_failures(func: Callable[[], object]) -> dict[str, int]:
    """Call ``func`` and count its ``ValueError`` and ``KeyError`` failures by type, with ``except*``.

    * Return ``{"ValueError": n, "KeyError": m}``, with only the keys that
      occurred. Return ``{}`` if ``func`` did not raise.
    * ``n`` is the number of matching exceptions in the group
      (``len(eg.exceptions)``). Subclasses count under the base name.
    * A plain (not grouped) ``ValueError`` also works: ``except*`` wraps it
      in a group for you, so it counts as 1.
    * Any other exception type in the group is not handled. ``except*``
      re-raises it automatically in an ``ExceptionGroup``.
    """
    raise NotImplementedError("TODO: implement this task")
