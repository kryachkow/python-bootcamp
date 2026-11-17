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

# TODO: replace the placeholder below with the real definition(s).
class Shipment(BaseModel):
    """TODO: id, status, priority, and advance()."""

    def advance(self, to: ShipmentStatus | str) -> Shipment:
        raise NotImplementedError("TODO: implement this task")


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

# TODO: replace the placeholders below with the real definitions.
class TextChunk(BaseModel):
    """TODO: type tag + text."""


class ToolCall(BaseModel):
    """TODO: type tag + id, name, arguments."""


class ErrorEvent(BaseModel):
    """TODO: type tag + message, retryable."""


StreamEvent = TextChunk | ToolCall | ErrorEvent  # TODO: make it a discriminated union


class AgentTurn(BaseModel):
    """TODO: events + text() and tool_calls()."""

    def text(self) -> str:
        raise NotImplementedError("TODO: implement this task")

    def tool_calls(self) -> list[ToolCall]:
        raise NotImplementedError("TODO: implement this task")


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

# TODO: replace the placeholder below with the real definition(s).
class Page[T](BaseModel):
    """TODO: items, total, page, size + computed pages and has_next."""


def paginate[T](items: Sequence[T], page: int, size: int) -> Page[T]:
    """Return page number ``page`` (1-based) of ``items``, ``size`` items per page.

    * ``total`` is ``len(items)``.
    * A page past the end has ``items == []`` (not an error).
    * ``page < 1`` or ``size < 1`` raises ``ValueError`` (a ``ValidationError``
      from building the ``Page`` is fine: it is a ``ValueError`` subclass).

    >>> paginate(["a", "b", "c"], page=2, size=2)
    Page(items=['c'], total=3, page=2, size=2, pages=2, has_next=False)
    """
    raise NotImplementedError("TODO: implement this task")


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

# TODO: replace the placeholder below with the real definition(s).
class ApiResponse[T](BaseModel):
    """TODO: ok, data, error, the consistency rules, success() and failure()."""

    @classmethod
    def success(cls, data: T) -> Self:
        raise NotImplementedError("TODO: implement this task")

    @classmethod
    def failure(cls, error: str) -> Self:
        raise NotImplementedError("TODO: implement this task")


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

# TODO: create the two module-level TypeAdapters here.


def parse_events(raw: str | bytes) -> list[StreamEvent]:
    """Validate a JSON array of stream events (Task 2) into model instances.

    >>> parse_events('[{"type": "text", "text": "Hi"}]')
    [TextChunk(type='text', text='Hi')]

    Invalid JSON or invalid events raise ``ValidationError``.
    """
    raise NotImplementedError("TODO: implement this task")


def dump_events(events: Sequence[TextChunk | ToolCall | ErrorEvent]) -> bytes:
    """Serialize ``events`` back to a compact JSON array (``bytes``), e.g. for an SSE stream.

    ``parse_events(dump_events(events)) == list(events)``.
    """
    raise NotImplementedError("TODO: implement this task")


def parse_stock(data: Mapping[str, Any]) -> dict[str, int]:
    """Validate a ``{sku: quantity}`` mapping: quantities are ints >= 0.

    ``{"A": "3", "B": 0}`` -> ``{"A": 3, "B": 0}``. ``{"A": -1}`` raises
    ``ValidationError`` with ``loc == ("A",)`` and type ``"greater_than_equal"``.
    """
    raise NotImplementedError("TODO: implement this task")


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

# TODO: replace the placeholder below with the real definition(s).
class Tags(RootModel[list[str]]):
    """TODO: the two validators, __iter__, __len__, __contains__."""


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

# TODO: replace the placeholder below with the real definition(s).
class Category(BaseModel):
    """TODO: name, children, walk(), depth(), find()."""

    def walk(self) -> Iterator[str]:
        raise NotImplementedError("TODO: implement this task")

    def depth(self) -> int:
        raise NotImplementedError("TODO: implement this task")

    def find(self, name: str) -> Category | None:
        raise NotImplementedError("TODO: implement this task")


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

# TODO: replace the placeholder below with the real definition(s).
MoneyCents = int


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
        raise NotImplementedError("TODO: implement this task")
