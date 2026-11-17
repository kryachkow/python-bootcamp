"""Exercise 2.2: field constraints, validators, and model config.

Each task asks you to write one model (or a reusable annotated type). The
comment above it is the spec. Run the tests with:

    uv run pytest m02_pydantic/e02_fields_and_validators
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from typing import Annotated, Any

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


# ---------------------------------------------------------------------------
# Task 1: CreateUserRequest (Field constraints)
# ---------------------------------------------------------------------------
# Write a request model that uses ONLY ``Field(...)`` constraints, no
# validator functions:
#
#   | field           | type               | rule                                             |
#   |-----------------|--------------------|--------------------------------------------------|
#   | ``username``    | ``str``            | 3..32 chars, regex ``^[a-z0-9_]+$``              |
#   | ``age``         | ``int``            | 13 <= age <= 130                                 |
#   | ``tags``        | ``list[str]``      | at most 5 items, default: new empty list         |
#   | ``referral_code`` | ``str | None``   | default ``None``; if given, exactly 6 chars      |
#
# Pydantic then reports these error types, which the tests check:
# ``string_too_short``, ``string_too_long``, ``string_pattern_mismatch``,
# ``greater_than_equal``, ``less_than_equal``, ``too_long``.
#
# Hint: ``Field(min_length=..., max_length=..., pattern=..., ge=..., le=...)``.
# ``min_length``/``max_length`` work on strings AND on lists.

# TODO: replace the placeholder below with the real definition(s).
class CreateUserRequest(BaseModel):
    """TODO: username, age, tags, referral_code with Field constraints."""


# ---------------------------------------------------------------------------
# Task 2: reusable Annotated types (Slug, CommaSeparated) and Article
# ---------------------------------------------------------------------------
# Define two type aliases you could reuse in any model, and a model using them.
#
# ``Slug``: ``Annotated[str, BeforeValidator(...), AfterValidator(...)]``
#   * BEFORE (raw input): if the value is a ``str``, strip it, lowercase it,
#     and replace every run of spaces and/or underscores with one ``"-"``.
#     Leave non-strings alone, so Pydantic reports its usual ``string_type``.
#   * AFTER (value is a ``str`` now): it must match
#     ``^[a-z0-9]+(?:-[a-z0-9]+)*$``, otherwise raise
#     ``ValueError("invalid slug")``.
#   * ``"  Hello World "`` -> ``"hello-world"``, ``"my_first__post"`` ->
#     ``"my-first-post"``, ``"héllo!"`` -> error.
#
# ``CommaSeparated``: ``Annotated[list[str], BeforeValidator(...)]``
#   * A ``str`` is split on ``","``; every part is stripped and empty parts
#     are dropped: ``"a, b,,c "`` -> ``["a", "b", "c"]``, ``""`` -> ``[]``.
#   * Anything else (e.g. a real list) is passed through unchanged.
#   * Typical use: ``?tags=a,b,c`` query parameters and CSV columns.
#
# ``Article(BaseModel)``:
#   * ``title: str``, ``slug: Slug``, ``tags: CommaSeparated`` (default ``[]``)
#
# Hint: a ``ValueError`` raised inside a validator becomes a
# ``ValidationError`` entry with type ``"value_error"``.

# TODO: replace the placeholders below with the real definitions.
Slug = str
CommaSeparated = list[str]


class Article(BaseModel):
    """TODO: title, slug (Slug), tags (CommaSeparated)."""


# ---------------------------------------------------------------------------
# Task 3: Contact (field_validator, before / after, several fields)
# ---------------------------------------------------------------------------
# Write a ``Contact`` model with fields ``first_name: str``, ``last_name: str``,
# ``phone: str`` and ``country: str`` and these ``@field_validator``s:
#
#   * ONE after-validator for BOTH ``first_name`` and ``last_name``: strip
#     the value; if it is then empty raise ``ValueError("must not be blank")``;
#     otherwise return it title-cased (``"  aDA "`` -> ``"Ada"``).
#   * a BEFORE validator for ``phone``: an ``int`` becomes a ``str``; from a
#     ``str`` remove spaces, ``-``, ``(``, ``)`` and ``.``; the result must
#     match ``^\+?\d{7,15}$`` or raise ``ValueError("invalid phone number")``.
#     Return any other type unchanged (Pydantic then reports ``string_type``).
#     ``"+38 (050) 123-45-67"`` -> ``"+380501234567"``.
#   * an after-validator for ``country``: uppercase it; it must be exactly
#     two ASCII letters, else ``ValueError("country must be an ISO alpha-2 code")``.
#
# Hint: ``@field_validator("first_name", "last_name")`` followed by
# ``@classmethod``. Use ``mode="before"`` for the phone validator.

# TODO: replace the placeholder below with the real definition(s).
class Contact(BaseModel):
    """TODO: first_name, last_name, phone, country + field validators."""


# ---------------------------------------------------------------------------
# Task 4: Booking (model_validator, mode="after", cross-field rules)
# ---------------------------------------------------------------------------
# Write a ``Booking`` model:
#
#   * ``check_in: date``, ``check_out: date`` (ISO strings such as
#     ``"2026-07-01"`` are accepted in lax mode)
#   * ``guests: int`` with ``1 <= guests <= 10`` (``Field``), default ``1``
#   * an after model validator: if ``check_out <= check_in`` raise
#     ``ValueError("check_out must be after check_in")``; if the stay is
#     longer than 30 nights raise ``ValueError("stay is limited to 30 nights")``.
#     Return ``self``.
#   * a read-only ``@property`` ``nights`` -> ``int`` (days between the dates).
#
# Model-level errors have an empty ``loc`` ``()`` and type ``"value_error"``.
# Field errors (e.g. a bad date) are reported first and the model
# validator does not run.

# TODO: replace the placeholder below with the real definition(s).
class Booking(BaseModel):
    """TODO: check_in, check_out, guests, the date rules, and nights."""


# ---------------------------------------------------------------------------
# Task 5: RegisterRequest (model_validator, password confirmation)
# ---------------------------------------------------------------------------
# Write a ``RegisterRequest`` model:
#
#   * ``email: str`` (no format check needed here)
#   * ``password: str`` with at least 8 characters
#   * ``password_confirm: str``
#   * an after model validator that raises
#       - ``ValueError("passwords do not match")`` if the two passwords differ;
#       - ``ValueError("password must not contain your email name")`` if the
#         part of ``email`` before ``"@"`` appears in ``password``, ignoring case
#         (``"ada@x.io"`` + ``"myADA2026!"`` is rejected).
#
# Keep the password out of logs: pass ``repr=False`` to both password
# ``Field``s, so ``repr(request)`` does not show them.

# TODO: replace the placeholder below with the real definition(s).
class RegisterRequest(BaseModel):
    """TODO: email, password, password_confirm + the password rules."""


# ---------------------------------------------------------------------------
# Task 6: GeoPoint (model_validator, mode="before", normalising raw input)
# ---------------------------------------------------------------------------
# Different clients send coordinates in different shapes. Write a
# ``GeoPoint`` model with ``lat: float`` (-90..90) and ``lon: float``
# (-180..180), plus a ``@model_validator(mode="before")`` that turns each of
# these inputs into ``{"lat": ..., "lon": ...}`` BEFORE field validation:
#
#   | raw input                                   | meaning                    |
#   |---------------------------------------------|----------------------------|
#   | ``{"lat": 50.4, "lon": 30.5}``              | already fine               |
#   | ``{"latitude": 50.4, "longitude": 30.5}``   | long key names             |
#   | ``{"lat": 50.4, "lng": 30.5}``              | Google-style ``lng``       |
#   | ``"50.4, 30.5"``                            | a ``"lat,lon"`` string (strip each part) |
#   | ``[50.4, 30.5]`` or ``(50.4, 30.5)``        | a 2-item list or tuple     |
#
#   * A string that does not split into exactly two parts, or a list/tuple
#     that does not have exactly two items, raises
#     ``ValueError("expected exactly two coordinates")``.
#   * Any other input is returned unchanged (Pydantic reports it).
#   * Do not convert the numbers yourself: field validation still coerces
#     ``"50.4"`` to ``50.4`` and enforces the ranges.
#
# >>> GeoPoint.model_validate("50.45, 30.52")
# GeoPoint(lat=50.45, lon=30.52)

# TODO: replace the placeholder below with the real definition(s).
class GeoPoint(BaseModel):
    """TODO: lat, lon with ranges + a before model validator."""


# ---------------------------------------------------------------------------
# Task 7: Account (ConfigDict: extra, whitespace, assignment validation)
# ---------------------------------------------------------------------------
# Write an ``Account`` model with
#
#   * ``model_config = ConfigDict(...)`` that
#       - forbids unknown fields (error type ``"extra_forbidden"``): a typo
#         such as ``usernmae`` must not be silently dropped;
#       - strips whitespace from every ``str`` field before validation;
#       - re-validates on attribute assignment, so ``acc.balance_cents = -1``
#         raises ``ValidationError`` and ``acc.balance_cents = "10"`` stores ``10``.
#   * ``username: str`` with at least 3 characters (counted AFTER stripping)
#   * ``balance_cents: int = 0`` with ``>= 0``

# TODO: replace the placeholder below with the real definition(s).
class Account(BaseModel):
    """TODO: model_config + username, balance_cents."""


# ---------------------------------------------------------------------------
# Task 8: Money (frozen value object)
# ---------------------------------------------------------------------------
# Write an immutable ``Money`` value object:
#
#   * ``model_config = ConfigDict(frozen=True)``: assigning to a field raises
#     ``ValidationError`` (type ``"frozen_instance"``), and instances are
#     hashable, so equal amounts can be dict keys / set members.
#   * ``amount: Decimal``
#   * ``currency: str`` matching ``^[A-Z]{3}$``
#   * ``__add__(self, other: Money) -> Money``: a NEW ``Money`` with the summed
#     amount; raise ``ValueError("currency mismatch")`` if the currencies differ.
#
# >>> Money(amount="1.10", currency="EUR") + Money(amount="2.05", currency="EUR")
# Money(amount=Decimal('3.15'), currency='EUR')

# TODO: replace the placeholder below with the real definition(s).
class Money(BaseModel):
    """TODO: frozen config, amount, currency, and __add__."""
