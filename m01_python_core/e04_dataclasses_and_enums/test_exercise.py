import dataclasses
import json
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from m01_python_core.e04_dataclasses_and_enums.exercise import (
    AppConfig,
    GeoPoint,
    LineItem,
    Order,
    OrderStatus,
    Permission,
    Version,
)


class TestTask1OrderStatus:
    def test_members_are_lowercase_strings(self):
        assert [s.value for s in OrderStatus] == ["pending", "paid", "shipped", "delivered", "cancelled"]
        assert OrderStatus.PAID == "paid"
        assert OrderStatus("shipped") is OrderStatus.SHIPPED
        assert json.dumps({"status": OrderStatus.PAID}) == '{"status": "paid"}'

    def test_is_final(self):
        assert [s for s in OrderStatus if s.is_final] == [OrderStatus.DELIVERED, OrderStatus.CANCELLED]

    @pytest.mark.parametrize(
        ("src", "dst", "allowed"),
        [
            ("pending", "paid", True),
            ("pending", "cancelled", True),
            ("paid", "shipped", True),
            ("shipped", "delivered", True),
            ("pending", "shipped", False),
            ("shipped", "cancelled", False),
            ("delivered", "pending", False),
            ("paid", "paid", False),
        ],
    )
    def test_can_transition_to(self, src, dst, allowed):
        assert OrderStatus(src).can_transition_to(OrderStatus(dst)) is allowed

    def test_transition_to(self):
        assert OrderStatus.PENDING.transition_to(OrderStatus.PAID) is OrderStatus.PAID
        with pytest.raises(ValueError, match="cannot go from shipped to paid"):
            OrderStatus.SHIPPED.transition_to(OrderStatus.PAID)


class TestTask2Permission:
    def test_values_and_combination(self):
        assert (Permission.READ, Permission.WRITE, Permission.DELETE) == (1, 2, 4)
        assert Permission.ADMIN == Permission.READ | Permission.WRITE | Permission.DELETE

    def test_from_names(self):
        assert Permission.from_names(["read", " Write "]) == Permission.READ | Permission.WRITE
        assert Permission.from_names([]) == 0
        assert Permission.from_names(["admin"]) is Permission.ADMIN

    def test_from_names_unknown(self):
        with pytest.raises(ValueError):
            Permission.from_names(["read", "fly"])

    def test_allows(self):
        rw = Permission.READ | Permission.WRITE
        assert rw.allows(Permission.READ)
        assert rw.allows(Permission.READ | Permission.WRITE)
        assert not rw.allows(Permission.DELETE)
        assert not rw.allows(Permission.ADMIN)
        assert Permission.ADMIN.allows(rw)

    def test_names(self):
        assert Permission.ADMIN.names() == ["read", "write", "delete"]
        assert (Permission.DELETE | Permission.READ).names() == ["read", "delete"]
        assert Permission.from_names([]).names() == []


KYIV = (50.4501, 30.5234)
LVIV = (49.8397, 24.0297)


class TestTask3GeoPoint:
    def test_fields_and_tuple_behaviour(self):
        p = GeoPoint(50.45, 30.52)
        assert p.label == ""
        lat, lon, label = p
        assert (lat, lon) == (50.45, 30.52)
        assert GeoPoint._fields == ("lat", "lon", "label")
        assert {p, GeoPoint(50.45, 30.52)} == {p}

    def test_distance(self):
        assert GeoPoint(0, 0).distance_km(GeoPoint(0, 1)) == pytest.approx(111.19, abs=0.01)
        kyiv, lviv = GeoPoint(*KYIV, "Kyiv"), GeoPoint(*LVIV)
        assert kyiv.distance_km(lviv) == pytest.approx(467.5, abs=0.5)
        assert kyiv.distance_km(kyiv) == 0

    def test_with_label_returns_copy(self):
        p = GeoPoint(1, 2)
        q = p.with_label("home")
        assert (q, p.label) == (GeoPoint(1, 2, "home"), "")

    def test_from_string(self):
        assert GeoPoint.from_string(" 50.45 , 30.52 ") == GeoPoint(50.45, 30.52)
        assert GeoPoint.from_string("1,2,office") == GeoPoint(1.0, 2.0, "office")

    @pytest.mark.parametrize("text", ["1", "1,2,3,4", "abc,2", "91,0", "0,-181"])
    def test_from_string_invalid(self, text):
        with pytest.raises(ValueError):
            GeoPoint.from_string(text)


class TestTask4Version:
    def test_frozen_and_hashable(self):
        v = Version(1, 2, 3)
        with pytest.raises(dataclasses.FrozenInstanceError):
            v.major = 2
        assert len({Version(1, 2, 3), Version(1, 2, 3)}) == 1

    def test_ordering(self):
        versions = [Version(1, 10, 0), Version(1, 2, 3), Version(0, 9), Version(1, 2)]
        assert sorted(versions) == [Version(0, 9), Version(1, 2), Version(1, 2, 3), Version(1, 10, 0)]
        assert Version(2) > Version(1, 99, 99)

    def test_parse_and_str(self):
        assert Version.parse("v1.2.3") == Version(1, 2, 3)
        assert str(Version.parse("10.0.1")) == "10.0.1"

    @pytest.mark.parametrize("text", ["1.2", "1.2.3.4", "1.x.3", "", "v-1.2.3"])
    def test_parse_invalid(self, text):
        with pytest.raises(ValueError):
            Version.parse(text)

    def test_validation(self):
        with pytest.raises(ValueError):
            Version(1, -1, 0)
        with pytest.raises(TypeError):
            Version("1", 0, 0)

    def test_bump(self):
        v = Version(1, 2, 3)
        assert v.bump("major") == Version(2, 0, 0)
        assert v.bump("minor") == Version(1, 3, 0)
        assert v.bump("patch") == Version(1, 2, 4)
        assert v == Version(1, 2, 3)
        with pytest.raises(ValueError):
            v.bump("build")


class TestTask5LineItem:
    def test_normalises(self):
        item = LineItem(" ab-1 ", "2.50", 3)
        assert item.sku == "AB-1"
        assert item.unit_price == Decimal("2.50") and isinstance(item.unit_price, Decimal)
        assert item.subtotal == Decimal("7.50")

    def test_int_price_and_default_quantity(self):
        item = LineItem("x", 5)
        assert (item.unit_price, item.quantity, item.subtotal) == (Decimal(5), 1, Decimal(5))

    @pytest.mark.parametrize(
        ("kwargs", "error"),
        [
            ({"sku": "  "}, ValueError),
            ({"unit_price": 1.5}, TypeError),
            ({"unit_price": "-1"}, ValueError),
            ({"quantity": 0}, ValueError),
            ({"quantity": True}, TypeError),
        ],
    )
    def test_validation(self, kwargs, error):
        args = {"sku": "ok", "unit_price": "1", "quantity": 1} | kwargs
        with pytest.raises(error):
            LineItem(**args)


class TestTask6Order:
    def test_keyword_only(self):
        order = Order(id="o1", customer_email="a@b.c")
        assert (order.id, order.customer_email) == ("o1", "a@b.c")
        with pytest.raises(TypeError):
            Order("o1", "a@b.c")

    def test_mutable_defaults_are_not_shared(self):
        a = Order(id="a", customer_email="x@y.z")
        b = Order(id="b", customer_email="x@y.z")
        a.items.append(LineItem("sku", 1))
        a.tags.add("vip")
        assert (b.items, b.tags) == ([], set())

    def test_created_at_default_and_excluded_from_eq(self):
        before = datetime.now(UTC)
        a = Order(id="a", customer_email="x@y.z")
        assert before <= a.created_at <= datetime.now(UTC)
        b = Order(id="a", customer_email="x@y.z", created_at=datetime(2000, 1, 1, tzinfo=UTC))
        assert a == b

    def test_add_item_merges_same_sku(self):
        order = Order(id="o1", customer_email="a@b.c")
        order.add_item(LineItem("A", "2.00", 1))
        order.add_item(LineItem("b", "1.50", 2))
        order.add_item(LineItem("a", "2.00", 3))
        assert [(i.sku, i.quantity) for i in order.items] == [("A", 4), ("B", 2)]
        assert order.total == Decimal("11.00")
        with pytest.raises(ValueError):
            order.add_item(LineItem("A", "9.99"))

    def test_empty_total(self):
        assert Order(id="o", customer_email="a@b.c").total == Decimal("0")


class TestTask7AppConfig:
    def test_from_env_converts_types(self):
        env = {"APP_HOST": "0.0.0.0", "APP_PORT": "9000", "APP_DEBUG": "Yes", "APP_TIMEOUT_S": "2.5", "OTHER": "x"}
        cfg = AppConfig.from_env(env)
        assert cfg == AppConfig(host="0.0.0.0", port=9000, debug=True, timeout_s=2.5)
        assert isinstance(cfg.port, int) and isinstance(cfg.timeout_s, float)

    def test_missing_keys_keep_defaults_and_custom_prefix(self):
        assert AppConfig.from_env({}) == AppConfig()
        cfg = AppConfig.from_env({"SVC_DEBUG": "off", "APP_PORT": "1"}, prefix="SVC_")
        assert (cfg.debug, cfg.port) == (False, 8000)

    @pytest.mark.parametrize("env", [{"APP_DEBUG": "maybe"}, {"APP_PORT": "eighty"}, {"APP_PORT": "70000"}])
    def test_from_env_invalid(self, env):
        with pytest.raises(ValueError):
            AppConfig.from_env(env)

    def test_validation_and_frozen(self):
        cfg = AppConfig()
        with pytest.raises(dataclasses.FrozenInstanceError):
            cfg.port = 1
        with pytest.raises(ValueError):
            AppConfig(timeout_s=0)

    def test_with_overrides(self):
        cfg = AppConfig()
        dev = cfg.with_overrides(debug=True, port=8080)
        assert (dev.debug, dev.port, cfg.debug) == (True, 8080, False)
        with pytest.raises(TypeError):
            cfg.with_overrides(colour="blue")
        with pytest.raises(ValueError):
            cfg.with_overrides(port=0)
