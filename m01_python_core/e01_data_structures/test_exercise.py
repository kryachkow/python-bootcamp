import inspect

import pytest

from m01_python_core.e01_data_structures.exercise import (
    LRUCache,
    count_words,
    flatten,
    group_by_first_letter,
    invert_dict,
    merge_intervals,
    moving_average,
    top_n,
    unique_preserve_order,
)


class TestTask1CountWords:
    def test_counts_case_insensitively(self):
        assert count_words("To be, or not to be!") == {"to": 2, "be": 2, "or": 1, "not": 1}

    def test_keeps_apostrophes_and_digits(self):
        assert count_words("It's 2 o'clock, it's 2") == {"it's": 2, "2": 2, "o'clock": 1}

    def test_empty_text(self):
        assert count_words("  ...  ") == {}

    def test_returns_plain_dict(self):
        assert type(count_words("a a")) is dict


class TestTask2GroupByFirstLetter:
    def test_groups_and_lowercases_keys(self):
        result = group_by_first_letter(["apple", "Avocado", "banana", "", "blueberry"])
        assert result == {"a": ["apple", "Avocado"], "b": ["banana", "blueberry"]}

    def test_key_order_follows_first_seen(self):
        assert list(group_by_first_letter(["zeta", "alpha", "zoo"])) == ["z", "a"]

    def test_accepts_any_iterable(self):
        assert group_by_first_letter(w for w in ["x"]) == {"x": ["x"]}

    def test_returns_plain_dict(self):
        assert type(group_by_first_letter(["a"])) is dict


class TestTask3Flatten:
    def test_deeply_nested(self):
        assert flatten([1, [2, (3, [4])], "ab", [[[]]]]) == [1, 2, 3, 4, "ab"]

    def test_strings_and_dicts_are_atoms(self):
        assert flatten(["abc", {"k": 1}, b"xy"]) == ["abc", {"k": 1}, b"xy"]

    def test_empty(self):
        assert flatten([]) == []


class TestTask4TopN:
    def test_sorted_by_score_then_name(self):
        assert top_n({"bob": 3, "alice": 5, "carol": 3}, 3) == [("alice", 5), ("bob", 3), ("carol", 3)]

    def test_n_bigger_than_size(self):
        assert top_n({"a": 1}, 10) == [("a", 1)]

    @pytest.mark.parametrize("n", [0, -1])
    def test_non_positive_n(self, n):
        assert top_n({"a": 1}, n) == []


class TestTask5UniquePreserveOrder:
    def test_keeps_first_occurrence(self):
        assert unique_preserve_order([3, 1, 3, 2, 1]) == [3, 1, 2]

    def test_works_with_generators(self):
        assert unique_preserve_order(c for c in "mississippi") == ["m", "i", "s", "p"]


class TestTask6InvertDict:
    def test_groups_keys_by_value(self):
        assert invert_dict({"a": 1, "b": 2, "c": 1}) == {1: ["a", "c"], 2: ["b"]}

    def test_empty(self):
        assert invert_dict({}) == {}


class TestTask7MergeIntervals:
    def test_unsorted_overlapping(self):
        assert merge_intervals([(5, 7), (1, 3), (2, 4)]) == [(1, 4), (5, 7)]

    def test_touching_intervals_merge(self):
        assert merge_intervals([(1, 3), (3, 5)]) == [(1, 5)]

    def test_contained_interval(self):
        assert merge_intervals([(1, 10), (2, 3)]) == [(1, 10)]

    def test_empty(self):
        assert merge_intervals([]) == []


class TestTask8MovingAverage:
    def test_basic(self):
        assert list(moving_average([1, 2, 3, 4, 5], 3)) == [2.0, 3.0, 4.0]

    def test_window_bigger_than_input(self):
        assert list(moving_average([1, 2], 3)) == []

    def test_is_lazy(self):
        result = moving_average(iter([1, 2, 3]), 1)
        assert inspect.isgenerator(result) or hasattr(result, "__next__")
        assert next(result) == 1.0

    def test_invalid_window_raises_eagerly(self):
        with pytest.raises(ValueError):
            moving_average([1, 2, 3], 0)  # no iteration needed


class TestTask9LRUCache:
    def test_get_missing_returns_none(self):
        assert LRUCache(2).get("x") is None

    def test_evicts_least_recently_used(self):
        cache = LRUCache(2)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.get("a")  # "a" becomes most recently used
        cache.put("c", 3)  # evicts "b"
        assert cache.get("b") is None
        assert cache.get("a") == 1
        assert cache.get("c") == 3
        assert len(cache) == 2

    def test_update_existing_key_does_not_grow(self):
        cache = LRUCache(2)
        cache.put("a", 1)
        cache.put("a", 2)
        assert len(cache) == 1
        assert cache.get("a") == 2

    def test_update_refreshes_recency(self):
        cache = LRUCache(2)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("a", 10)  # "a" refreshed, "b" is now LRU
        cache.put("c", 3)
        assert cache.get("b") is None
        assert cache.get("a") == 10
