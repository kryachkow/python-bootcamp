"""Exercise 1.5: iterators, generators, and itertools.

Implement every task below. Each one says what it must do in its docstring.
Laziness is part of the spec: the tests check that you do not read more input
than needed. Run the tests with:

    uv run pytest m01_python_core/e05_iterators_and_generators
"""

from __future__ import annotations

import itertools
import operator
from collections import deque
from collections.abc import Callable, Generator, Iterable, Iterator, Mapping
from datetime import date, datetime
from typing import Any, NamedTuple


# ---------------------------------------------------------------------------
# Task 1: the iterator protocol, by hand
# ---------------------------------------------------------------------------
class Paginator[T]:
    """Iterate over every item of a cursor-paginated API, one item at a time.

    ``fetch(cursor)`` returns ``(items, next_cursor)``. The first call uses
    ``cursor=None``, and ``next_cursor is None`` means "last page". This is
    how most REST APIs (Stripe, GitHub, Slack) and vector stores paginate.

    * ``__iter__`` returns ``self``: a ``Paginator`` *is* an iterator, so it
      can be consumed only once.
    * ``__next__`` returns the next item. It fetches a page only when the
      buffered items are used up. Pages that are empty but have a next cursor
      are skipped, and fetching goes on.
    * When the last page is used up, raise ``StopIteration``. Every later
      ``next()`` raises ``StopIteration`` again, without fetching.
    * Nothing is fetched in ``__init__``. ``pages_fetched`` counts the calls
      to ``fetch`` and starts at 0.

    >>> pages = {None: ([1, 2], "c1"), "c1": ([3], None)}
    >>> list(Paginator(pages.__getitem__))
    [1, 2, 3]

    Hint: keep a ``collections.deque`` buffer, the next cursor, and a
    "done" flag.
    """

    def __init__(self, fetch: Callable[[str | None], tuple[list[T], str | None]]) -> None:
        self._fetch = fetch
        pass

    def __iter__(self) -> Paginator[T]:
        raise NotImplementedError("TODO: implement this task")

    def __next__(self) -> T:
        raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 2: a generator function
# ---------------------------------------------------------------------------
def clean_lines(lines: Iterable[str]) -> Iterator[str]:
    """Yield the meaningful lines of a text file, lazily.

    * Strip whitespace (including the trailing ``"\\n"``) from both ends.
    * Skip lines that are empty after stripping.
    * Skip comment lines: lines whose first non-space character is ``#``.

    ``lines`` can be an open file. A file object yields lines lazily, so a
    generator lets you process a 10 GB log without loading it into memory.
    Write this function as a generator (with ``yield``).

    >>> list(clean_lines(["a\\n", "   \\n", "  # comment\\n", "  b  \\n"]))
    ['a', 'b']
    """
    raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 3: a lazy generator pipeline
# ---------------------------------------------------------------------------
class LogRecord(NamedTuple):
    timestamp: datetime
    level: str
    message: str


LEVELS = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}


def parse_log_lines(lines: Iterable[str]) -> Iterator[LogRecord]:
    """Parse lines like ``"2024-05-01T12:00:00 ERROR db timeout after 5s"``.

    * The format is ``<ISO timestamp> <LEVEL> <message>``, separated by
      whitespace. The message is everything after the level and can contain
      spaces.
    * Skip a line, without raising, if it has fewer than three parts, if the
      timestamp is not valid ISO 8601 (``datetime.fromisoformat``), or if
      the level is not a key of ``LEVELS`` (case-sensitive).
    * Strip the line first. Generator, lazy.

    Hint: ``line.split(maxsplit=2)``.
    """
    raise NotImplementedError("TODO: implement this task")


def errors_since(lines: Iterable[str], since: datetime) -> Iterator[str]:
    """Pipeline: yield the message of each ERROR-or-worse record at or after ``since``.

    Chain the stages lazily: ``lines -> clean_lines -> parse_log_lines ->
    filter``. No stage may build a list. The whole pipeline is a chain of
    generators that pull one line at a time. "ERROR or worse" means
    ``LEVELS[level] >= LEVELS["ERROR"]``.

    This builds on Task 2 (``clean_lines``).
    """
    raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 4: recursion with ``yield from``
# ---------------------------------------------------------------------------
def iter_leaves(tree: Mapping[str, Any], prefix: str = "") -> Iterator[tuple[str, Any]]:
    """Yield ``(dotted_key, value)`` for every leaf of a nested mapping.

    * A value that is a ``Mapping`` is a branch: go into it recursively with
      ``yield from``. Every other value (lists included) is a leaf.
    * Keys are joined with ``"."``. ``prefix`` is the path so far (``""`` at
      the top).
    * An empty nested mapping yields nothing.
    * Yield the leaves in insertion order (depth first).

    >>> list(iter_leaves({"db": {"host": "x", "port": 5432}, "debug": False}))
    [('db.host', 'x'), ('db.port', 5432), ('debug', False)]

    This is how ``pydantic-settings`` and config loaders map nested config
    to ``DB__HOST``-style environment variables.
    """
    raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 5: batching (itertools.batched)
# ---------------------------------------------------------------------------
def chunked[T](iterable: Iterable[T], size: int) -> Iterator[list[T]]:
    """Split ``iterable`` into lists of ``size`` items. The last list may be shorter.

    * Lazy: works on an infinite iterator, and reads only as many items as
      the chunks taken so far need.
    * Raise ``ValueError`` if ``size < 1``, when ``chunked`` is **called**
      (not when the first chunk is read).

    Use it to send rows to ``session.add_all`` or texts to an embeddings API
    in batches of 100.

    >>> list(chunked(range(7), 3))
    [[0, 1, 2], [3, 4, 5], [6]]

    Hint: ``itertools.batched`` (3.12+) yields tuples; ``map(list, ...)``.
    """
    raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 6: itertools.groupby
# ---------------------------------------------------------------------------
def daily_totals(events: Iterable[tuple[datetime, float]]) -> list[tuple[date, float]]:
    """Sum amounts per calendar day for events **sorted by timestamp**.

    * Return ``[(day, total), ...]`` in chronological order, with only the
      days that have events.
    * ``itertools.groupby`` only groups *consecutive* equal keys. If the
      input is not sorted (a day shows up again after another day started),
      raise ``ValueError`` instead of returning wrong totals.

    >>> daily_totals([(datetime(2024, 1, 1, 9), 10.0), (datetime(2024, 1, 1, 18), 5.0),
    ...               (datetime(2024, 1, 3, 7), 1.5)])
    [(datetime.date(2024, 1, 1), 15.0), (datetime.date(2024, 1, 3), 1.5)]
    """
    raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 7: an infinite generator (itertools.accumulate)
# ---------------------------------------------------------------------------
def backoff_delays(base: float = 0.1, factor: float = 2.0, max_delay: float = 10.0) -> Iterator[float]:
    """Yield retry delays forever: ``base``, ``base*factor``, ..., capped at ``max_delay``.

    * The sequence never ends. Callers take what they need with
      ``itertools.islice`` or ``zip(range(n), ...)``.
    * Once a delay reaches ``max_delay``, every later delay is ``max_delay``.
    * Raise ``ValueError`` eagerly (when called) if ``base <= 0``,
      ``factor < 1``, or ``max_delay < base``.

    >>> list(itertools.islice(backoff_delays(1, 3, 20), 5))
    [1, 3, 9, 20, 20]

    Hint: ``itertools.accumulate(itertools.repeat(factor), operator.mul,
    initial=base)`` is an infinite geometric sequence. ``map`` a cap over it.
    """
    raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 8: round-robin (itertools.chain / zip_longest)
# ---------------------------------------------------------------------------
def interleave(*iterables: Iterable[Any]) -> Iterator[Any]:
    """Yield one item from each iterable in turn, skipping exhausted ones.

    ``interleave("ab", [1, 2, 3], "X")`` yields ``a 1 X b 2 3``.

    * Lazy: must work when some inputs are infinite.
    * ``None`` is a valid item and must not be dropped.

    Hint: ``itertools.zip_longest(..., fillvalue=sentinel)`` and
    ``itertools.chain.from_iterable``, then filter out a private
    ``sentinel = object()``.
    """
    raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 9: a generator you talk to with send()
# ---------------------------------------------------------------------------
def running_average() -> Generator[float | None, float | None, None]:
    """A coroutine-style generator that keeps a running average.

    * Prime it with ``next(gen)``. That first ``next`` returns ``None``.
    * ``gen.send(x)`` adds ``x`` and returns the average of all values so far.
    * ``gen.send(None)`` (or ``next(gen)``) adds nothing and returns the
      current average (``None`` if nothing was sent yet).

    >>> avg = running_average()
    >>> next(avg)
    >>> avg.send(10), avg.send(20), avg.send(None)
    (10.0, 15.0, 15.0)

    Hint: ``received = yield current`` both produces a value and receives
    the next one.
    """
    raise NotImplementedError("TODO: implement this task")
