"""Exercise 1.7: typing that you can see at runtime.

Type hints are checked by mypy/pyright, but many of them also exist at runtime,
and frameworks (FastAPI, Pydantic, LangChain tools) read them. The tests check
runtime behaviour and runtime-visible typing metadata, not mypy output.

Task 4 lives in ``messages.py`` (see the note at the top of that file).

Run the tests with:

    uv run pytest m01_python_core/e07_typing
"""

from __future__ import annotations

import functools
import inspect
from collections.abc import Callable, Hashable, Iterable
from typing import Concatenate, Protocol, TypeGuard, overload, runtime_checkable

try:  # Python 3.13+
    from typing import TypeIs
except ImportError:  # Python 3.12: the backport (installed with pydantic)
    from typing_extensions import TypeIs


# ---------------------------------------------------------------------------
# Task 1: Protocol (structural typing) + runtime_checkable
# ---------------------------------------------------------------------------
# Make ``Retriever`` usable with ``isinstance()``: decorate the class.
@runtime_checkable
class Retriever(Protocol):
    """Anything that has a ``retrieve(query: str, k: int = 4) -> list[str]`` method.

    Write the protocol member (a method whose body is ``...``). Classes do
    **not** inherit from ``Retriever``. A vector store, a BM25 index, or a
    fake in a test all match it just by having the method. This is
    duck typing that a type checker understands.

    Decorate it with ``@typing.runtime_checkable`` so ``isinstance(obj,
    Retriever)`` works. At runtime that check only tests that the method
    *exists*; it does not check signatures.
    """

    def retrieve(self, query: str, k: int = 4) -> list[str]: ...


def retrieve_all(sources: Iterable[object], query: str, k: int = 4) -> list[str]:
    """Query every source that is a ``Retriever`` and merge the results.

    * Skip sources that are not ``Retriever`` instances (use ``isinstance``).
    * Call ``source.retrieve(query, k)`` for each remaining source, in order.
    * Concatenate the results, drop duplicates (keep the first occurrence),
      and return at most ``k`` documents.
    """
    seen: dict[str, None] = {}
    for source in sources:
        if isinstance(source, Retriever):
            for doc in source.retrieve(query, k):
                seen.setdefault(doc, None)
    return list(seen)[:k]


# ---------------------------------------------------------------------------
# Task 2: a PEP 695 generic class with a bound
# ---------------------------------------------------------------------------
class HasId(Protocol):
    """Given: anything with an ``id: int`` attribute."""

    id: int


# Write the class header so the repository is generic over ``T``, with ``T``
# bound to ``HasId``: ``class InMemoryRepository[T: HasId]:``
class InMemoryRepository[T: HasId]:
    """An in-memory stand-in for a database repository, used in unit tests.

    Use PEP 695 syntax (no ``TypeVar``): ``InMemoryRepository[User]`` then
    only accepts and returns ``User``. At runtime the type parameter is
    visible as ``InMemoryRepository.__type_params__``.

    * ``add(entity)``: store it under ``entity.id`` and return it. Raise
      ``ValueError`` if that id is already stored.
    * ``get(id)``: the entity, or ``None``.
    * ``list(where=None)``: all entities in insertion order, filtered by the
      ``where`` predicate if given.
    * ``remove(id)``: ``True`` if something was removed, otherwise ``False``.
    * ``len(repo)``: the number of entities.
    """

    def __init__(self) -> None:
        self._items: dict[int, T] = {}

    def add(self, entity: T) -> T:
        if entity.id in self._items:
            raise ValueError(f"duplicate id: {entity.id}")
        self._items[entity.id] = entity
        return entity

    def get(self, id: int) -> T | None:
        return self._items.get(id)

    def list(self, where: Callable[[T], bool] | None = None) -> list[T]:
        items = self._items.values()
        return [e for e in items if where(e)] if where else [*items]

    def remove(self, id: int) -> bool:
        return self._items.pop(id, None) is not None

    def __len__(self) -> int:
        return len(self._items)


# ---------------------------------------------------------------------------
# Task 3: a PEP 695 generic function
# ---------------------------------------------------------------------------
# Write the header with two type parameters, ``T`` and ``K`` (bound to
# ``Hashable``), in that order:
#     def index_by[T, K: Hashable](items: Iterable[T], key: Callable[[T], K]) -> dict[K, T]:
def index_by[T, K: Hashable](items: Iterable[T], key: Callable[[T], K]) -> dict[K, T]:
    """Build ``{key(item): item}``, for example users by email.

    * Keep the insertion order.
    * Raise ``ValueError`` (with the duplicate key's ``repr`` in the message)
      if two items have the same key. Silently overwriting would hide data
      bugs.

    >>> index_by(["apple", "bob"], key=len)
    {5: 'apple', 3: 'bob'}
    """
    result: dict[K, T] = {}
    for item in items:
        k = key(item)
        if k in result:
            raise ValueError(f"duplicate key: {k!r}")
        result[k] = item
    return result


# ---------------------------------------------------------------------------
# Task 5: @overload
# ---------------------------------------------------------------------------
TRUE_STRINGS = frozenset({"1", "true", "yes", "on"})
FALSE_STRINGS = frozenset({"0", "false", "no", "off"})

# Declare three ``@overload`` signatures for ``coerce`` here, so a type checker
# knows that ``coerce("1", int)`` is an ``int``, ``coerce("1", float)`` is a
# ``float``, and ``coerce("on", bool)`` is a ``bool``. Each overload's body is
# ``...``. Put the ``bool`` overload first (``bool`` is a subclass of ``int``).
@overload
def coerce(value: str, to: type[bool]) -> bool: ...
@overload
def coerce(value: str, to: type[int]) -> int: ...
@overload
def coerce(value: str, to: type[float]) -> float: ...
def coerce(value: str, to: type[bool] | type[int] | type[float]) -> bool | int | float:
    """Convert a config string to ``bool``, ``int``, or ``float``.

    * Strip spaces first.
    * ``bool``: case-insensitive ``TRUE_STRINGS`` / ``FALSE_STRINGS``,
      anything else raises ``ValueError``.
    * ``int`` / ``float``: call the type (it raises ``ValueError`` itself).
    * Any other target type raises ``TypeError``.

    The overloads exist only for type checkers. At runtime only this
    implementation runs, but ``typing.get_overloads(coerce)`` lists them.
    """
    value = value.strip()
    if to is bool:
        lowered = value.lower()
        if lowered in TRUE_STRINGS:
            return True
        if lowered in FALSE_STRINGS:
            return False
        raise ValueError(f"not a boolean: {value!r}")
    if to is int or to is float:
        return to(value)
    raise TypeError(f"unsupported target type: {to!r}")


# ---------------------------------------------------------------------------
# Task 6: TypeGuard and TypeIs narrowing functions
# ---------------------------------------------------------------------------
def is_str_list(values: list[object]) -> TypeGuard[list[str]]:
    """Return ``True`` if every element is a ``str`` (an empty list counts).

    ``TypeGuard[list[str]]`` tells the type checker: after ``if
    is_str_list(xs):``, treat ``xs`` as ``list[str]``. A ``TypeGuard`` is
    needed here, not ``TypeIs``, because ``list[str]`` is not a subtype of
    ``list[object]`` (lists are invariant).
    """
    return all(isinstance(v, str) for v in values)


type JsonScalar = str | int | float | bool | None


def is_json_scalar(value: object) -> TypeIs[JsonScalar]:
    """Return ``True`` if ``value`` is a JSON scalar: ``str``, ``int``, ``float``, ``bool``, or ``None``.

    ``TypeIs`` (3.13, backported in ``typing_extensions``) narrows **both**
    branches: after ``if is_json_scalar(x): ... else: ...``, a checker knows
    that ``x`` is a ``JsonScalar`` in the first branch and is *not* one in
    the second. That is only sound if the function returns ``True`` for
    every value of the type, which a plain ``isinstance`` check guarantees.

    ``type JsonScalar = ...`` above is a PEP 695 type alias. At runtime it is
    a ``typing.TypeAliasType``, and its ``__value__`` holds the union.
    """
    return value is None or isinstance(value, (str, int, float, bool))


# ---------------------------------------------------------------------------
# Task 7: a ParamSpec-typed decorator
# ---------------------------------------------------------------------------
def logged[**P, R](log: list[str]) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator factory: append one line to ``log`` per call.

    * Line format: ``"name(args) -> result"``. ``args`` are the ``repr`` of
      the positional arguments, then ``key=repr(value)`` for keyword
      arguments, joined by ``", "``: ``"add(1, b=2) -> 3"``.
    * If the call raises, log ``"name(args) raised ExcType"`` and re-raise.
    * Use ``functools.wraps``. Then ``inspect.signature(wrapper)`` shows the
      original parameters, which FastAPI and LangChain's ``@tool`` rely on.

    ``**P`` (a ``ParamSpec``) captures the whole parameter list of the
    decorated function, so the wrapper keeps the exact signature for type
    checkers too. ``Callable[..., Any]`` would lose it.
    """
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            shown = ", ".join([*map(repr, args), *(f"{k}={v!r}" for k, v in kwargs.items())])
            call = f"{func.__name__}({shown})"
            try:
                result = func(*args, **kwargs)
            except Exception as exc:
                log.append(f"{call} raised {type(exc).__name__}")
                raise
            log.append(f"{call} -> {result!r}")
            return result

        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# Task 8: Concatenate, a decorator that injects an argument
# ---------------------------------------------------------------------------
class Session(Protocol):
    """Given: the minimal interface of a DB session."""

    def close(self) -> None: ...


def with_session[S: Session, **P, R](
    factory: Callable[[], S],
) -> Callable[[Callable[Concatenate[S, P], R]], Callable[P, R]]:
    """Decorator factory: open a session, pass it as the first argument, always close it.

    ``@with_session(make_session)`` on ``def get_user(session, user_id)``
    gives a function called as ``get_user(user_id)``. This is a tiny version of
    FastAPI's ``Depends(get_session)``.

    * On each call: ``session = factory()``, then
      ``func(session, *args, **kwargs)``, then ``session.close()`` in a
      ``finally``, so it runs even when ``func`` raises.
    * Use ``functools.wraps``, then set ``wrapper.__signature__`` to the
      original signature **without its first parameter**, so introspection
      (FastAPI, docs, ``help()``) shows only what callers pass. Build it with
      ``inspect.signature(func)`` and ``.replace(parameters=...)``.

    The decorated function is typed ``Callable[Concatenate[S, P], R]``:
    "a session first, then whatever parameters ``P`` stands for". The
    result is ``Callable[P, R]``: the same function without the session.
    """
    def decorator(func: Callable[Concatenate[S, P], R]) -> Callable[P, R]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            session = factory()
            try:
                return func(session, *args, **kwargs)
            finally:
                session.close()

        sig = inspect.signature(func)
        wrapper.__signature__ = sig.replace(parameters=list(sig.parameters.values())[1:])  # type: ignore[attr-defined]
        return wrapper

    return decorator
