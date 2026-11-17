import inspect
from collections.abc import Hashable
from dataclasses import dataclass
from typing import TypeAliasType, TypeGuard, get_args, get_overloads, get_type_hints

import pytest

from m01_python_core.e07_typing.exercise import (
    HasId,
    InMemoryRepository,
    JsonScalar,
    Retriever,
    TypeIs,
    coerce,
    index_by,
    is_json_scalar,
    is_str_list,
    logged,
    retrieve_all,
    with_session,
)
from m01_python_core.e07_typing.messages import ChatMessage, Role, ToolCall, validate_message


class KeywordIndex:
    def __init__(self, docs):
        self.docs = docs
        self.calls = []

    def retrieve(self, query, k=4):
        self.calls.append((query, k))
        return [d for d in self.docs if query in d][:k]


class NotARetriever:
    def search(self, query):
        return ["never"]


class TestTask1Protocol:
    def test_structural_isinstance(self):
        assert isinstance(KeywordIndex([]), Retriever)
        assert not isinstance(NotARetriever(), Retriever)
        assert not isinstance("text", Retriever)

    def test_no_inheritance_needed(self):
        assert Retriever not in KeywordIndex.__mro__
        assert isinstance(KeywordIndex([]), Retriever)

    def test_retrieve_all_merges_dedupes_and_limits(self):
        a = KeywordIndex(["cat food", "cat toys"])
        b = KeywordIndex(["cat toys", "cat tree", "dog"])
        result = retrieve_all([a, NotARetriever(), b], "cat", k=3)
        assert result == ["cat food", "cat toys", "cat tree"]
        assert a.calls == [("cat", 3)] and b.calls == [("cat", 3)]

    def test_retrieve_all_with_no_retrievers(self):
        assert retrieve_all([NotARetriever(), 42], "q") == []


@dataclass
class User:
    id: int
    email: str


class TestTask2GenericRepository:
    def test_type_params(self):
        (t,) = InMemoryRepository.__type_params__
        assert t.__name__ == "T"
        assert t.__bound__ is HasId

    def test_add_get_list_remove(self):
        repo = InMemoryRepository[User]()
        ann = repo.add(User(1, "ann@x.io"))
        repo.add(User(2, "bob@x.io"))
        assert ann.email == "ann@x.io"
        assert repo.get(2) == User(2, "bob@x.io")
        assert repo.get(99) is None
        assert [u.id for u in repo.list()] == [1, 2]
        assert repo.list(where=lambda u: u.email.startswith("b")) == [User(2, "bob@x.io")]
        assert repo.remove(1) is True
        assert repo.remove(1) is False
        assert len(repo) == 1

    def test_duplicate_id(self):
        repo = InMemoryRepository()
        repo.add(User(1, "a"))
        with pytest.raises(ValueError):
            repo.add(User(1, "b"))


class TestTask3GenericFunction:
    def test_type_params(self):
        t, k = index_by.__type_params__
        assert (t.__name__, k.__name__) == ("T", "K")
        assert k.__bound__ is Hashable
        assert t.__bound__ is None

    def test_index_by(self):
        users = [User(1, "ann@x.io"), User(2, "bob@x.io")]
        assert index_by(users, key=lambda u: u.email) == {"ann@x.io": users[0], "bob@x.io": users[1]}
        assert list(index_by(["apple", "bob"], key=len)) == [5, 3]

    def test_duplicate_key(self):
        with pytest.raises(ValueError, match="'b'"):
            index_by(["bob", "bill"], key=lambda s: s[0])


class TestTask4TypedDict:
    def test_role_literal(self):
        assert get_args(Role) == ("system", "user", "assistant", "tool")

    def test_chat_message_keys(self):
        assert ChatMessage.__required_keys__ == {"role", "content"}
        assert ChatMessage.__optional_keys__ == {"name"}
        assert get_type_hints(ChatMessage) == {"role": Role, "content": str, "name": str}

    def test_tool_call_keys(self):
        assert ToolCall.__required_keys__ == {"id", "name"}
        assert ToolCall.__optional_keys__ == {"arguments"}

    def test_validate_valid(self):
        data = {"role": "user", "content": "hi", "name": "ann"}
        result = validate_message(data)
        assert result == data and result is not data
        assert validate_message({"role": "system", "content": "be brief"}) == {"role": "system", "content": "be brief"}

    @pytest.mark.parametrize(
        ("data", "error", "match"),
        [
            ({"content": "hi"}, ValueError, "missing key: role"),
            ({}, ValueError, "missing key: content"),
            ({"role": "user", "content": "hi", "extra": 1}, ValueError, "extra"),
            ({"role": "robot", "content": "hi"}, ValueError, "robot"),
            ({"role": "user", "content": 42}, TypeError, "content"),
            ({"role": "user", "content": "hi", "name": None}, TypeError, "name"),
        ],
    )
    def test_validate_invalid(self, data, error, match):
        with pytest.raises(error, match=match):
            validate_message(data)


class TestTask5Overload:
    def test_has_three_overloads(self):
        overloads = get_overloads(coerce)
        assert len(overloads) == 3
        returns = [get_type_hints(o)["return"] for o in overloads]
        assert returns == [bool, int, float]

    @pytest.mark.parametrize(
        ("value", "to", "expected"),
        [(" 42 ", int, 42), ("2.5", float, 2.5), ("On", bool, True), ("no", bool, False), ("0", bool, False)],
    )
    def test_coerce(self, value, to, expected):
        result = coerce(value, to)
        assert result == expected and type(result) is to

    def test_errors(self):
        with pytest.raises(ValueError):
            coerce("maybe", bool)
        with pytest.raises(ValueError):
            coerce("4.2", int)
        with pytest.raises(TypeError):
            coerce("x", str)


class TestTask6Narrowing:
    def test_is_str_list(self):
        assert is_str_list(["a", "b"]) is True
        assert is_str_list([]) is True
        assert is_str_list(["a", 1]) is False
        assert get_type_hints(is_str_list)["return"] == TypeGuard[list[str]]

    @pytest.mark.parametrize("value", ["", "x", 0, 1.5, True, None])
    def test_is_json_scalar_true(self, value):
        assert is_json_scalar(value) is True

    @pytest.mark.parametrize("value", [[], {}, b"bytes", object(), (1,)])
    def test_is_json_scalar_false(self, value):
        assert is_json_scalar(value) is False

    def test_type_alias_and_hints(self):
        assert is_json_scalar("x") is True
        assert isinstance(JsonScalar, TypeAliasType)
        assert get_type_hints(is_json_scalar)["return"] == TypeIs[JsonScalar]


class TestTask7Logged:
    def test_logs_calls_and_results(self):
        log = []

        @logged(log)
        def add(a, b=0):
            return a + b

        assert add(1, b=2) == 3
        assert add("x", "y") == "xy"
        assert log == ["add(1, b=2) -> 3", "add('x', 'y') -> 'xy'"]

    def test_logs_errors_and_reraises(self):
        log = []

        @logged(log)
        def div(a, b):
            return a / b

        with pytest.raises(ZeroDivisionError):
            div(1, 0)
        assert log == ["div(1, 0) raised ZeroDivisionError"]

    def test_preserves_signature(self):
        def search(query: str, *, k: int = 4) -> list[str]:
            """Search docs."""
            return []

        wrapped = logged([])(search)
        assert inspect.signature(wrapped) == inspect.signature(search)
        assert wrapped.__name__ == "search" and wrapped.__doc__ == "Search docs."


class FakeSession:
    instances = []

    def __init__(self):
        self.closed = False
        FakeSession.instances.append(self)

    def close(self):
        self.closed = True


class TestTask8WithSession:
    def setup_method(self):
        FakeSession.instances.clear()

    def test_injects_and_closes(self):
        @with_session(FakeSession)
        def get_user(session, user_id: int, *, active: bool = True):
            return (session, user_id, active)

        session, user_id, active = get_user(7, active=False)
        assert isinstance(session, FakeSession)
        assert (user_id, active) == (7, False)
        assert session.closed

    def test_new_session_per_call_closed_on_error(self):
        @with_session(FakeSession)
        def fail(session):
            raise KeyError("boom")

        for _ in range(2):
            with pytest.raises(KeyError):
                fail()
        assert len(FakeSession.instances) == 2
        assert all(s.closed for s in FakeSession.instances)

    def test_signature_hides_session(self):
        def get_user(session, user_id: int, *, active: bool = True) -> dict:
            """Load a user."""
            return {}

        wrapped = with_session(FakeSession)(get_user)
        assert list(inspect.signature(wrapped).parameters) == ["user_id", "active"]
        assert inspect.signature(wrapped).return_annotation == inspect.signature(get_user).return_annotation
        assert wrapped.__name__ == "get_user"

