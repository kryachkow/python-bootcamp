from datetime import date
from decimal import Decimal

import pytest
from pydantic import TypeAdapter, ValidationError

from m02_pydantic.e02_fields_and_validators.exercise import (
    Account,
    Article,
    Booking,
    CommaSeparated,
    Contact,
    CreateUserRequest,
    GeoPoint,
    Money,
    RegisterRequest,
    Slug,
)


def errors_of(exc_info: pytest.ExceptionInfo[ValidationError]) -> list[tuple[tuple, str]]:
    return [(e["loc"], e["type"]) for e in exc_info.value.errors()]


def messages_of(exc_info: pytest.ExceptionInfo[ValidationError]) -> list[str]:
    return [e["msg"] for e in exc_info.value.errors()]


VALID_USER = {"username": "ada_99", "age": 30}


class TestTask1CreateUserRequest:
    def test_valid_with_defaults(self):
        user = CreateUserRequest(**VALID_USER)
        assert (user.username, user.age, user.tags, user.referral_code) == ("ada_99", 30, [], None)

    @pytest.mark.parametrize(
        ("username", "error_type"),
        [
            ("ab", "string_too_short"),
            ("a" * 33, "string_too_long"),
            ("Ada", "string_pattern_mismatch"),
            ("ada-lovelace", "string_pattern_mismatch"),
        ],
    )
    def test_username_rules(self, username, error_type):
        with pytest.raises(ValidationError) as exc_info:
            CreateUserRequest(**{**VALID_USER, "username": username})
        assert errors_of(exc_info) == [(("username",), error_type)]

    @pytest.mark.parametrize(("age", "error_type"), [(12, "greater_than_equal"), (131, "less_than_equal")])
    def test_age_bounds(self, age, error_type):
        with pytest.raises(ValidationError) as exc_info:
            CreateUserRequest(**{**VALID_USER, "age": age})
        assert errors_of(exc_info) == [(("age",), error_type)]

    def test_age_bounds_are_inclusive(self):
        assert CreateUserRequest(**{**VALID_USER, "age": 13}).age == 13
        assert CreateUserRequest(**{**VALID_USER, "age": 130}).age == 130

    def test_tags_and_referral_code(self):
        assert CreateUserRequest(**VALID_USER, tags=list("abcde"), referral_code="ABC123").tags == list("abcde")
        with pytest.raises(ValidationError) as exc_info:
            CreateUserRequest(**VALID_USER, tags=list("abcdef"), referral_code="ABC")
        assert errors_of(exc_info) == [(("tags",), "too_long"), (("referral_code",), "string_too_short")]


class TestTask2AnnotatedTypes:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [("  Hello World ", "hello-world"), ("my_first__post", "my-first-post"), ("Release_V2 ", "release-v2")],
    )
    def test_slug_normalised(self, raw, expected):
        assert TypeAdapter(Slug).validate_python(raw) == expected

    @pytest.mark.parametrize("raw", ["héllo!", "-leading", "", "a--b"])
    def test_invalid_slug(self, raw):
        with pytest.raises(ValidationError) as exc_info:
            TypeAdapter(Slug).validate_python(raw)
        assert exc_info.value.errors()[0]["type"] == "value_error"
        assert "invalid slug" in exc_info.value.errors()[0]["msg"]

    def test_slug_non_string_reports_string_type(self):
        assert TypeAdapter(Slug).validate_python(" Ok ") == "ok"
        with pytest.raises(ValidationError) as exc_info:
            TypeAdapter(Slug).validate_python(42)
        assert exc_info.value.errors()[0]["type"] == "string_type"

    def test_comma_separated(self):
        adapter = TypeAdapter(CommaSeparated)
        assert adapter.validate_python("a, b,,c ") == ["a", "b", "c"]
        assert adapter.validate_python("") == []
        assert adapter.validate_python(["x", "y"]) == ["x", "y"]

    def test_article_uses_both(self):
        article = Article(title="Hi", slug="Pydantic V2 Tips", tags="python, pydantic")
        assert article.slug == "pydantic-v2-tips"
        assert article.tags == ["python", "pydantic"]
        assert Article(title="t", slug="s").tags == []


VALID_CONTACT = {"first_name": "ada", "last_name": "lovelace", "phone": "+380501234567", "country": "ua"}


class TestTask3Contact:
    def test_names_and_country_normalised(self):
        c = Contact(**{**VALID_CONTACT, "first_name": "  aDA ", "last_name": "von neumann"})
        assert (c.first_name, c.last_name, c.country) == ("Ada", "Von Neumann", "UA")

    @pytest.mark.parametrize("field", ["first_name", "last_name"])
    def test_blank_name(self, field):
        with pytest.raises(ValidationError) as exc_info:
            Contact(**{**VALID_CONTACT, field: "   "})
        assert errors_of(exc_info) == [((field,), "value_error")]
        assert "must not be blank" in messages_of(exc_info)[0]

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [("+38 (050) 123-45-67", "+380501234567"), ("050.123.45.67", "0501234567"), (380501234567, "380501234567")],
    )
    def test_phone_normalised(self, raw, expected):
        assert Contact(**{**VALID_CONTACT, "phone": raw}).phone == expected

    @pytest.mark.parametrize(("raw", "error_type"), [("12-34", "value_error"), ("call me", "value_error"), (None, "string_type")])
    def test_bad_phone(self, raw, error_type):
        with pytest.raises(ValidationError) as exc_info:
            Contact(**{**VALID_CONTACT, "phone": raw})
        assert errors_of(exc_info) == [(("phone",), error_type)]

    @pytest.mark.parametrize("country", ["UKR", "u1", ""])
    def test_bad_country(self, country):
        with pytest.raises(ValidationError) as exc_info:
            Contact(**{**VALID_CONTACT, "country": country})
        assert errors_of(exc_info) == [(("country",), "value_error")]


class TestTask4Booking:
    def test_valid_booking_from_strings(self):
        b = Booking(check_in="2026-07-01", check_out="2026-07-04")
        assert b.check_in == date(2026, 7, 1)
        assert (b.nights, b.guests) == (3, 1)

    @pytest.mark.parametrize("check_out", ["2026-07-01", "2026-06-30"])
    def test_check_out_must_be_after_check_in(self, check_out):
        with pytest.raises(ValidationError) as exc_info:
            Booking(check_in="2026-07-01", check_out=check_out)
        assert errors_of(exc_info) == [((), "value_error")]
        assert "check_out must be after check_in" in messages_of(exc_info)[0]

    def test_max_stay(self):
        assert Booking(check_in="2026-07-01", check_out="2026-07-31").nights == 30
        with pytest.raises(ValidationError) as exc_info:
            Booking(check_in="2026-07-01", check_out="2026-08-01")
        assert "stay is limited to 30 nights" in messages_of(exc_info)[0]

    def test_field_errors_come_first(self):
        with pytest.raises(ValidationError) as exc_info:
            Booking(check_in="not a date", check_out="2026-07-01", guests=11)
        assert errors_of(exc_info) == [(("check_in",), "date_from_datetime_parsing"), (("guests",), "less_than_equal")]


class TestTask5RegisterRequest:
    def test_valid(self):
        r = RegisterRequest(email="ada@example.com", password="s3cret-pass", password_confirm="s3cret-pass")
        assert r.email == "ada@example.com"
        assert "s3cret-pass" not in repr(r)

    def test_passwords_must_match(self):
        with pytest.raises(ValidationError) as exc_info:
            RegisterRequest(email="a@b.c", password="s3cret-pass", password_confirm="s3cret-pas")
        assert errors_of(exc_info) == [((), "value_error")]
        assert "passwords do not match" in messages_of(exc_info)[0]

    def test_password_must_not_contain_email_name(self):
        with pytest.raises(ValidationError) as exc_info:
            RegisterRequest(email="ada@x.io", password="myADA2026!", password_confirm="myADA2026!")
        assert "password must not contain your email name" in messages_of(exc_info)[0]

    def test_short_password_skips_model_validator(self):
        with pytest.raises(ValidationError) as exc_info:
            RegisterRequest(email="a@b.c", password="short", password_confirm="other")
        assert errors_of(exc_info) == [(("password",), "string_too_short")]


class TestTask6GeoPoint:
    @pytest.mark.parametrize(
        "raw",
        [
            {"lat": 50.45, "lon": 30.52},
            {"latitude": 50.45, "longitude": 30.52},
            {"lat": "50.45", "lng": "30.52"},
            "50.45, 30.52",
            [50.45, 30.52],
            (50.45, 30.52),
        ],
    )
    def test_accepted_shapes(self, raw):
        point = GeoPoint.model_validate(raw)
        assert (point.lat, point.lon) == (50.45, 30.52)

    @pytest.mark.parametrize("raw", ["50.45", "1,2,3", [1.0], (1, 2, 3)])
    def test_wrong_number_of_coordinates(self, raw):
        with pytest.raises(ValidationError) as exc_info:
            GeoPoint.model_validate(raw)
        assert "expected exactly two coordinates" in messages_of(exc_info)[0]

    def test_ranges_still_enforced(self):
        with pytest.raises(ValidationError) as exc_info:
            GeoPoint.model_validate("91, 181")
        assert errors_of(exc_info) == [(("lat",), "less_than_equal"), (("lon",), "less_than_equal")]

    def test_other_input_reported_by_pydantic(self):
        assert GeoPoint.model_validate(" -1.5 ,2 ").lon == 2.0
        with pytest.raises(ValidationError) as exc_info:
            GeoPoint.model_validate(42)
        assert errors_of(exc_info) == [((), "model_type")]


class TestTask7Account:
    def test_strips_whitespace(self):
        assert Account(username="  bob  ").username == "bob"

    def test_length_counted_after_strip(self):
        with pytest.raises(ValidationError) as exc_info:
            Account(username="  ab   ")
        assert errors_of(exc_info) == [(("username",), "string_too_short")]

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError) as exc_info:
            Account(username="bob", usernmae="typo")
        assert errors_of(exc_info) == [(("usernmae",), "extra_forbidden")]

    def test_assignment_is_validated(self):
        acc = Account(username="bob")
        acc.balance_cents = "10"
        assert acc.balance_cents == 10
        with pytest.raises(ValidationError) as exc_info:
            acc.balance_cents = -1
        assert errors_of(exc_info) == [(("balance_cents",), "greater_than_equal")]
        assert acc.balance_cents == 10


class TestTask8Money:
    def test_add(self):
        total = Money(amount="1.10", currency="EUR") + Money(amount="2.05", currency="EUR")
        assert total == Money(amount=Decimal("3.15"), currency="EUR")

    def test_add_currency_mismatch(self):
        with pytest.raises(ValueError, match="currency mismatch"):
            Money(amount=1, currency="EUR") + Money(amount=1, currency="USD")

    def test_frozen(self):
        m = Money(amount=1, currency="EUR")
        with pytest.raises(ValidationError) as exc_info:
            m.amount = Decimal("2")
        assert errors_of(exc_info) == [(("amount",), "frozen_instance")]

    def test_hashable(self):
        prices = {Money(amount="1.0", currency="EUR"), Money(amount="1.0", currency="EUR")}
        assert len(prices) == 1
        assert {Money(amount=5, currency="UAH"): "five"}[Money(amount=5, currency="UAH")] == "five"

    def test_currency_pattern(self):
        with pytest.raises(ValidationError) as exc_info:
            Money(amount=1, currency="eur")
        assert errors_of(exc_info) == [(("currency",), "string_pattern_mismatch")]
