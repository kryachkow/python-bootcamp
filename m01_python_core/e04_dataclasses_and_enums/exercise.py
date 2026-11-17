"""Exercise 1.4: dataclasses, enums, and NamedTuple.

Implement every task below. Some tasks ask you to write the class body
(members or fields) yourself; the docstring lists exactly what to declare.
Run the tests with:

    uv run pytest m01_python_core/e04_dataclasses_and_enums
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, fields, replace
from datetime import UTC, datetime
from decimal import Decimal
from enum import IntFlag, StrEnum, auto
from typing import Any, Literal, NamedTuple, Self, get_type_hints


# ---------------------------------------------------------------------------
# Task 1: StrEnum with behaviour
# ---------------------------------------------------------------------------
class OrderStatus(StrEnum):
    """The lifecycle of an order.

    Declare five members with ``auto()``. For a ``StrEnum``, ``auto()`` uses
    the lowercased member name as the value: ``PENDING``, ``PAID``,
    ``SHIPPED``, ``DELIVERED``, ``CANCELLED``. Members are real ``str``
    objects, so ``OrderStatus.PAID == "paid"`` and they serialise to JSON
    as-is (Pydantic and SQLAlchemy both handle them).

    Allowed transitions::

        pending -> paid | cancelled
        paid    -> shipped | cancelled
        shipped -> delivered
        delivered, cancelled -> (nothing: final states)

    * ``is_final`` (property): true for ``DELIVERED`` and ``CANCELLED``.
    * ``can_transition_to(target)``: whether the transition is allowed.
      Moving to the same status is not a transition (``False``).
    * ``transition_to(target)``: return ``target`` if allowed, otherwise
      raise ``ValueError("cannot go from shipped to paid")``.

    Hint: you cannot add a plain dict as a class attribute of an ``Enum``
    (it would become a member). Put the transition table in a module-level
    constant, or build it inside the method.
    """

    pass

    @property
    def is_final(self) -> bool:
        raise NotImplementedError("TODO: implement this task")

    def can_transition_to(self, target: OrderStatus) -> bool:
        raise NotImplementedError("TODO: implement this task")

    def transition_to(self, target: OrderStatus) -> OrderStatus:
        raise NotImplementedError("TODO: implement this task")


# (your transition table goes here, if you want one)


# ---------------------------------------------------------------------------
# Task 2: IntFlag for permissions
# ---------------------------------------------------------------------------
class Permission(IntFlag):
    """Bit-flag permissions that combine with ``|``.

    Declare ``READ``, ``WRITE``, ``DELETE`` with ``auto()`` (giving 1, 2, 4)
    and ``ADMIN = READ | WRITE | DELETE``.

    * ``from_names(names)`` (classmethod): combine names such as
      ``["read", " Write "]``. Matching ignores case and surrounding spaces.
      An unknown name raises ``ValueError``. No names gives ``Permission(0)``.
    * ``allows(required)``: true if **every** bit of ``required`` is set in
      ``self``.
    * ``names()``: the lowercased names of the single-bit members contained
      in ``self``, in definition order. ``ADMIN.names()`` is
      ``["read", "write", "delete"]``.

    >>> p = Permission.from_names(["read", "write"])
    >>> p.allows(Permission.READ), p.allows(Permission.ADMIN), p.names()
    (True, False, ['read', 'write'])

    Hint: since Python 3.11, iterating over a flag value yields the
    single-bit members it contains.
    """

    pass

    @classmethod
    def from_names(cls, names: Iterable[str]) -> Permission:
        raise NotImplementedError("TODO: implement this task")

    def allows(self, required: Permission) -> bool:
        raise NotImplementedError("TODO: implement this task")

    def names(self) -> list[str]:
        raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 3: NamedTuple
# ---------------------------------------------------------------------------
EARTH_RADIUS_KM = 6371.0


class GeoPoint(NamedTuple):
    """An immutable (latitude, longitude) pair with an optional label.

    Declare the fields: ``lat: float``, ``lon: float``, ``label: str = ""``.
    A ``NamedTuple`` is a real tuple: it unpacks, it is hashable, and it is
    cheap. It is the right tool for small records such as rows or
    coordinates.

    * ``distance_km(other)``: the great-circle distance with the haversine
      formula and ``EARTH_RADIUS_KM``. The labels do not matter.
    * ``with_label(label)``: a copy with a new label (``self._replace``).
    * ``from_string("50.45, 30.52")`` (classmethod): parse ``"lat,lon"`` or
      ``"lat,lon,label"``, strip spaces around each part. Raise ``ValueError``
      for the wrong number of parts, non-numbers, latitude outside
      [-90, 90], or longitude outside [-180, 180].

    Haversine::

        h = sin²(Δφ/2) + cos φ1 · cos φ2 · sin²(Δλ/2)
        d = 2 · R · asin(√h)          (φ = latitude, λ = longitude, in radians)
    """

    pass

    def distance_km(self, other: GeoPoint) -> float:
        raise NotImplementedError("TODO: implement this task")

    def with_label(self, label: str) -> GeoPoint:
        raise NotImplementedError("TODO: implement this task")

    @classmethod
    def from_string(cls, text: str) -> GeoPoint:
        raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 4: frozen + ordered dataclass
# ---------------------------------------------------------------------------
# Replace the plain ``@dataclass`` below so that ``Version`` is frozen
# (immutable and hashable) and ordered (``<`` compares fields in order).
@dataclass
class Version:
    """A semantic version ``major.minor.patch``.

    * Make the dataclass **frozen** and **ordered**: assigning a field raises
      ``dataclasses.FrozenInstanceError``, instances can go in a set, and
      ``sorted(versions)`` works, because fields are compared as a tuple in
      declaration order.
    * ``__post_init__``: raise ``ValueError`` if any part is negative, and
      ``TypeError`` if a part is not an ``int`` (or is a ``bool``).
    * ``parse("1.2.3")`` / ``parse("v1.2.3")`` (classmethod): exactly three
      dot-separated integers, with an optional leading ``v``. Anything else
      raises ``ValueError``.
    * ``bump(part)``: return a new version, made with
      ``dataclasses.replace``. ``"major"`` resets minor and patch to 0, and
      ``"minor"`` resets patch to 0. Any other part raises ``ValueError``.
    * ``str(Version(1, 2, 3))`` is ``"1.2.3"``.
    """

    major: int
    minor: int = 0
    patch: int = 0

    def __post_init__(self) -> None:
        raise NotImplementedError("TODO: implement this task")

    @classmethod
    def parse(cls, text: str) -> Self:
        raise NotImplementedError("TODO: implement this task")

    def bump(self, part: Literal["major", "minor", "patch"]) -> Self:
        raise NotImplementedError("TODO: implement this task")

    def __str__(self) -> str:
        raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 5: __post_init__ validation and normalisation
# ---------------------------------------------------------------------------
@dataclass
class LineItem:
    """One line of an order.

    ``__post_init__`` normalises and validates, like a tiny Pydantic model:

    * ``sku``: strip spaces and uppercase it. Empty after stripping:
      ``ValueError``.
    * ``unit_price``: accept ``Decimal``, ``int``, or ``str`` and store a
      ``Decimal``. A ``float`` raises ``TypeError``. A negative price raises
      ``ValueError``.
    * ``quantity``: must be an ``int`` (not ``bool``, otherwise
      ``TypeError``) and ``>= 1`` (otherwise ``ValueError``).

    ``subtotal`` (property) is ``unit_price * quantity``.

    >>> LineItem(" ab-1 ", "2.50", 3).subtotal
    Decimal('7.50')
    """

    sku: str
    unit_price: Decimal
    quantity: int = 1

    def __post_init__(self) -> None:
        raise NotImplementedError("TODO: implement this task")

    @property
    def subtotal(self) -> Decimal:
        raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 6: kw_only, default_factory, field options
# ---------------------------------------------------------------------------
# Replace the plain ``@dataclass`` below with a keyword-only one.
@dataclass
class Order:
    """An order. Write the fields yourself:

    * Make the dataclass ``kw_only=True``. ``Order(id="o1", customer_email=...)``
      works and ``Order("o1", "a@b.c")`` raises ``TypeError``. With many
      fields, keyword-only construction prevents mixing up arguments.
    * ``id: str`` and ``customer_email: str``, both required.
    * ``items: list[LineItem]``, default: a new empty list per instance. Use
      ``field(default_factory=list)``; a plain ``= []`` default is rejected by
      dataclasses for a good reason.
    * ``tags: set[str]``, default: a new empty set.
    * ``created_at: datetime``, default: ``datetime.now(UTC)`` at creation
      time. Exclude it from ``==`` with ``compare=False``, so two orders with
      the same data are equal however far apart they were created.

    Methods:

    * ``add_item(item)``: if an item with the same ``sku`` exists, replace it
      with a copy whose quantity is the sum (``dataclasses.replace``, which
      runs ``__post_init__`` again). If the unit prices differ, raise
      ``ValueError`` instead. Otherwise append.
    * ``total`` (property): the sum of the subtotals, ``Decimal("0")`` when
      empty.
    """

    pass

    def add_item(self, item: LineItem) -> None:
        raise NotImplementedError("TODO: implement this task")

    @property
    def total(self) -> Decimal:
        raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 7: settings from environment variables (fields() + get_type_hints)
# ---------------------------------------------------------------------------
TRUE_STRINGS = frozenset({"1", "true", "yes", "on"})
FALSE_STRINGS = frozenset({"0", "false", "no", "off"})


@dataclass(frozen=True)
class AppConfig:
    """Immutable application settings: a hand-made ``pydantic-settings``.

    * ``__post_init__``: ``port`` must be in 1..65535 and ``timeout_s`` must
      be > 0, otherwise ``ValueError``.
    * ``from_env(env, *, prefix="APP_")`` (classmethod): for every field,
      look up ``prefix + field_name.upper()`` in ``env`` (for example
      ``APP_PORT``). Convert the string to the field's type:

      * ``bool``: case-insensitive ``TRUE_STRINGS`` / ``FALSE_STRINGS``;
        anything else raises ``ValueError``. (``bool("false")`` is ``True``,
        which is why you need this.)
      * ``int`` / ``float`` / ``str``: call the type.

      Missing keys keep the default. Keys that do not match a field are
      ignored.
    * ``with_overrides(**changes)``: a modified copy made with
      ``dataclasses.replace``. An unknown field name raises ``TypeError``
      (``replace`` does that), and validation runs again.

    Hint: iterate over ``dataclasses.fields(cls)``. Get the real types from
    ``typing.get_type_hints(cls)``: with ``from __future__ import
    annotations`` at the top of this module, ``field.type`` is only the
    *string* ``"int"``.
    """

    host: str = "127.0.0.1"
    port: int = 8000
    debug: bool = False
    timeout_s: float = 5.0

    def __post_init__(self) -> None:
        raise NotImplementedError("TODO: implement this task")

    @classmethod
    def from_env(cls, env: Mapping[str, str], *, prefix: str = "APP_") -> Self:
        raise NotImplementedError("TODO: implement this task")

    def with_overrides(self, **changes: Any) -> Self:
        raise NotImplementedError("TODO: implement this task")
