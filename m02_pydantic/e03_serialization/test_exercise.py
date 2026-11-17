import json
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from typing import Literal
from uuid import UUID

import pytest
from pydantic import BaseModel, Field, ValidationError

from m02_pydantic.e03_serialization.exercise import (
    ApiError,
    Cart,
    CartLine,
    Event,
    ExternalUser,
    Invoice,
    LoginSession,
    ProductOut,
    Profile,
    UserPatch,
    UserProfile,
    UserRecord,
    apply_patch,
    public_view,
    to_json_dict,
    tool_spec,
)

INVOICE_ID = UUID("12345678-1234-5678-1234-567812345678")


class TestTask1ToJsonDict:
    def test_types_become_json_friendly(self):
        inv = Invoice(id=INVOICE_ID, issued_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC), amount=Decimal("12.50"))
        assert to_json_dict(inv) == {
            "id": "12345678-1234-5678-1234-567812345678",
            "issued_at": "2026-01-02T03:04:05Z",
            "amount": "12.50",
            "currency": "EUR",
            "tags": [],
        }

    def test_none_dropped_falsy_kept(self):
        inv = Invoice(id=INVOICE_ID, issued_at=datetime(2026, 1, 2), amount=0, notes="", paid_at=None)
        data = to_json_dict(inv)
        assert "paid_at" not in data
        assert data["notes"] == "" and data["amount"] == "0"

    def test_result_is_json_encodable(self):
        inv = Invoice(
            id=INVOICE_ID,
            issued_at=datetime(2026, 1, 2, tzinfo=UTC),
            amount="1.5",
            paid_at=datetime(2026, 1, 3, tzinfo=UTC),
            tags=["b2b"],
        )
        assert json.loads(json.dumps(to_json_dict(inv)))["paid_at"] == "2026-01-03T00:00:00Z"


class TestTask2ApplyPatch:
    def test_unsent_fields_unchanged(self):
        user = UserProfile(id=1, name="Ada", bio="math", age=36)
        patched = apply_patch(user, UserPatch.model_validate({"age": 37}))
        assert patched == UserProfile(id=1, name="Ada", bio="math", age=37)

    def test_explicit_null_is_applied(self):
        user = UserProfile(id=1, name="Ada", bio="math", age=36)
        patched = apply_patch(user, UserPatch.model_validate({"bio": None}))
        assert patched.bio is None and patched.age == 36

    def test_empty_patch_and_original_unchanged(self):
        user = UserProfile(id=1, name="Ada", bio="math", age=36)
        patched = apply_patch(user, UserPatch())
        assert patched == user and patched is not user
        apply_patch(user, UserPatch(name="Grace"))
        assert user.name == "Ada"


def make_record() -> UserRecord:
    return UserRecord(
        id=7,
        email="ada@example.com",
        password_hash="$argon2id$...",
        profile=Profile(display_name="Ada", internal_notes="VIP, refund twice"),
        sessions=[LoginSession(token="t1", ip="10.0.0.1"), LoginSession(token="t2", ip="10.0.0.2")],
    )


class TestTask3PublicView:
    def test_exact_output(self):
        assert public_view(make_record()) == {
            "id": 7,
            "email": "ada@example.com",
            "profile": {"display_name": "Ada"},
            "sessions": [{"ip": "10.0.0.1"}, {"ip": "10.0.0.2"}],
        }

    def test_no_secret_anywhere(self):
        dumped = json.dumps(public_view(make_record()))
        assert "argon2" not in dumped and "VIP" not in dumped and '"t1"' not in dumped
        assert "10.0.0.2" in dumped

    def test_no_sessions(self):
        record = make_record().model_copy(update={"sessions": []})
        assert public_view(record)["sessions"] == []


class TestTask4ExternalUser:
    @pytest.mark.parametrize("id_key", ["id", "userId", "user_id"])
    def test_id_alias_choices(self, id_key):
        user = ExternalUser.model_validate({id_key: "5", "fullName": "Ada L", "email": "a@x.io"})
        assert user.user_id == 5 and user.full_name == "Ada L"

    def test_nested_alias_path(self):
        user = ExternalUser.model_validate({"id": 1, "fullName": "A", "email": "a@x.io", "permissions": {"admin": True}})
        assert user.is_admin is True
        assert ExternalUser.model_validate({"id": 1, "fullName": "A", "email": "a@x.io"}).is_admin is False

    def test_full_name_only_via_alias(self):
        with pytest.raises(ValidationError) as exc_info:
            ExternalUser.model_validate({"id": 1, "full_name": "A", "email": "a@x.io"})
        assert [(e["loc"], e["type"]) for e in exc_info.value.errors()] == [(("fullName",), "missing")]

    def test_dump_by_alias_and_by_name(self):
        user = ExternalUser.model_validate({"userId": 1, "fullName": "A", "email": "a@x.io"})
        assert user.model_dump(by_alias=True) == {"user_id": 1, "fullName": "A", "emailAddress": "a@x.io", "is_admin": False}
        assert user.model_dump() == {"user_id": 1, "full_name": "A", "email": "a@x.io", "is_admin": False}


class TestTask5CamelModel:
    def test_accepts_camel_and_snake(self):
        a = ProductOut.model_validate({"productId": 1, "displayName": "Pen", "unitPriceCents": 150})
        b = ProductOut(product_id=1, display_name="Pen", unit_price_cents=150)
        assert a == b and a.unit_price_cents == 150

    def test_dumps_camel_by_default(self):
        p = ProductOut(product_id=1, display_name="Pen", unit_price_cents=150)
        assert p.model_dump() == {"productId": 1, "displayName": "Pen", "unitPriceCents": 150, "isActive": True}
        assert p.model_dump_json() == '{"productId":1,"displayName":"Pen","unitPriceCents":150,"isActive":true}'

    def test_snake_on_request(self):
        p = ProductOut(product_id=1, display_name="Pen", unit_price_cents=150, is_active=False)
        assert p.model_dump(by_alias=False)["is_active"] is False

    def test_schema_uses_aliases(self):
        assert set(ProductOut.model_json_schema()["properties"]) == {"productId", "displayName", "unitPriceCents", "isActive"}


class TestTask6Cart:
    def test_computed_values(self):
        cart = Cart(lines=[CartLine(sku="A", quantity=2, unit_price_cents=150), {"sku": "B", "quantity": 1, "unit_price_cents": 1000}])
        assert (cart.item_count, cart.subtotal_cents, cart.total_cents) == (3, 1300, 1300)
        assert cart.lines[0].line_total_cents == 300

    def test_in_dump(self):
        cart = Cart(lines=[CartLine(sku="A", quantity=2, unit_price_cents=150)], discount_cents=100)
        assert cart.model_dump() == {
            "lines": [{"sku": "A", "quantity": 2, "unit_price_cents": 150, "line_total_cents": 300}],
            "discount_cents": 100,
            "item_count": 2,
            "subtotal_cents": 300,
            "total_cents": 200,
        }

    def test_total_never_negative_and_empty_cart(self):
        assert Cart(lines=[CartLine(sku="A", quantity=1, unit_price_cents=50)], discount_cents=100).total_cents == 0
        assert Cart().model_dump()["total_cents"] == 0

    def test_schema_only_in_serialization_mode(self):
        out = Cart.model_json_schema(mode="serialization")["properties"]
        assert out["total_cents"]["readOnly"] is True and out["total_cents"]["type"] == "integer"
        assert "total_cents" not in Cart.model_json_schema(mode="validation")["properties"]


class TestTask7Event:
    def test_json_output(self):
        e = Event(name="standup", starts_at="2026-03-01T10:00:00+02:00", duration=900, tags={"b", "a"})
        assert e.model_dump_json() == '{"name":"standup","starts_at":"2026-03-01T08:00:00Z","duration":900,"tags":["a","b"]}'

    def test_python_mode_keeps_datetime(self):
        starts = datetime(2026, 3, 1, 10, 0, tzinfo=timezone(timedelta(hours=2)))
        data = Event(name="x", starts_at=starts, duration=timedelta(minutes=90)).model_dump()
        assert data["starts_at"] == starts and isinstance(data["starts_at"], datetime)
        assert data["duration"] == 5400 and data["tags"] == []

    def test_naive_and_microseconds(self):
        e = Event(name="x", starts_at=datetime(2026, 3, 1, 8, 0, 0, 123456), duration=timedelta(seconds=1.9))
        data = e.model_dump(mode="json")
        assert data["starts_at"] == "2026-03-01T08:00:00Z"
        assert data["duration"] == 1


class TestTask8ApiError:
    def test_envelope_without_details(self):
        assert ApiError(code="not_found", message="No such user").model_dump() == {
            "error": {"code": "not_found", "message": "No such user"}
        }

    def test_envelope_with_details_json(self):
        err = ApiError(code="invalid", message="Bad", details={"field": "age"}, status_code=422)
        assert err.model_dump_json() == '{"error":{"code":"invalid","message":"Bad","details":{"field":"age"}}}'

    def test_status_code_kept_on_model(self):
        err = ApiError(code="c", message="m", status_code=409)
        assert err.status_code == 409
        assert "status_code" not in json.dumps(err.model_dump())


class _Filters(BaseModel):
    team: str
    since_days: int = 30


class SearchDocuments(BaseModel):
    """Search the knowledge base."""

    query: str = Field(description="Full-text query")
    top_k: int = Field(default=5, ge=1, le=50)
    source: Literal["wiki", "tickets"] = "wiki"


class SearchTickets(BaseModel):
    query: str
    filters: _Filters | None = None


class TestTask9ToolSpec:
    def test_name_description_required(self):
        spec = tool_spec(SearchDocuments)
        assert spec["name"] == "search_documents"
        assert spec["description"] == "Search the knowledge base."
        assert spec["parameters"]["type"] == "object"
        assert spec["parameters"]["required"] == ["query"]

    def test_properties_from_schema(self):
        props = tool_spec(SearchDocuments)["parameters"]["properties"]
        assert props["query"]["description"] == "Full-text query"
        assert (props["top_k"]["minimum"], props["top_k"]["maximum"], props["top_k"]["default"]) == (1, 50, 5)
        assert props["source"]["enum"] == ["wiki", "tickets"]

    def test_defs_only_when_needed(self):
        assert "$defs" not in tool_spec(SearchDocuments)["parameters"]
        spec = tool_spec(SearchTickets)
        assert spec["description"] == ""
        assert set(spec["parameters"]["$defs"]["_Filters"]["properties"]) == {"team", "since_days"}
        assert json.dumps(spec)  # serializable as-is
