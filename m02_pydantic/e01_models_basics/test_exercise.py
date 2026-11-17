from decimal import Decimal

import pytest
from pydantic import BaseModel, Field, ValidationError, model_validator

from m02_pydantic.e01_models_basics.exercise import (
    Address,
    Order,
    OrderItem,
    Product,
    StrictPayment,
    apply_discount,
    clone_order,
    format_errors,
    parse_order,
    with_changes,
)

ORDER_DATA = {
    "id": 1,
    "shipping_address": {"street": "Khreshchatyk 1", "city": "Kyiv"},
    "items": [
        {"sku": "A", "quantity": 2, "unit_price": "1.25"},
        {"sku": "B", "quantity": 1, "unit_price": 10},
    ],
}


def error_types(exc_info: pytest.ExceptionInfo[ValidationError]) -> list[tuple[tuple, str]]:
    return [(e["loc"], e["type"]) for e in exc_info.value.errors()]


class TestTask1Product:
    def test_defaults(self):
        p = Product(id=1, name="Pen", price=1.5)
        assert (p.in_stock, p.tags, p.description) == (True, [], None)

    def test_required_fields(self):
        with pytest.raises(ValidationError) as exc_info:
            Product(name="Pen")
        assert sorted(loc for loc, _ in error_types(exc_info)) == [("id",), ("price",)]
        assert {t for _, t in error_types(exc_info)} == {"missing"}

    def test_lax_coercion(self):
        p = Product(id="7", name="Pen", price="1.5", in_stock="yes")
        assert p.id == 7 and p.price == 1.5 and p.in_stock is True

    def test_tags_default_is_not_shared(self):
        a, b = Product(id=1, name="a", price=1), Product(id=2, name="b", price=2)
        a.tags.append("sale")
        assert b.tags == []

    def test_uncoercible_value(self):
        with pytest.raises(ValidationError) as exc_info:
            Product(id="seven", name="Pen", price=1)
        assert error_types(exc_info) == [(("id",), "int_parsing")]


class TestTask2StrictPayment:
    def test_accepts_exact_types(self):
        p = StrictPayment(amount_cents=100, currency="EUR")
        assert (p.amount_cents, p.currency, p.captured) == (100, "EUR", False)

    @pytest.mark.parametrize("amount", ["100", 100.0, True])
    def test_rejects_coercible_amounts(self, amount):
        with pytest.raises(ValidationError) as exc_info:
            StrictPayment(amount_cents=amount, currency="EUR")
        assert error_types(exc_info) == [(("amount_cents",), "int_type")]

    @pytest.mark.parametrize("captured", ["true", 1])
    def test_rejects_coercible_bools(self, captured):
        with pytest.raises(ValidationError) as exc_info:
            StrictPayment(amount_cents=1, currency="EUR", captured=captured)
        assert error_types(exc_info) == [(("captured",), "bool_type")]


class TestTask3NestedModels:
    def test_nested_dicts_become_models(self):
        order = Order.model_validate(ORDER_DATA)
        assert isinstance(order.shipping_address, Address)
        assert order.shipping_address.country_code == "UA"
        assert all(isinstance(i, OrderItem) for i in order.items)
        assert order.items[0].unit_price == Decimal("1.25")
        assert order.note is None

    def test_total(self):
        assert Order.model_validate(ORDER_DATA).total() == Decimal("12.50")

    def test_total_of_empty_order(self):
        order = Order(id=2, shipping_address=Address(street="s", city="c"), items=[])
        assert order.total() == Decimal("0")

    def test_error_location_is_full_path(self):
        bad = {**ORDER_DATA, "items": [ORDER_DATA["items"][0], {"sku": "B", "quantity": 0, "unit_price": 1}]}
        with pytest.raises(ValidationError) as exc_info:
            Order.model_validate(bad)
        assert error_types(exc_info) == [(("items", 1, "quantity"), "greater_than_equal")]

    def test_items_are_required(self):
        with pytest.raises(ValidationError) as exc_info:
            Order(id=1, shipping_address={"street": "s", "city": "c"})
        assert error_types(exc_info) == [(("items",), "missing")]


class TestTask4ParseOrder:
    def test_from_json_string(self):
        raw = '{"id": 5, "shipping_address": {"street": "s", "city": "c"}, "items": []}'
        assert parse_order(raw).id == 5

    def test_from_bytes_and_dict(self):
        raw = b'{"id": 6, "shipping_address": {"street": "s", "city": "c"}, "items": []}'
        assert parse_order(raw).id == 6
        assert parse_order(ORDER_DATA).total() == Decimal("12.50")

    def test_invalid_json_is_validation_error(self):
        with pytest.raises(ValidationError) as exc_info:
            parse_order('{"id": 1,')
        assert exc_info.value.errors()[0]["type"] == "json_invalid"

    def test_unsupported_type(self):
        with pytest.raises(TypeError):
            parse_order([("id", 1)])


class _Signup(BaseModel):
    email: str
    age: int = Field(ge=18)
    items: list[int] = []
    password: str = "x"
    confirm: str = "x"

    @model_validator(mode="after")
    def _match(self):
        if self.password != self.confirm:
            raise ValueError("passwords do not match")
        return self


class TestTask5FormatErrors:
    def test_fields_codes_and_messages(self):
        with pytest.raises(ValidationError) as exc_info:
            _Signup.model_validate({"age": "x"})
        assert format_errors(exc_info.value) == [
            {"field": "email", "code": "missing", "message": "Field required"},
            {
                "field": "age",
                "code": "int_parsing",
                "message": "Input should be a valid integer, unable to parse string as an integer",
            },
        ]

    def test_list_index_in_field(self):
        with pytest.raises(ValidationError) as exc_info:
            _Signup.model_validate({"email": "a@b.c", "age": 20, "items": [1, "two"]})
        [error] = format_errors(exc_info.value)
        assert error["field"] == "items.1"
        assert error["code"] == "int_parsing"

    def test_model_level_error_is_root(self):
        with pytest.raises(ValidationError) as exc_info:
            _Signup.model_validate({"email": "a@b.c", "age": 20, "password": "a", "confirm": "b"})
        [error] = format_errors(exc_info.value)
        assert error["field"] == "__root__"
        assert error["code"] == "value_error"
        assert "passwords do not match" in error["message"]


class TestTask6ApplyDiscount:
    def test_discount(self):
        p = Product(id=1, name="Pen", price=10.0, tags=["office"])
        cheaper = apply_discount(p, 25)
        assert cheaper.price == 7.5
        assert cheaper.tags == ["office"] and cheaper.name == "Pen"

    def test_original_unchanged(self):
        p = Product(id=1, name="Pen", price=10.0)
        apply_discount(p, 50)
        assert p.price == 10.0

    def test_rounding_and_bounds(self):
        p = Product(id=1, name="Pen", price=9.99)
        assert apply_discount(p, 33).price == 6.69
        assert apply_discount(p, 0).price == 9.99
        assert apply_discount(p, 100).price == 0.0

    @pytest.mark.parametrize("percent", [-1, 100.5])
    def test_invalid_percent(self, percent):
        with pytest.raises(ValueError):
            apply_discount(Product(id=1, name="Pen", price=1), percent)


class TestTask7WithChanges:
    def test_changes_are_coerced(self):
        p = Product(id=1, name="Pen", price=10.0)
        changed = with_changes(p, price="9.5", in_stock="no")
        assert changed.price == 9.5 and changed.in_stock is False
        assert type(changed) is Product

    def test_original_unchanged(self):
        p = Product(id=1, name="Pen", price=10.0)
        with_changes(p, name="Pencil")
        assert p.name == "Pen"

    def test_invalid_change_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            with_changes(Product(id=1, name="Pen", price=1.0), price="abc")
        assert error_types(exc_info) == [(("price",), "float_parsing")]

    def test_works_for_nested_models(self):
        order = Order.model_validate(ORDER_DATA)
        changed = with_changes(order, shipping_address={"street": "x", "city": "Lviv"})
        assert isinstance(changed.shipping_address, Address)
        assert changed.shipping_address.city == "Lviv"
        assert changed.total() == Decimal("12.50")


class TestTask8CloneOrder:
    def test_new_id_same_content(self):
        order = Order.model_validate(ORDER_DATA)
        clone = clone_order(order, 99)
        assert clone.id == 99 and order.id == 1
        assert clone.items == order.items

    def test_deep_copy_of_lists(self):
        order = Order.model_validate(ORDER_DATA)
        clone = clone_order(order, 2)
        clone.items.append(OrderItem(sku="C", quantity=1, unit_price=1))
        assert len(order.items) == 2

    def test_deep_copy_of_nested_models(self):
        order = Order.model_validate(ORDER_DATA)
        clone = clone_order(order, 2)
        clone.shipping_address.city = "Odesa"
        assert order.shipping_address.city == "Kyiv"
        assert clone.shipping_address is not order.shipping_address
