import json
from decimal import Decimal

import pytest
from pydantic import BaseModel, TypeAdapter, ValidationError

from m02_pydantic.e04_advanced_types.exercise import (
    AgentTurn,
    ApiResponse,
    Category,
    ErrorEvent,
    MoneyCents,
    Page,
    Priority,
    SemVer,
    Shipment,
    ShipmentStatus,
    Tags,
    TextChunk,
    ToolCall,
    dump_events,
    paginate,
    parse_events,
    parse_stock,
)


def errors_of(exc_info: pytest.ExceptionInfo[ValidationError]) -> list[tuple[tuple, str]]:
    return [(e["loc"], e["type"]) for e in exc_info.value.errors()]


class TestTask1Shipment:
    def test_enum_coercion_and_defaults(self):
        s = Shipment(id="s1", status="paid", priority="3")
        assert s.status is ShipmentStatus.PAID and s.priority is Priority.HIGH
        d = Shipment(id="s2")
        assert (d.status, d.priority) == (ShipmentStatus.PENDING, Priority.NORMAL)

    def test_invalid_enum_value(self):
        with pytest.raises(ValidationError) as exc_info:
            Shipment(id="s1", status="lost", priority=9)
        assert errors_of(exc_info) == [(("status",), "enum"), (("priority",), "enum")]

    def test_json_uses_values(self):
        assert Shipment(id="s1", status=ShipmentStatus.SHIPPED).model_dump(mode="json") == {
            "id": "s1",
            "status": "shipped",
            "priority": 2,
        }

    def test_advance_allowed(self):
        s = Shipment(id="s1")
        paid = s.advance(ShipmentStatus.PAID)
        assert paid.status is ShipmentStatus.PAID and s.status is ShipmentStatus.PENDING
        assert paid.advance("shipped").status is ShipmentStatus.SHIPPED

    def test_advance_forbidden(self):
        with pytest.raises(ValueError, match="cannot go from pending to delivered"):
            Shipment(id="s1").advance("delivered")
        with pytest.raises(ValueError):
            Shipment(id="s1", status="cancelled").advance("paid")


TURN = {
    "events": [
        {"type": "text", "text": "Let me "},
        {"type": "tool_call", "id": "c1", "name": "search", "arguments": {"q": "pydantic"}},
        {"type": "text", "text": "check."},
        {"type": "error", "message": "rate limited", "retryable": True},
    ]
}


class TestTask2DiscriminatedUnion:
    def test_each_event_gets_its_model(self):
        turn = AgentTurn.model_validate(TURN)
        assert [type(e) for e in turn.events] == [TextChunk, ToolCall, TextChunk, ErrorEvent]
        assert turn.events[3].retryable is True

    def test_text_and_tool_calls(self):
        turn = AgentTurn.model_validate(TURN)
        assert turn.text() == "Let me check."
        [call] = turn.tool_calls()
        assert (call.name, call.arguments) == ("search", {"q": "pydantic"})

    def test_unknown_and_missing_tag(self):
        with pytest.raises(ValidationError) as exc_info:
            AgentTurn.model_validate({"events": [{"type": "image", "url": "x"}, {"text": "no tag"}]})
        assert errors_of(exc_info) == [(("events", 0), "union_tag_invalid"), (("events", 1), "union_tag_not_found")]

    def test_error_located_under_tag(self):
        with pytest.raises(ValidationError) as exc_info:
            AgentTurn.model_validate({"events": [{"type": "text", "text": "a"}, {"type": "tool_call", "id": "c1"}]})
        assert errors_of(exc_info) == [(("events", 1, "tool_call", "name"), "missing")]

    def test_default_tags(self):
        assert ToolCall(id="c", name="n").model_dump() == {"type": "tool_call", "id": "c", "name": "n", "arguments": {}}
        assert AgentTurn(events=[TextChunk(text="hi")]).text() == "hi"


class _User(BaseModel):
    name: str


class TestTask3Page:
    def test_items_validated_as_type(self):
        page = Page[_User].model_validate({"items": [{"name": "ada"}], "total": 1, "page": 1, "size": 10})
        assert isinstance(page.items[0], _User)
        assert Page[int](items=["1", 2], total=2, page=1, size=2).items == [1, 2]

    def test_item_errors(self):
        with pytest.raises(ValidationError) as exc_info:
            Page[int](items=[1, "x"], total=2, page=0, size=2)
        assert errors_of(exc_info) == [(("items", 1), "int_parsing"), (("page",), "greater_than_equal")]

    @pytest.mark.parametrize(
        ("total", "page", "size", "pages", "has_next"),
        [(0, 1, 10, 0, False), (10, 1, 10, 1, False), (11, 1, 10, 2, True), (11, 2, 10, 2, False)],
    )
    def test_computed_fields(self, total, page, size, pages, has_next):
        p = Page[int](items=[], total=total, page=page, size=size)
        assert (p.pages, p.has_next) == (pages, has_next)
        assert p.model_dump()["pages"] == pages

    def test_paginate(self):
        letters = list("abcde")
        assert paginate(letters, 1, 2).items == ["a", "b"]
        last = paginate(letters, 3, 2)
        assert (last.items, last.total, last.pages, last.has_next) == (["e"], 5, 3, False)
        assert paginate(letters, 4, 2).items == []

    @pytest.mark.parametrize(("page", "size"), [(0, 2), (1, 0)])
    def test_paginate_invalid(self, page, size):
        with pytest.raises(ValueError):
            paginate([1, 2, 3], page, size)


class TestTask4ApiResponse:
    def test_success_validates_data(self):
        r = ApiResponse[int].success("5")
        assert (r.ok, r.data, r.error) == (True, 5, None)
        users = ApiResponse[list[_User]].success([{"name": "ada"}])
        assert isinstance(users.data[0], _User)

    def test_failure(self):
        r = ApiResponse[int].failure("boom")
        assert (r.ok, r.data, r.error) == (False, None, "boom")

    @pytest.mark.parametrize(
        ("payload", "message"),
        [
            ({"ok": True, "data": 1, "error": "x"}, "successful response cannot have an error"),
            ({"ok": False}, "failed response needs an error"),
            ({"ok": False, "data": 1, "error": "x"}, "failed response cannot have data"),
        ],
    )
    def test_consistency_rules(self, payload, message):
        with pytest.raises(ValidationError) as exc_info:
            ApiResponse[int].model_validate(payload)
        assert message in exc_info.value.errors()[0]["msg"]

    def test_wrong_data_type(self):
        with pytest.raises(ValidationError) as exc_info:
            ApiResponse[int].model_validate_json('{"ok": true, "data": "five"}')
        assert errors_of(exc_info) == [(("data",), "int_parsing")]


class TestTask5TypeAdapter:
    def test_parse_events(self):
        events = parse_events(json.dumps(TURN["events"]))
        assert [type(e) for e in events] == [TextChunk, ToolCall, TextChunk, ErrorEvent]
        assert parse_events(b"[]") == []

    def test_parse_events_errors(self):
        with pytest.raises(ValidationError) as exc_info:
            parse_events('[{"type": "nope"}]')
        assert errors_of(exc_info) == [((0,), "union_tag_invalid")]
        with pytest.raises(ValidationError):
            parse_events("not json")

    def test_dump_round_trip(self):
        events = [TextChunk(text="hi"), ToolCall(id="1", name="f", arguments={"x": 1})]
        raw = dump_events(events)
        assert isinstance(raw, bytes)
        assert json.loads(raw)[1] == {"type": "tool_call", "id": "1", "name": "f", "arguments": {"x": 1}}
        assert parse_events(raw) == events

    def test_parse_stock(self):
        assert parse_stock({"A": "3", "B": 0}) == {"A": 3, "B": 0}
        with pytest.raises(ValidationError) as exc_info:
            parse_stock({"A": 1, "B": -1})
        assert errors_of(exc_info) == [(("B",), "greater_than_equal")]


class TestTask6Tags:
    def test_normalised(self):
        assert Tags(["Python", " pydantic ", "python", ""]).root == ["python", "pydantic"]

    def test_from_comma_string_and_json(self):
        assert Tags("FastAPI, , sqlalchemy").root == ["fastapi", "sqlalchemy"]
        assert Tags.model_validate_json('["A", "a", "B"]').root == ["a", "b"]

    def test_dump_has_no_wrapper(self):
        tags = Tags(["Python", "Pydantic"])
        assert tags.model_dump() == ["python", "pydantic"]
        assert tags.model_dump_json() == '["python","pydantic"]'

    def test_container_protocol(self):
        tags = Tags(["Python", "Pydantic"])
        assert list(tags) == ["python", "pydantic"]
        assert len(tags) == 2
        assert " PYTHON " in tags and "django" not in tags

    def test_inside_another_model(self):
        class Post(BaseModel):
            tags: Tags

        assert Post(tags="A,b").model_dump() == {"tags": ["a", "b"]}


TREE = {
    "name": "root",
    "children": [
        {"name": "books", "children": [{"name": "python"}, {"name": "rust"}]},
        {"name": "music", "children": [{"name": "jazz", "children": [{"name": "bebop"}]}]},
    ],
}


class TestTask7Category:
    def test_nested_validation(self):
        tree = Category.model_validate(TREE)
        assert isinstance(tree.children[1].children[0], Category)
        assert Category(name="leaf").children == []

    def test_walk_preorder(self):
        assert list(Category.model_validate(TREE).walk()) == ["root", "books", "python", "rust", "music", "jazz", "bebop"]

    def test_depth(self):
        assert Category.model_validate(TREE).depth() == 4
        assert Category(name="leaf").depth() == 1

    def test_find(self):
        tree = Category.model_validate(TREE)
        assert tree.find("jazz").children[0].name == "bebop"
        assert tree.find("root") is tree
        assert tree.find("metal") is None

    def test_error_path_into_tree(self):
        bad = {"name": "root", "children": [{"name": "a", "children": [{"name": "ok"}, {"name": ""}]}]}
        with pytest.raises(ValidationError) as exc_info:
            Category.model_validate(bad)
        assert errors_of(exc_info) == [(("children", 0, "children", 1, "name"), "string_too_short")]


class TestTask8MoneyCents:
    @pytest.mark.parametrize(
        ("raw", "cents"),
        [("12.34", 1234), (12.34, 1234), (Decimal("12.34"), 1234), (12, 1200), ("12", 1200), ("-0.5", -50), (0.1, 10)],
    )
    def test_parse(self, raw, cents):
        assert TypeAdapter(MoneyCents).validate_python(raw) == cents

    @pytest.mark.parametrize(
        ("raw", "message"),
        [("abc", "invalid amount"), (True, "invalid amount"), ([1], "invalid amount"), ("1.234", "at most 2 decimal places")],
    )
    def test_invalid(self, raw, message):
        with pytest.raises(ValidationError) as exc_info:
            TypeAdapter(MoneyCents).validate_python(raw)
        assert message in exc_info.value.errors()[0]["msg"]

    def test_serialize(self):
        class Price(BaseModel):
            amount: MoneyCents

        assert Price(amount="12.34").amount == 1234
        assert Price(amount=-0.5).model_dump() == {"amount": "-0.50"}
        assert Price(amount=0).model_dump_json() == '{"amount":"0.00"}'

    def test_json_schema(self):
        assert TypeAdapter(MoneyCents).json_schema() == {
            "type": "string",
            "pattern": r"^-?\d+(\.\d{1,2})?$",
            "examples": ["12.34"],
        }


def make_release_model() -> type[BaseModel]:
    class Release(BaseModel):
        name: str
        version: SemVer

    return Release


class TestTask9SemVer:
    def test_validates_strings_and_instances(self):
        release_cls = make_release_model()
        assert release_cls(name="a", version="v1.10.0").version == SemVer(1, 10, 0)
        v = SemVer(2, 0, 1)
        assert release_cls(name="b", version=v).version is v

    def test_json_input_and_ordering(self):
        release_cls = make_release_model()
        r = release_cls.model_validate_json('{"name": "x", "version": "1.10.0"}')
        assert r.version > SemVer.parse("1.9.9")

    @pytest.mark.parametrize("bad", ["1.2", "one.two.three", 123, None])
    def test_rejects_invalid(self, bad):
        with pytest.raises(ValidationError):
            make_release_model()(name="x", version=bad)

    def test_parse_error_is_value_error(self):
        with pytest.raises(ValidationError) as exc_info:
            make_release_model().model_validate_json('{"name": "x", "version": "1.2"}')
        assert [e["type"] for e in exc_info.value.errors()] == ["value_error"]
        assert "invalid semantic version" in exc_info.value.errors()[0]["msg"]

    def test_serialization_and_schema(self):
        release_cls = make_release_model()
        r = release_cls(name="x", version="v1.4.2")
        assert r.model_dump() == {"name": "x", "version": "1.4.2"}
        assert r.model_dump_json() == '{"name":"x","version":"1.4.2"}'
        for mode in ("validation", "serialization"):
            assert release_cls.model_json_schema(mode=mode)["properties"]["version"]["type"] == "string"
