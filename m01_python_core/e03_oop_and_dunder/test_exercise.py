from datetime import UTC, datetime
from decimal import Decimal

import pytest

from m01_python_core.e03_oop_and_dunder.exercise import (
    Article,
    CurrencyMismatchError,
    EmailNotifier,
    Message,
    MessageHistory,
    Model,
    Money,
    Notifier,
    SmsNotifier,
    SoftDeleteMixin,
    Temperature,
    TimestampMixin,
    Vector,
)

T0 = datetime(2024, 1, 1, tzinfo=UTC)
T1 = datetime(2024, 2, 1, tzinfo=UTC)


class TestTask1Temperature:
    def test_conversions(self):
        t = Temperature(100)
        assert t.celsius == 100.0
        assert isinstance(t.celsius, float)
        assert t.fahrenheit == 212.0
        assert t.kelvin == pytest.approx(373.15)

    def test_fahrenheit_setter_updates_celsius(self):
        t = Temperature(20)
        t.fahrenheit = 32
        assert t.celsius == 0.0

    def test_validation_below_absolute_zero(self):
        t = Temperature(0)
        with pytest.raises(ValueError):
            t.celsius = -300
        with pytest.raises(ValueError):
            t.fahrenheit = -500  # validated through the celsius setter
        assert t.celsius == 0.0
        with pytest.raises(ValueError):
            Temperature(-273.16)

    @pytest.mark.parametrize("bad", ["20", None, True])
    def test_type_validation(self, bad):
        with pytest.raises(TypeError):
            Temperature(bad)

    def test_kelvin_is_read_only(self):
        t = Temperature(0)
        assert t.kelvin == pytest.approx(273.15)
        with pytest.raises(AttributeError):
            t.kelvin = 10


class TestTask2MoneyValueSemantics:
    def test_repr_and_str(self):
        m = Money("12.5", "usd")
        assert repr(m) == "Money('12.50', 'USD')"
        assert str(m) == "12.50 USD"

    def test_equality(self):
        assert Money("1", "USD") == Money("1.00", "usd")
        assert Money("1", "USD") != Money("1", "EUR")
        assert Money("1", "USD") != Money("2", "USD")

    def test_comparison_with_other_types_is_false_not_error(self):
        assert Money("1", "USD") != "1.00 USD"
        assert (Money("1", "USD") == 1) is False

    def test_hashable_and_consistent_with_eq(self):
        prices = {Money("1", "USD"), Money("1.00", "USD"), Money("1", "EUR")}
        assert len(prices) == 2
        assert {Money("5", "USD"): "five"}[Money("5.00", "USD")] == "five"


class TestTask3MoneyArithmetic:
    def test_add_and_sub(self):
        total = Money("1.10", "USD") + Money("2.20", "usd")
        assert (total.amount, total.currency) == (Decimal("3.30"), "USD")
        diff = Money("1", "USD") - Money("2.50", "USD")
        assert diff.amount == Decimal("-1.50")

    def test_currency_mismatch(self):
        with pytest.raises(CurrencyMismatchError):
            Money("1", "USD") + Money("1", "EUR")
        with pytest.raises(CurrencyMismatchError):
            Money("1", "USD") - Money("1", "EUR")
        assert issubclass(CurrencyMismatchError, ValueError)

    def test_sum_uses_radd(self):
        result = sum([Money("1.25", "USD"), Money("2", "USD"), Money("0.75", "USD")])
        assert result.amount == Decimal("4.00")

    def test_multiply_and_negate(self):
        assert (Money("2.50", "USD") * 3).amount == Decimal("7.50")
        assert (3 * Money("2.50", "USD")).amount == Decimal("7.50")
        assert (Money("10", "USD") * Decimal("0.333")).amount == Decimal("3.33")
        assert (-Money("5", "USD")).amount == Decimal("-5.00")

    @pytest.mark.parametrize("bad", [1.5, True, "2"])
    def test_unsupported_operands_raise_type_error(self, bad):
        m = Money("1", "USD")
        assert (m * 2).amount == Decimal("2.00")
        with pytest.raises(TypeError):
            m * bad
        with pytest.raises(TypeError):
            m + bad


class TestTask4MoneyOrderingAndConstructors:
    def test_ordering(self):
        a, b = Money("1", "USD"), Money("2", "USD")
        assert a < b and b > a and a <= a and b >= a
        assert max([b, a, Money("1.50", "USD")]).amount == Decimal("2.00")

    def test_ordering_across_currencies_raises(self):
        with pytest.raises(CurrencyMismatchError):
            Money("1", "USD") < Money("2", "EUR")

    def test_zero_and_from_cents(self):
        assert Money.zero("usd").amount == Decimal("0.00")
        assert Money.from_cents(1250, "USD").amount == Decimal("12.50")
        assert Money.from_cents(-5, "EUR").amount == Decimal("-0.05")
        with pytest.raises(TypeError):
            Money.from_cents(12.5, "USD")

    def test_parse(self):
        m = Money.parse("  12.50   eur ")
        assert (m.amount, m.currency) == (Decimal("12.50"), "EUR")

    @pytest.mark.parametrize("text", ["12.50", "USD 12.50", "1 2 USD", ""])
    def test_parse_rejects_bad_input(self, text):
        with pytest.raises(ValueError):
            Money.parse(text)

    def test_classmethods_respect_subclasses(self):
        class Price(Money):
            pass

        assert type(Price.parse("1 USD")) is Price
        assert type(Price.zero("USD")) is Price


class TestTask5MessageHistory:
    def test_len_iter_and_index(self):
        h = MessageHistory([("system", "be brief"), ("user", "hi"), ("assistant", "hello")])
        assert len(h) == 3
        assert [m.role for m in h] == ["system", "user", "assistant"]
        assert h[0] == Message("system", "be brief")
        assert h[-1].content == "hello"

    def test_slice_returns_new_history(self):
        h = MessageHistory([("user", "a"), ("assistant", "b"), ("user", "c")], max_messages=5)
        tail = h[1:]
        assert isinstance(tail, MessageHistory)
        assert [m.content for m in tail] == ["b", "c"]
        assert tail.max_messages == 5
        assert len(h) == 3

    def test_contains_by_content_or_message(self):
        h = MessageHistory([("user", "hi")])
        assert "hi" in h
        assert "bye" not in h
        assert Message("user", "hi") in h
        assert ("assistant", "hi") not in h

    def test_trimming_keeps_system_prompt(self):
        h = MessageHistory([("system", "be brief"), ("user", "hi")], max_messages=2)
        h.append("assistant", "hello")
        assert [m.content for m in h] == ["be brief", "hello"]
        h.append("user", "more")
        assert [m.content for m in h] == ["be brief", "more"]

    def test_invalid_role(self):
        h = MessageHistory()
        assert len(h) == 0
        with pytest.raises(ValueError):
            h.append("robot", "beep")


class TestTask6Notifier:
    def test_abstract_base_cannot_be_instantiated(self):
        with pytest.raises(TypeError):
            Notifier()

    def test_incomplete_subclass_cannot_be_instantiated(self):
        class OnlySend(Notifier):
            def send(self, recipient, message):
                return "sent"

        with pytest.raises(TypeError):
            OnlySend()

    def test_email(self):
        n = EmailNotifier("noreply@app.io")
        assert n.channel == "email"
        assert n.send("ann@x.io", "hi") == "email from noreply@app.io to ann@x.io: hi"
        with pytest.raises(ValueError):
            n.send("ann", "hi")

    def test_sms_validation_and_truncation(self):
        n = SmsNotifier()
        assert n.channel == "sms"
        assert n.send("+380501234567", "hi") == "sms to +380501234567: hi"
        long = n.send("+1", "x" * 200)
        text = long.removeprefix("sms to +1: ")
        assert len(text) == 160 and text.endswith("...")
        for bad in ["380501234567", "+", "+38-050"]:
            with pytest.raises(ValueError):
                n.send(bad, "hi")

    def test_notify_all_template_method(self):
        results = SmsNotifier().notify_all(["+1", "oops"], "ping")
        assert results["+1"] == "sms to +1: ping"
        assert results["oops"].startswith("error: ")


class TestTask7CooperativeInheritance:
    def test_all_init_methods_run(self):
        a = Article(title="Hello", created_at=T0)
        assert (a.title, a.created_at, a.deleted_at, a.is_deleted) == ("Hello", T0, None, False)

    def test_default_created_at_is_aware_utc_now(self):
        before = datetime.now(UTC)
        a = Article(title="x")
        assert before <= a.created_at <= datetime.now(UTC)

    def test_to_dict_follows_the_mro(self):
        a = Article(title="Hello", created_at=T0, deleted_at=T1)
        d = a.to_dict()
        assert d == {
            "deleted_at": "2024-02-01T00:00:00+00:00",
            "created_at": "2024-01-01T00:00:00+00:00",
            "title": "Hello",
        }
        assert list(d) == ["deleted_at", "created_at", "title"]

    def test_unknown_field_reaches_model(self):
        with pytest.raises(TypeError, match="author"):
            Article(title="x", author="me")

    def test_soft_delete_and_other_combinations(self):
        class Note(SoftDeleteMixin, Model):
            pass

        n = Note()
        n.soft_delete(T1)
        assert n.is_deleted and n.to_dict() == {"deleted_at": "2024-02-01T00:00:00+00:00"}
        with pytest.raises(RuntimeError):
            n.soft_delete(T1)

        class Event(TimestampMixin, Model):
            pass

        assert Event(created_at=T0).to_dict() == {"created_at": "2024-01-01T00:00:00+00:00"}


class TestTask8Vector:
    def test_basics(self):
        v = Vector(3, 4)
        assert repr(v) == "Vector(3.0, 4.0)"
        assert len(v) == 2
        x, y = v
        assert (x, y) == (3.0, 4.0)
        assert abs(v) == 5.0

    def test_slots(self):
        v = Vector(1, 2)
        assert not hasattr(v, "__dict__")
        with pytest.raises(AttributeError):
            v.label = "oops"

    def test_eq_hash_bool(self):
        assert Vector(1, 2) == Vector(1.0, 2.0)
        assert Vector(1, 2) != (1.0, 2.0)
        assert len({Vector(1, 2), Vector(1, 2), Vector(2, 1)}) == 2
        assert not Vector(0, 0) and Vector(0, 0.1)

    def test_dot_product_and_errors(self):
        assert Vector(1, 2, 3) @ Vector(4, 5, 6) == 32.0
        with pytest.raises(ValueError):
            Vector(1, 2) @ Vector(1, 2, 3)
        with pytest.raises(ValueError):
            Vector()

    def test_cosine_similarity(self):
        assert Vector(1, 0).cosine_similarity(Vector(5, 0)) == pytest.approx(1.0)
        assert Vector(1, 0).cosine_similarity(Vector(0, 2)) == pytest.approx(0.0)
        assert Vector(1, 1).cosine_similarity(Vector(-1, -1)) == pytest.approx(-1.0)
        with pytest.raises(ValueError):
            Vector(0, 0).cosine_similarity(Vector(1, 1))
