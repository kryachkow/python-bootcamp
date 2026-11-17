"""Exercise 2.4: advanced types.

Enums, discriminated unions, generic models, ``TypeAdapter``, ``RootModel``,
recursive models, and custom types. Run the tests with:

    uv run pytest m02_pydantic/e04_advanced_types
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import IntEnum, StrEnum
from typing import Annotated, Any, ClassVar, Literal, Self

from pydantic import (
    BaseModel,
    BeforeValidator,
    Field,
    GetCoreSchemaHandler,
    NonNegativeInt,
    PlainSerializer,
    RootModel,
    TypeAdapter,
    WithJsonSchema,
    computed_field,
    field_validator,
    model_validator,
)
from pydantic_core import core_schema


# ---------------------------------------------------------------------------
# Task 1: Shipment (Enum fields)
# ---------------------------------------------------------------------------
class ShipmentStatus(StrEnum):
    """Given. A ``StrEnum`` member is also a ``str``: ``ShipmentStatus.PAID == "paid"``."""

    PENDING = "pending"
    PAID = "paid"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class Priority(IntEnum):
    """Given."""

    LOW = 1
    NORMAL = 2
    HIGH = 3


ALLOWED_TRANSITIONS: dict[ShipmentStatus, set[ShipmentStatus]] = {
    ShipmentStatus.PENDING: {ShipmentStatus.PAID, ShipmentStatus.CANCELLED},
    ShipmentStatus.PAID: {ShipmentStatus.SHIPPED, ShipmentStatus.CANCELLED},
    ShipmentStatus.SHIPPED: {ShipmentStatus.DELIVERED},
    ShipmentStatus.DELIVERED: set(),
    ShipmentStatus.CANCELLED: set(),
}
"""Given. Which status may follow which."""

# Write a ``Shipment`` model:
#
#   * ``id: str``
#   * ``status: ShipmentStatus = ShipmentStatus.PENDING``: input ``"paid"``
#     becomes ``ShipmentStatus.PAID``; an unknown value fails with type ``"enum"``.
#   * ``priority: Priority = Priority.NORMAL``: input ``3`` or ``"3"`` becomes
#     ``Priority.HIGH``.
#   * method ``advance(self, to: ShipmentStatus | str) -> Shipment``: return a
#     NEW shipment with ``status=to`` if ``ALLOWED_TRANSITIONS`` allows it,
#     otherwise raise ``ValueError(f"cannot go from {old} to {new}")``. A
#     string such as ``"shipped"`` must work too (convert it with
#     ``ShipmentStatus(to)``).
#
# In JSON the enums are written as their values: ``{"status": "paid", "priority": 2}``.
# (``ConfigDict(use_enum_values=True)`` would store raw values instead of
# members; do NOT use it here, members are more useful in code.)

class Shipment(BaseModel):
    id: str
    status: ShipmentStatus = ShipmentStatus.PENDING
    priority: Priority = Priority.NORMAL

    def advance(self, to: ShipmentStatus | str) -> Shipment:
        new = ShipmentStatus(to)
        if new not in ALLOWED_TRANSITIONS[self.status]:
            raise ValueError(f"cannot go from {self.status} to {new}")
        return self.model_copy(update={"status": new})


# ---------------------------------------------------------------------------
# Task 2: LLM stream events (discriminated union)
# ---------------------------------------------------------------------------
# An agent streams events of three kinds. Each one carries a ``type`` tag:
#
#   | model        | ``type`` (Literal, with that default) | other fields                                        |
#   |--------------|---------------------------------------|-----------------------------------------------------|
#   | ``TextChunk``  | ``"text"``                          | ``text: str``                                       |
#   | ``ToolCall``   | ``"tool_call"``                     | ``id: str``, ``name: str``, ``arguments: dict[str, Any] = {}`` |
#   | ``ErrorEvent`` | ``"error"``                         | ``message: str``, ``retryable: bool = False``       |
#
# Then define
#
#   * ``StreamEvent = Annotated[TextChunk | ToolCall | ErrorEvent, Field(discriminator="type")]``
#     Pydantic reads the tag and validates against that ONE model, instead of
#     trying every member. Errors are clearer: an unknown tag fails with
#     ``"union_tag_invalid"``, a missing tag with ``"union_tag_not_found"``,
#     and field errors are located under the tag, e.g.
#     ``("events", 1, "tool_call", "name")``.
#   * ``AgentTurn(BaseModel)`` with ``events: list[StreamEvent]`` and methods
#       - ``text() -> str``: all ``TextChunk.text`` values joined with ``""``,
#       - ``tool_calls() -> list[ToolCall]``: the tool calls, in order.

class TextChunk(BaseModel):
    type: Literal["text"] = "text"
    text: str


class ToolCall(BaseModel):
    type: Literal["tool_call"] = "tool_call"
    id: str
    name: str
    arguments: dict[str, Any] = {}


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    message: str
    retryable: bool = False


StreamEvent = Annotated[TextChunk | ToolCall | ErrorEvent, Field(discriminator="type")]


class AgentTurn(BaseModel):
    events: list[StreamEvent]

    def text(self) -> str:
        return "".join(e.text for e in self.events if isinstance(e, TextChunk))

    def tool_calls(self) -> list[ToolCall]:
        return [e for e in self.events if isinstance(e, ToolCall)]


# ---------------------------------------------------------------------------
# Task 3: Page[T] (generic model) and paginate
# ---------------------------------------------------------------------------
# Write a generic ``Page[T]`` model (``class Page[T](BaseModel)``, or the
# older ``class Page(BaseModel, Generic[T])``):
#
#   * ``items: list[T]``, ``total: int`` (>= 0), ``page: int`` (>= 1),
#     ``size: int`` (>= 1)
#   * computed field ``pages: int``: ``ceil(total / size)`` (``0`` when ``total == 0``)
#   * computed field ``has_next: bool``: ``page < pages``
#
# ``Page[User].model_validate({...})`` validates every item as a ``User``;
# ``Page[int]`` coerces ``"1"`` to ``1``.

class Page[T](BaseModel):
    items: list[T]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    size: int = Field(ge=1)

    @computed_field
    @property
    def pages(self) -> int:
        return math.ceil(self.total / self.size)

    @computed_field
    @property
    def has_next(self) -> bool:
        return self.page < self.pages


def paginate[T](items: Sequence[T], page: int, size: int) -> Page[T]:
    """Return page number ``page`` (1-based) of ``items``, ``size`` items per page.

    * ``total`` is ``len(items)``.
    * A page past the end has ``items == []`` (not an error).
    * ``page < 1`` or ``size < 1`` raises ``ValueError`` (a ``ValidationError``
      from building the ``Page`` is fine: it is a ``ValueError`` subclass).

    >>> paginate(["a", "b", "c"], page=2, size=2)
    Page(items=['c'], total=3, page=2, size=2, pages=2, has_next=False)
    """
    if page < 1 or size < 1:
        raise ValueError("page and size must be >= 1")
    start = (page - 1) * size
    return Page(items=list(items[start : start + size]), total=len(items), page=page, size=size)


# ---------------------------------------------------------------------------
# Task 4: ApiResponse[T] (generic model with a model validator)
# ---------------------------------------------------------------------------
# Write a generic response envelope ``ApiResponse[T]``:
#
#   * ``ok: bool``, ``data: T | None = None``, ``error: str | None = None``
#   * an after model validator:
#       - ``ok=True`` with an ``error`` -> ``ValueError("successful response cannot have an error")``
#       - ``ok=False`` without an ``error`` -> ``ValueError("failed response needs an error")``
#       - ``ok=False`` with ``data`` -> ``ValueError("failed response cannot have data")``
#   * classmethods ``success(data)`` and ``failure(error)`` returning
#     ``cls(...)``. Called on a parametrised class they validate the data:
#     ``ApiResponse[int].success("5").data == 5``.
#
# Hint: annotate the classmethods' return type as ``Self``.

class ApiResponse[T](BaseModel):
    ok: bool
    data: T | None = None
    error: str | None = None

    @model_validator(mode="after")
    def _check_consistency(self) -> Self:
        if self.ok and self.error is not None:
            raise ValueError("successful response cannot have an error")
        if not self.ok and self.error is None:
            raise ValueError("failed response needs an error")
        if not self.ok and self.data is not None:
            raise ValueError("failed response cannot have data")
        return self

    @classmethod
    def success(cls, data: T) -> Self:
        return cls(ok=True, data=data)

    @classmethod
    def failure(cls, error: str) -> Self:
        return cls(ok=False, error=error)


# ---------------------------------------------------------------------------
# Task 5: TypeAdapter (validate things that are not models)
# ---------------------------------------------------------------------------
# A ``TypeAdapter`` gives any type (``list[Model]``, ``dict[str, int]``, a
# union) the ``validate_python`` / ``validate_json`` / ``dump_json`` API of a
# model. Building one compiles a validator, which is not free, so create
# them ONCE at module level and reuse them:
#
#   * ``_EVENTS_ADAPTER = TypeAdapter(list[StreamEvent])``
#   * ``_STOCK_ADAPTER = TypeAdapter(dict[str, NonNegativeInt])``
#
# then implement the three functions below.

_EVENTS_ADAPTER: TypeAdapter[list[StreamEvent]] = TypeAdapter(list[StreamEvent])
_STOCK_ADAPTER: TypeAdapter[dict[str, int]] = TypeAdapter(dict[str, NonNegativeInt])


def parse_events(raw: str | bytes) -> list[StreamEvent]:
    """Validate a JSON array of stream events (Task 2) into model instances.

    >>> parse_events('[{"type": "text", "text": "Hi"}]')
    [TextChunk(type='text', text='Hi')]

    Invalid JSON or invalid events raise ``ValidationError``.
    """
    return _EVENTS_ADAPTER.validate_json(raw)


def dump_events(events: Sequence[TextChunk | ToolCall | ErrorEvent]) -> bytes:
    """Serialize ``events`` back to a compact JSON array (``bytes``), e.g. for an SSE stream.

    ``parse_events(dump_events(events)) == list(events)``.
    """
    return _EVENTS_ADAPTER.dump_json(list(events))


def parse_stock(data: Mapping[str, Any]) -> dict[str, int]:
    """Validate a ``{sku: quantity}`` mapping: quantities are ints >= 0.

    ``{"A": "3", "B": 0}`` -> ``{"A": 3, "B": 0}``. ``{"A": -1}`` raises
    ``ValidationError`` with ``loc == ("A",)`` and type ``"greater_than_equal"``.
    """
    return _STOCK_ADAPTER.validate_python(data)


# ---------------------------------------------------------------------------
# Task 6: Tags (RootModel)
# ---------------------------------------------------------------------------
# Some JSON documents are not objects: a bare array or a bare string. A
# ``RootModel`` wraps such a value in ``.root`` and (de)serializes it
# without a wrapper key. Write ``Tags(RootModel[list[str]])``:
#
#   * input: a list of strings, OR one comma-separated string
#     (``"Python, pydantic"``), handled by a ``mode="before"`` validator;
#   * normalised (``mode="after"``): every tag stripped and lowercased, empty
#     tags dropped, duplicates removed keeping the first occurrence;
#   * ``__iter__`` over the tags, ``__len__``, and ``__contains__(tag)``
#     which also normalises its argument (``" PYTHON " in tags`` is ``True``).
#
# >>> tags = Tags(["Python", " pydantic ", "python", ""])
# >>> tags.root
# ['python', 'pydantic']
# >>> tags.model_dump_json()
# '["python","pydantic"]'
#
# Hint: in a ``RootModel`` the single field is called ``"root"``, so
# ``@field_validator("root", mode=...)`` works.

class Tags(RootModel[list[str]]):
    @field_validator("root", mode="before")
    @classmethod
    def _split(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.split(",")
        return value

    @field_validator("root")
    @classmethod
    def _normalise(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(t.strip().lower() for t in value if t.strip()))

    def __iter__(self) -> Iterator[str]:  # type: ignore[override]
        return iter(self.root)

    def __len__(self) -> int:
        return len(self.root)

    def __contains__(self, tag: object) -> bool:
        return isinstance(tag, str) and tag.strip().lower() in self.root


# ---------------------------------------------------------------------------
# Task 7: Category tree (recursive model)
# ---------------------------------------------------------------------------
# Write a self-referencing ``Category`` model:
#
#   * ``name: str`` (at least 1 character)
#   * ``children: list[Category] = []``  (with ``from __future__ import
#     annotations``, as in this file, Pydantic resolves the self-reference)
#   * ``walk() -> Iterator[str]``: names in depth-first pre-order (the node,
#     then each child's subtree, left to right)
#   * ``depth() -> int``: ``1`` for a leaf, otherwise ``1 + max(child depths)``
#   * ``find(name) -> Category | None``: the first node (pre-order) with that
#     name, or ``None``
#
# A nested JSON document validates in one call, and errors point into the
# tree, e.g. ``("children", 0, "children", 1, "name")``.

class Category(BaseModel):
    name: str = Field(min_length=1)
    children: list[Category] = []

    def walk(self) -> Iterator[str]:
        yield self.name
        for child in self.children:
            yield from child.walk()

    def depth(self) -> int:
        return 1 + max((child.depth() for child in self.children), default=0)

    def find(self, name: str) -> Category | None:
        if self.name == name:
            return self
        for child in self.children:
            if (found := child.find(name)) is not None:
                return found
        return None


# ---------------------------------------------------------------------------
# Task 8: MoneyCents (custom type with Annotated + PlainSerializer)
# ---------------------------------------------------------------------------
# Store money as integer cents in Python, but accept and emit decimal
# strings on the wire. Define
#
#   ``MoneyCents = Annotated[int, BeforeValidator(...), PlainSerializer(..., return_type=str), WithJsonSchema(...)]``
#
#   * input: ``"12.34"``, ``12.34``, ``Decimal("12.34")`` -> ``1234``;
#     ``12`` or ``"12"`` -> ``1200``; ``"-0.5"`` -> ``-50``. Convert through
#     ``Decimal(str(value))`` so floats do not lose precision.
#   * ``bool`` input, non-numeric strings, or other types ->
#     ``ValueError("invalid amount")``; more than 2 decimal places ->
#     ``ValueError("at most 2 decimal places")``.
#   * output (python AND json mode): a string with exactly two decimals:
#     ``1234`` -> ``"12.34"``, ``-50`` -> ``"-0.50"``, ``0`` -> ``"0.00"``.
#   * JSON Schema: exactly
#     ``{"type": "string", "pattern": r"^-?\d+(\.\d{1,2})?$", "examples": ["12.34"]}``
#     (``WithJsonSchema``), because the schema derived from ``int`` would lie.

def _to_cents(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        raise ValueError("invalid amount")
    try:
        amount = Decimal(str(value).strip())
    except InvalidOperation:
        raise ValueError("invalid amount") from None
    if not amount.is_finite():
        raise ValueError("invalid amount")
    if amount != amount.quantize(Decimal("0.01")):
        raise ValueError("at most 2 decimal places")
    return int(amount * 100)


def _cents_to_str(cents: int) -> str:
    return f"{Decimal(cents) / 100:.2f}"


MoneyCents = Annotated[
    int,
    BeforeValidator(_to_cents),
    PlainSerializer(_cents_to_str, return_type=str),
    WithJsonSchema({"type": "string", "pattern": r"^-?\d+(\.\d{1,2})?$", "examples": ["12.34"]}),
]


# ---------------------------------------------------------------------------
# Task 9: SemVer (custom type with __get_pydantic_core_schema__)
# ---------------------------------------------------------------------------
@dataclass(frozen=True, order=True)
class SemVer:
    """A semantic version such as ``1.4.2``. Given, except for the Pydantic hook.

    Instances compare by ``(major, minor, patch)``, so ``SemVer.parse("1.10.0") >
    SemVer.parse("1.9.9")``, which string comparison gets wrong.
    """

    major: int
    minor: int
    patch: int

    _PATTERN: ClassVar[re.Pattern[str]] = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")

    @classmethod
    def parse(cls, value: str) -> SemVer:
        match = cls._PATTERN.fullmatch(value.strip())
        if not match:
            raise ValueError(f"invalid semantic version: {value!r}")
        return cls(*(int(part) for part in match.groups()))

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: Any, handler: GetCoreSchemaHandler) -> core_schema.CoreSchema:
        """Teach Pydantic how to validate and serialize ``SemVer`` fields.

        Return a core schema such that a model field ``version: SemVer``:

        * accepts a ``SemVer`` instance unchanged (python input only),
        * accepts a ``str`` (python or JSON input) and parses it with
          ``SemVer.parse``; its ``ValueError`` becomes a ``ValidationError``
          entry with type ``"value_error"``,
        * rejects other types (e.g. ``123``),
        * serializes as the string ``"1.4.2"`` (``str(version)``) in both
          python and json mode,
        * appears in JSON Schema as ``{"type": "string"}``.

        Hint: ``core_schema.json_or_python_schema(json_schema=..., python_schema=...,
        serialization=...)`` with ``chain_schema([str_schema(),
        no_info_plain_validator_function(cls.parse)])``, ``union_schema``,
        ``is_instance_schema(cls)`` and
        ``plain_serializer_function_ser_schema(str, return_schema=str_schema())``
        (without ``return_schema`` the serialization-mode JSON Schema fails).
        """
        from_str = core_schema.chain_schema(
            [core_schema.str_schema(), core_schema.no_info_plain_validator_function(cls.parse)]
        )
        return core_schema.json_or_python_schema(
            json_schema=from_str,
            python_schema=core_schema.union_schema([core_schema.is_instance_schema(cls), from_str]),
            serialization=core_schema.plain_serializer_function_ser_schema(
                str, return_schema=core_schema.str_schema()
            ),
        )
