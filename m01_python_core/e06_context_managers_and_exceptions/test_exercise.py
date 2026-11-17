import json
from contextlib import contextmanager

import pytest

from m01_python_core.e06_context_managers_and_exceptions.exercise import (
    AppError,
    Catch,
    ConflictError,
    InvalidInputError,
    NotFoundError,
    Timer,
    acquire_all,
    count_failures,
    delete_quietly,
    error_response,
    parse_ints,
    parse_payload,
    run_all,
    temporary_env,
    transaction,
)


class Boom(Exception):
    """A test-only error. (Never use RuntimeError here: NotImplementedError subclasses it.)"""


class TestTask1ExceptionHierarchy:
    def test_base_error(self):
        err = AppError("boom", details={"k": 1})
        assert str(err) == "boom"
        assert err.to_dict() == {"code": "app_error", "message": "boom", "details": {"k": 1}}
        assert AppError("x").details == {}

    @pytest.mark.parametrize(
        ("cls", "code", "status"),
        [(NotFoundError, "not_found", 404), (InvalidInputError, "invalid_input", 422), (ConflictError, "conflict", 409)],
    )
    def test_subclasses(self, cls, code, status):
        err = cls("nope")
        assert isinstance(err, AppError)
        assert (err.code, err.status_code) == (code, status)
        assert err.to_dict()["code"] == code

    def test_details_are_copied(self):
        details = {"id": 1}
        err = NotFoundError("missing", details=details)
        details["id"] = 2
        assert err.details == {"id": 1}

    def test_error_response(self):
        assert error_response(NotFoundError("user 7 not found")) == (
            404,
            {"code": "not_found", "message": "user 7 not found", "details": {}},
        )

    def test_error_response_hides_unexpected_errors(self):
        status, body = error_response(RuntimeError("password=hunter2"))
        assert status == 500
        assert body["code"] == "internal_error"
        assert "hunter2" not in json.dumps(body)


class TestTask2RaiseFrom:
    def test_valid(self):
        assert parse_payload('{"id": 1, "name": "x"}') == {"id": 1, "name": "x"}
        assert parse_payload(b'{"id": 2}') == {"id": 2}

    def test_malformed_json_is_chained(self):
        with pytest.raises(InvalidInputError) as info:
            parse_payload('{"id": ')
        assert info.value.message == "malformed JSON"
        assert isinstance(info.value.__cause__, json.JSONDecodeError)
        assert info.value.details == {"position": info.value.__cause__.pos}

    def test_not_an_object(self):
        with pytest.raises(InvalidInputError, match="must be a JSON object"):
            parse_payload("[1, 2]")

    def test_missing_id_suppresses_key_error_context(self):
        with pytest.raises(InvalidInputError, match="missing field: id") as info:
            parse_payload('{"name": "x"}')
        assert info.value.__cause__ is None
        assert info.value.__suppress_context__ is True


class TestTask3TemporaryEnv:
    def test_sets_and_restores(self):
        env = {"MODE": "prod", "KEEP": "1"}
        with temporary_env(env, MODE="test", DEBUG="1") as inside:
            assert inside is env
            assert env == {"MODE": "test", "KEEP": "1", "DEBUG": "1"}
        assert env == {"MODE": "prod", "KEEP": "1"}

    def test_none_removes_key_temporarily(self):
        env = {"TOKEN": "secret"}
        with temporary_env(env, TOKEN=None, ABSENT=None):
            assert env == {}
        assert env == {"TOKEN": "secret"}

    def test_restores_on_error(self):
        env = {"MODE": "prod"}
        with pytest.raises(Boom):
            with temporary_env(env, MODE="test", NEW="x"):
                raise Boom
        assert env == {"MODE": "prod"}

    def test_untouched_keys_changed_inside_are_kept(self):
        env = {}
        with temporary_env(env, A="1"):
            env["B"] = "2"
        assert env == {"B": "2"}


def fake_clock(*times):
    it = iter(times)
    return lambda: next(it)


class TestTask4Timer:
    def test_measures_with_injected_clock(self):
        t = Timer(clock=fake_clock(10.0, 12.5))
        assert t.elapsed is None
        with t as same:
            assert same is t
        assert t.elapsed == 2.5

    def test_does_not_suppress_and_still_measures(self):
        t = Timer(clock=fake_clock(1.0, 4.0))
        with pytest.raises(ValueError):
            with t:
                raise ValueError
        assert t.elapsed == 3.0

    def test_reusable(self):
        t = Timer(clock=fake_clock(0.0, 1.0, 5.0, 7.0))
        with t:
            pass
        with t:
            assert t.elapsed is None
        assert t.elapsed == 2.0

    def test_as_decorator(self):
        t = Timer(clock=fake_clock(0.0, 0.25))

        @t
        def work(x):
            return x * 2

        assert work(21) == 42
        assert t.elapsed == 0.25

    def test_real_clock(self):
        with Timer() as t:
            sum(range(1000))
        assert 0 <= t.elapsed < 1


class TestTask5Catch:
    def test_catches_listed_types_and_subclasses(self):
        with Catch(LookupError) as caught:
            {}["missing"]
        assert isinstance(caught.exception, KeyError)

    def test_nothing_raised(self):
        with Catch(ValueError) as caught:
            pass
        assert caught.exception is None

    def test_other_exceptions_propagate(self):
        with pytest.raises(TypeError):
            with Catch(ValueError, KeyError):
                raise TypeError("not mine")

    def test_requires_types(self):
        with pytest.raises(TypeError):
            Catch()


class TestTask6Suppress:
    def test_delete_quietly(self, tmp_path):
        path = tmp_path / "f.txt"
        path.write_text("x")
        assert delete_quietly(path) is True
        assert not path.exists()
        assert delete_quietly(path) is False

    def test_delete_quietly_other_errors_propagate(self, tmp_path):
        with pytest.raises(OSError):
            delete_quietly(tmp_path)  # a directory, not a file

    def test_parse_ints(self):
        assert parse_ints(["1", "x", " 2 ", "3.5", "-4"]) == [1, 2, -4]
        assert parse_ints([]) == []


class Resource:
    def __init__(self, name, log, fail_on_enter=False):
        self.name, self.log, self.fail_on_enter = name, log, fail_on_enter

    def __enter__(self):
        if self.fail_on_enter:
            raise ConnectionError(self.name)
        self.log.append(f"open {self.name}")
        return self.name.upper()

    def __exit__(self, *exc_info):
        self.log.append(f"close {self.name}")
        return False


class TestTask7AcquireAll:
    def test_enters_in_order_and_exits_in_reverse(self):
        log = []
        factories = [lambda n=n: Resource(n, log) for n in "abc"]
        with acquire_all(factories) as values:
            assert values == ["A", "B", "C"]
            log.append("body")
        assert log == ["open a", "open b", "open c", "body", "close c", "close b", "close a"]

    def test_failure_while_entering_cleans_up(self):
        log = []
        factories = [lambda: Resource("a", log), lambda: Resource("b", log), lambda: Resource("c", log, True)]
        with pytest.raises(ConnectionError):
            with acquire_all(factories):
                log.append("body")  # never reached
        assert log == ["open a", "open b", "close b", "close a"]

    def test_body_error_exits_all(self):
        log = []
        with pytest.raises(KeyError):
            with acquire_all([lambda: Resource("a", log)]):
                raise KeyError
        assert log == ["open a", "close a"]

    def test_works_with_generator_based_managers(self):
        events = []

        @contextmanager
        def cm(n):
            events.append(n)
            yield n
            events.append(-n)

        with acquire_all([lambda: cm(1), lambda: cm(2)]) as values:
            assert values == [1, 2]
        assert events == [1, 2, -2, -1]


class TestTask8Transaction:
    def test_commit(self):
        store = {"balance": 10}
        with transaction(store) as tx:
            assert tx is store
            store["balance"] -= 3
        assert store == {"balance": 7}

    def test_rollback_restores_in_place_including_nested(self):
        store = {"balance": 10, "history": [1, 2], "meta": {"v": 1}}
        same = store
        with pytest.raises(Boom):
            with transaction(store):
                store["balance"] = 0
                store["history"].append(3)
                store["meta"]["v"] = 2
                del store["meta"]
                store["new"] = True
                raise Boom("payment failed")
        assert same is store
        assert store == {"balance": 10, "history": [1, 2], "meta": {"v": 1}}

    def test_rollback_on_base_exception(self):
        store = {"x": 1}
        with pytest.raises(KeyboardInterrupt):
            with transaction(store):
                store["x"] = 2
                raise KeyboardInterrupt
        assert store == {"x": 1}


class TestTask9ExceptionGroups:
    def test_run_all_success(self):
        assert run_all({"a": lambda: 1, "b": lambda: 2}) == {"a": 1, "b": 2}

    def test_run_all_collects_every_failure(self):
        calls = []

        def ok():
            calls.append("ok")
            return 1

        def bad_value():
            raise ValueError("bad")

        def bad_key():
            raise KeyError("k")

        with pytest.raises(ExceptionGroup) as info:
            run_all({"v": bad_value, "ok": ok, "k": bad_key})
        group = info.value
        assert calls == ["ok"]
        assert str(group) == "2 of 3 job(s) failed (2 sub-exceptions)"
        assert [type(e) for e in group.exceptions] == [ValueError, KeyError]
        assert group.exceptions[0].__notes__ == ["job: v"]

    def test_count_failures(self):
        def many():
            raise ExceptionGroup("x", [ValueError(1), KeyError(2), ValueError(3), UnicodeDecodeError("utf-8", b"", 0, 1, "r")])

        assert count_failures(many) == {"ValueError": 3, "KeyError": 1}

    def test_count_failures_plain_and_none(self):
        def plain():
            raise ValueError("single")

        assert count_failures(plain) == {"ValueError": 1}
        assert count_failures(lambda: None) == {}

    def test_count_failures_reraises_unhandled(self):
        def mixed():
            raise ExceptionGroup("x", [ValueError(1), TypeError(2)])

        with pytest.raises(ExceptionGroup) as info:
            count_failures(mixed)
        assert [type(e) for e in info.value.exceptions] == [TypeError]
