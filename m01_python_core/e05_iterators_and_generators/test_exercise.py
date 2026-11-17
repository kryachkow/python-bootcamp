import inspect
import itertools
from datetime import date, datetime

import pytest

from m01_python_core.e05_iterators_and_generators.exercise import (
    LogRecord,
    Paginator,
    backoff_delays,
    chunked,
    clean_lines,
    daily_totals,
    errors_since,
    interleave,
    iter_leaves,
    parse_log_lines,
    running_average,
)


class Tracked:
    """An iterator that records how many items were pulled from it."""

    def __init__(self, items):
        self._it = iter(items)
        self.pulled = 0

    def __iter__(self):
        return self

    def __next__(self):
        value = next(self._it)
        self.pulled += 1
        return value


class FakeApi:
    def __init__(self, pages):
        self.pages = pages  # cursor -> (items, next_cursor)
        self.calls = []

    def __call__(self, cursor):
        self.calls.append(cursor)
        return self.pages[cursor]


class TestTask1Paginator:
    def test_iterates_all_pages(self):
        api = FakeApi({None: ([1, 2], "c1"), "c1": ([3], "c2"), "c2": ([4, 5], None)})
        assert list(Paginator(api)) == [1, 2, 3, 4, 5]
        assert api.calls == [None, "c1", "c2"]

    def test_is_lazy(self):
        api = FakeApi({None: ([1, 2], "c1"), "c1": ([3], None)})
        p = Paginator(api)
        assert p.pages_fetched == 0
        assert iter(p) is p
        assert next(p) == 1
        assert next(p) == 2
        assert p.pages_fetched == 1
        assert next(p) == 3
        assert p.pages_fetched == 2

    def test_skips_empty_pages_and_handles_empty_result(self):
        api = FakeApi({None: ([], "c1"), "c1": ([], "c2"), "c2": (["x"], None)})
        assert list(Paginator(api)) == ["x"]
        assert list(Paginator(FakeApi({None: ([], None)}))) == []

    def test_exhausted_stays_exhausted_without_refetching(self):
        api = FakeApi({None: ([1], None)})
        p = Paginator(api)
        assert list(p) == [1]
        with pytest.raises(StopIteration):
            next(p)
        assert list(p) == []
        assert api.calls == [None]


class TestTask2CleanLines:
    def test_strips_and_skips(self):
        lines = ["a\n", "   \n", "  # comment\n", "  b  \n", "c # not a comment\n", "\n"]
        assert list(clean_lines(lines)) == ["a", "b", "c # not a comment"]

    def test_is_a_generator(self):
        assert inspect.isgenerator(clean_lines([]))

    def test_is_lazy(self):
        source = Tracked(["# header", "first", "second", "third"])
        gen = clean_lines(source)
        assert next(gen) == "first"
        assert source.pulled == 2

    def test_works_with_a_real_file(self, tmp_path):
        path = tmp_path / "data.txt"
        path.write_text("x\n\n# c\ny\n")
        with path.open() as f:
            assert list(clean_lines(f)) == ["x", "y"]


LOG = [
    "# app log\n",
    "2024-05-01T09:00:00 INFO server started\n",
    "2024-05-01T09:05:00 ERROR db timeout after 5s\n",
    "garbage line\n",
    "not-a-date ERROR nope\n",
    "2024-05-01T09:06:00 error lowercase level is skipped\n",
    "\n",
    "2024-05-01T10:00:00 CRITICAL disk full\n",
    "2024-05-01T10:30:00 WARNING slow request\n",
]


class TestTask3Pipeline:
    def test_parse_log_lines(self):
        records = list(parse_log_lines(["2024-05-01T09:05:00 ERROR db timeout after 5s"]))
        assert records == [LogRecord(datetime(2024, 5, 1, 9, 5), "ERROR", "db timeout after 5s")]

    def test_parse_skips_malformed(self):
        records = list(parse_log_lines(LOG))
        assert [r.level for r in records] == ["INFO", "ERROR", "CRITICAL", "WARNING"]

    def test_errors_since(self):
        assert list(errors_since(LOG, datetime(2024, 5, 1))) == ["db timeout after 5s", "disk full"]
        assert list(errors_since(LOG, datetime(2024, 5, 1, 9, 30))) == ["disk full"]

    def test_pipeline_is_lazy(self):
        source = Tracked(LOG)
        result = errors_since(source, datetime(2024, 5, 1))
        assert source.pulled == 0
        assert next(result) == "db timeout after 5s"
        assert source.pulled == 3


class TestTask4IterLeaves:
    def test_nested(self):
        tree = {"db": {"host": "x", "port": 5432, "pool": {"size": 5}}, "debug": False, "tags": ["a"]}
        assert list(iter_leaves(tree)) == [
            ("db.host", "x"),
            ("db.port", 5432),
            ("db.pool.size", 5),
            ("debug", False),
            ("tags", ["a"]),
        ]

    def test_empty_branches_and_prefix(self):
        assert list(iter_leaves({"a": {}, "b": {"c": {}}})) == []
        assert list(iter_leaves({"x": 1}, prefix="root")) == [("root.x", 1)]

    def test_is_lazy(self):
        gen = iter_leaves({"a": 1, "b": 2})
        assert next(gen) == ("a", 1)


class TestTask5Chunked:
    def test_chunks(self):
        assert list(chunked(range(7), 3)) == [[0, 1, 2], [3, 4, 5], [6]]
        assert list(chunked([], 3)) == []

    def test_chunks_are_lists(self):
        assert all(type(c) is list for c in chunked("abcd", 2))

    def test_lazy_on_infinite_input(self):
        source = Tracked(itertools.count())
        chunks = chunked(source, 4)
        assert next(chunks) == [0, 1, 2, 3]
        assert source.pulled == 4

    @pytest.mark.parametrize("size", [0, -2])
    def test_invalid_size_raises_eagerly(self, size):
        with pytest.raises(ValueError):
            chunked([1, 2], size)


def ts(day, hour=12):
    return datetime(2024, 1, day, hour)


class TestTask6DailyTotals:
    def test_groups_consecutive_days(self):
        events = [(ts(1, 9), 10.0), (ts(1, 18), 5.0), (ts(3, 7), 1.5), (ts(3, 8), 1.0)]
        assert daily_totals(events) == [(date(2024, 1, 1), 15.0), (date(2024, 1, 3), 2.5)]

    def test_empty(self):
        assert daily_totals([]) == []

    def test_unsorted_input_raises(self):
        with pytest.raises(ValueError):
            daily_totals([(ts(1), 1.0), (ts(2), 1.0), (ts(1, 23), 1.0)])


class TestTask7BackoffDelays:
    def test_sequence_is_capped(self):
        assert list(itertools.islice(backoff_delays(1, 3, 20), 5)) == [1, 3, 9, 20, 20]

    def test_defaults(self):
        delays = list(itertools.islice(backoff_delays(), 9))
        assert delays[:4] == pytest.approx([0.1, 0.2, 0.4, 0.8])
        assert delays[-1] == 10.0

    def test_is_infinite(self):
        assert sum(1 for _ in zip(range(1000), backoff_delays())) == 1000

    @pytest.mark.parametrize("kwargs", [{"base": 0}, {"factor": 0.5}, {"base": 5, "max_delay": 1}])
    def test_invalid_parameters_raise_eagerly(self, kwargs):
        with pytest.raises(ValueError):
            backoff_delays(**kwargs)


class TestTask8Interleave:
    def test_round_robin(self):
        assert list(interleave("ab", [1, 2, 3], "X")) == ["a", 1, "X", "b", 2, 3]

    def test_keeps_none_items(self):
        assert list(interleave([None, None], [0])) == [None, 0, None]

    def test_works_with_infinite_inputs(self):
        assert list(itertools.islice(interleave(itertools.count(), "ab"), 6)) == [0, "a", 1, "b", 2, 3]

    def test_no_inputs(self):
        assert list(interleave()) == []


class TestTask9RunningAverage:
    def test_send(self):
        avg = running_average()
        assert next(avg) is None
        assert avg.send(10) == 10.0
        assert avg.send(20) == 15.0
        assert avg.send(None) == 15.0
        assert avg.send(0) == 10.0

    def test_next_without_values(self):
        avg = running_average()
        next(avg)
        assert next(avg) is None

    def test_independent_generators(self):
        a, b = running_average(), running_average()
        next(a)
        next(b)
        a.send(100)
        assert b.send(1) == 1.0
