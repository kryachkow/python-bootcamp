"""Exercise 1.1: built-in data structures and the `collections` module.

Implement every function below. Each one says what it must do in its
docstring. Run the tests with:

    uv run pytest m01_python_core/e01_data_structures
"""

from __future__ import annotations

import re
from collections import Counter, OrderedDict, defaultdict, deque
from collections.abc import Hashable, Iterable, Iterator
from typing import Any


# ---------------------------------------------------------------------------
# Task 1: count words
# ---------------------------------------------------------------------------
def count_words(text: str) -> dict[str, int]:
    """Count how many times each word occurs in ``text``.

    * Matching ignores case: ``"Hello"`` and ``"hello"`` are the same word.
    * A word is a run of letters, digits, or apostrophes; everything else
      separates words.
    * Return a plain ``dict`` with lowercased words as keys.

    >>> count_words("To be, or not to be!")
    {'to': 2, 'be': 2, 'or': 1, 'not': 1}

    Hint: ``re.findall`` and ``collections.Counter``.
    """
    raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 2: group by first letter
# ---------------------------------------------------------------------------
def group_by_first_letter(words: Iterable[str]) -> dict[str, list[str]]:
    """Group words by their first letter, lowercased.

    * Skip empty strings.
    * Inside each group, keep the order the words came in.
    * Keys appear in the order their first word was seen.

    >>> group_by_first_letter(["apple", "Avocado", "banana", "", "blueberry"])
    {'a': ['apple', 'Avocado'], 'b': ['banana', 'blueberry']}

    Hint: ``collections.defaultdict(list)``.
    """
    raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 3: flatten
# ---------------------------------------------------------------------------
def flatten(nested: Iterable[Any]) -> list[Any]:
    """Flatten lists and tuples nested to any depth into one flat list.

    Treat strings, bytes, dicts, and every other type as single values. Do
    not iterate into them.

    >>> flatten([1, [2, (3, [4])], "ab", [[[]]]])
    [1, 2, 3, 4, 'ab']
    """
    raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 4: top N
# ---------------------------------------------------------------------------
def top_n(scores: dict[str, int], n: int) -> list[tuple[str, int]]:
    """Return the ``n`` best ``(name, score)`` pairs.

    * Sort by score, highest first. Break ties by name, alphabetically.
    * If ``n`` is greater than ``len(scores)``, return all pairs.
    * If ``n <= 0``, return ``[]``.

    >>> top_n({"bob": 3, "alice": 5, "carol": 3}, 2)
    [('alice', 5), ('bob', 3)]

    Hint: ``sorted(..., key=lambda kv: (-kv[1], kv[0]))``.
    """
    raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 5: unique, keep order
# ---------------------------------------------------------------------------
def unique_preserve_order[T: Hashable](items: Iterable[T]) -> list[T]:
    """Remove duplicates and keep the first occurrence of each item.

    >>> unique_preserve_order([3, 1, 3, 2, 1])
    [3, 1, 2]

    Hint: since Python 3.7, a ``dict`` keeps keys in insertion order.
    """
    raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 6: invert a dict
# ---------------------------------------------------------------------------
def invert_dict[K, V: Hashable](mapping: dict[K, V]) -> dict[V, list[K]]:
    """Invert ``mapping`` so each value maps to the list of keys that had it.

    Keep the keys in the order they appear in ``mapping``.

    >>> invert_dict({"a": 1, "b": 2, "c": 1})
    {1: ['a', 'c'], 2: ['b']}
    """
    raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 7: merge intervals
# ---------------------------------------------------------------------------
def merge_intervals(intervals: Iterable[tuple[int, int]]) -> list[tuple[int, int]]:
    """Merge overlapping or touching closed intervals.

    * The input can be in any order.
    * Return the merged intervals sorted by start.
    * ``(1, 3)`` and ``(3, 5)`` touch, so they merge into ``(1, 5)``.

    >>> merge_intervals([(5, 7), (1, 3), (2, 4)])
    [(1, 4), (5, 7)]
    """
    raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 8: moving average
# ---------------------------------------------------------------------------
def moving_average(values: Iterable[float], window: int) -> Iterator[float]:
    """Yield the average of each full sliding window over ``values``.

    * Yield nothing until ``window`` values have been seen.
    * Raise ``ValueError`` if ``window < 1``. Raise it when the function is
      called, not when the first value is read.

    >>> list(moving_average([1, 2, 3, 4, 5], 3))
    [2.0, 3.0, 4.0]

    Hint: ``collections.deque(maxlen=window)``. To raise eagerly, check the
    argument in this function and return an inner generator.
    """
    raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 9: LRU cache
# ---------------------------------------------------------------------------
class LRUCache:
    """A fixed-size cache that drops the least recently used entry when full.

    * ``get(key)`` returns the value, or ``None`` if the key is missing. A
      successful ``get`` marks the key as most recently used.
    * ``put(key, value)`` inserts or updates an entry and marks it as most
      recently used. If that makes the cache grow past ``capacity``, remove
      the least recently used entry.
    * ``len(cache)`` returns the number of entries.

    Hint: ``collections.OrderedDict`` has ``move_to_end`` and ``popitem(last=False)``.
    """

    def __init__(self, capacity: int) -> None:
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self.capacity = capacity
        pass

    def get(self, key: Hashable) -> Any | None:
        raise NotImplementedError("TODO: implement this task")

    def put(self, key: Hashable, value: Any) -> None:
        raise NotImplementedError("TODO: implement this task")

    def __len__(self) -> int:
        raise NotImplementedError("TODO: implement this task")
