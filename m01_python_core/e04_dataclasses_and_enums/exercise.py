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

    PENDING = auto()
    PAID = auto()
    SHIPPED = auto()
    DELIVERED = auto()
    CANCELLED = auto()

    @property
    def is_final(self) -> bool:
        return not _TRANSITIONS[self]

    def can_transition_to(self, target: OrderStatus) -> bool:
        return target in _TRANSITIONS[self]

    def transition_to(self, target: OrderStatus) -> OrderStatus:
        if not self.can_transition_to(target):
            raise ValueError(f"cannot go from {self} to {target}")
        return target


_TRANSITIONS: dict[OrderStatus, frozenset[OrderStatus]] = {
    OrderStatus.PENDING: frozenset({OrderStatus.PAID, OrderStatus.CANCELLED}),
    OrderStatus.PAID: frozenset({OrderStatus.SHIPPED, OrderStatus.CANCELLED}),
    OrderStatus.SHIPPED: frozenset({OrderStatus.DELIVERED}),
    OrderStatus.DELIVERED: frozenset(),
    OrderStatus.CANCELLED: frozenset(),
}


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

    READ = auto()
    WRITE = auto()
    DELETE = auto()
    ADMIN = READ | WRITE | DELETE

    @classmethod
    def from_names(cls, names: Iterable[str]) -> Permission:
        result = cls(0)
        for name in names:
            key = name.strip().upper()
            if key not in cls.__members__:
                raise ValueError(f"unknown permission: {name!r}")
            result |= cls[key]
        return result

    def allows(self, required: Permission) -> bool:
        return self & required == required

    def names(self) -> list[str]:
        return [m.name.lower() for m in self if m.name]


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

    lat: float
    lon: float
    label: str = ""

    def distance_km(self, other: GeoPoint) -> float:
        phi1, phi2 = math.radians(self.lat), math.radians(other.lat)
        d_phi = phi2 - phi1
        d_lambda = math.radians(other.lon - self.lon)
        h = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
        return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(h))

    def with_label(self, label: str) -> GeoPoint:
        return self._replace(label=label)

    @classmethod
    def from_string(cls, text: str) -> GeoPoint:
        parts = [p.strip() for p in text.split(",")]
        if len(parts) not in (2, 3):
            raise ValueError(f"expected 'lat,lon[,label]', got {text!r}")
        lat, lon = float(parts[0]), float(parts[1])  # float() raises ValueError itself
        if not -90 <= lat <= 90:
            raise ValueError(f"latitude out of range: {lat}")
        if not -180 <= lon <= 180:
            raise ValueError(f"longitude out of range: {lon}")
        return cls(lat, lon, parts[2] if len(parts) == 3 else "")


# ---------------------------------------------------------------------------
# Task 4: frozen + ordered dataclass
# ---------------------------------------------------------------------------
# Replace the plain ``@dataclass`` below so that ``Version`` is frozen
# (immutable and hashable) and ordered (``<`` compares fields in order).
@dataclass(frozen=True, order=True)
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
        for f in fields(self):
            value = getattr(self, f.name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{f.name} must be an int")
            if value < 0:
                raise ValueError(f"{f.name} must be >= 0")

    @classmethod
    def parse(cls, text: str) -> Self:
        parts = text.removeprefix("v").split(".")
        if len(parts) != 3 or not all(p.isdigit() for p in parts):
            raise ValueError(f"invalid version: {text!r}")
        major, minor, patch = (int(p) for p in parts)
        return cls(major, minor, patch)

    def bump(self, part: Literal["major", "minor", "patch"]) -> Self:
        match part:
            case "major":
                return replace(self, major=self.major + 1, minor=0, patch=0)
            case "minor":
                return replace(self, minor=self.minor + 1, patch=0)
            case "patch":
                return replace(self, patch=self.patch + 1)
        raise ValueError(f"unknown part: {part!r}")

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


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
        self.sku = self.sku.strip().upper()
        if not self.sku:
            raise ValueError("sku must not be empty")
        if isinstance(self.unit_price, float):
            raise TypeError("unit_price must not be a float")
        self.unit_price = Decimal(self.unit_price)
        if self.unit_price < 0:
            raise ValueError("unit_price must be >= 0")
        if isinstance(self.quantity, bool) or not isinstance(self.quantity, int):
            raise TypeError("quantity must be an int")
        if self.quantity < 1:
            raise ValueError("quantity must be >= 1")

    @property
    def subtotal(self) -> Decimal:
        return self.unit_price * self.quantity


# ---------------------------------------------------------------------------
# Task 6: kw_only, default_factory, field options
# ---------------------------------------------------------------------------
# Replace the plain ``@dataclass`` below with a keyword-only one.
@dataclass(kw_only=True)
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

    id: str
    customer_email: str
    items: list[LineItem] = field(default_factory=list)
    tags: set[str] = field(default_factory=set)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC), compare=False)

    def add_item(self, item: LineItem) -> None:
        for i, existing in enumerate(self.items):
            if existing.sku == item.sku:
                if existing.unit_price != item.unit_price:
                    raise ValueError(f"price mismatch for {item.sku}")
                self.items[i] = replace(existing, quantity=existing.quantity + item.quantity)
                return
        self.items.append(item)

    @property
    def total(self) -> Decimal:
        return sum((item.subtotal for item in self.items), Decimal("0"))


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
        if not 1 <= self.port <= 65535:
            raise ValueError(f"port out of range: {self.port}")
        if self.timeout_s <= 0:
            raise ValueError("timeout_s must be > 0")

    @classmethod
    def from_env(cls, env: Mapping[str, str], *, prefix: str = "APP_") -> Self:
        hints = get_type_hints(cls)
        kwargs: dict[str, Any] = {}
        for f in fields(cls):
            key = prefix + f.name.upper()
            if key not in env:
                continue
            raw, typ = env[key], hints[f.name]
            if typ is bool:
                lowered = raw.strip().lower()
                if lowered in TRUE_STRINGS:
                    kwargs[f.name] = True
                elif lowered in FALSE_STRINGS:
                    kwargs[f.name] = False
                else:
                    raise ValueError(f"{key}: not a boolean: {raw!r}")
            else:
                kwargs[f.name] = typ(raw)
        return cls(**kwargs)

    def with_overrides(self, **changes: Any) -> Self:
        return replace(self, **changes)
