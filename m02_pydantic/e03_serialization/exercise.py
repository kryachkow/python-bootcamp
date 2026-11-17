"""Exercise 2.3: serialization, aliases, computed fields, and JSON Schema.

Tasks 1-3 give you a model and ask for a function that dumps it the right
way. Tasks 4-8 ask you to write the model. Task 9 builds an LLM tool spec
from a JSON Schema. Run the tests with:

    uv run pytest m02_pydantic/e03_serialization
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import (
    AliasChoices,
    AliasPath,
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    computed_field,
    field_serializer,
    model_serializer,
)
from pydantic.alias_generators import to_camel, to_snake


# ---------------------------------------------------------------------------
# Task 1: dump to JSON-compatible data
# ---------------------------------------------------------------------------
class Invoice(BaseModel):
    """Given. Do not change."""

    id: UUID
    issued_at: datetime
    amount: Decimal
    currency: str = "EUR"
    paid_at: datetime | None = None
    notes: str | None = None
    tags: list[str] = []


def to_json_dict(invoice: Invoice) -> dict[str, Any]:
    """Return ``invoice`` as a dict that ``json.dumps`` can encode, without ``None`` values.

    * ``UUID`` -> ``str``, ``datetime`` -> ISO 8601 string (UTC is written
      as ``"...Z"``), ``Decimal`` -> ``str`` (``Decimal("12.50")`` -> ``"12.50"``).
    * Fields whose value is ``None`` are left out entirely.
    * Empty lists and other falsy values (``""``, ``0``) are kept.

    This is what you would put in a message queue, a cache, or an LLM prompt.

    Hint: ``model_dump(mode="json", exclude_none=True)``. The default
    ``mode="python"`` keeps ``UUID``/``datetime``/``Decimal`` objects.
    """
    return invoice.model_dump(mode="json", exclude_none=True)


# ---------------------------------------------------------------------------
# Task 2: PATCH semantics with exclude_unset
# ---------------------------------------------------------------------------
class UserProfile(BaseModel):
    """Given. The stored user."""

    id: int
    name: str
    bio: str | None = None
    age: int | None = None


class UserPatch(BaseModel):
    """Given. A PATCH body: every field is optional."""

    name: str | None = None
    bio: str | None = None
    age: int | None = None


def apply_patch(user: UserProfile, patch: UserPatch) -> UserProfile:
    """Return a NEW ``UserProfile`` with only the fields the client actually SENT applied.

    * A field the client did not send stays unchanged.
    * A field the client sent as ``null`` IS applied: ``{"bio": null}``
      clears the bio. (So ``exclude_none`` would be wrong here.)
    * ``user`` itself is not modified.

    >>> user = UserProfile(id=1, name="Ada", bio="math", age=36)
    >>> apply_patch(user, UserPatch.model_validate({"bio": None}))
    UserProfile(id=1, name='Ada', bio=None, age=36)

    Hint: ``patch.model_dump(exclude_unset=True)`` and ``model_copy(update=...)``.
    """
    return user.model_copy(update=patch.model_dump(exclude_unset=True))


# ---------------------------------------------------------------------------
# Task 3: hide private data with nested exclude
# ---------------------------------------------------------------------------
class Profile(BaseModel):
    """Given."""

    display_name: str
    internal_notes: str = ""


class LoginSession(BaseModel):
    """Given."""

    token: str
    ip: str


class UserRecord(BaseModel):
    """Given. A user row as the service stores it."""

    id: int
    email: str
    password_hash: str
    profile: Profile
    sessions: list[LoginSession] = []


def public_view(user: UserRecord) -> dict[str, Any]:
    """Return ``user`` as a dict that is safe to send to other users.

    Leave out:

    * ``password_hash``,
    * ``profile.internal_notes`` (keep ``profile.display_name``),
    * the ``token`` of EVERY session (keep each session's ``ip``).

    Everything else stays.

    Hint: ``exclude`` accepts nested sets/dicts, and ``"__all__"`` applies
    a rule to every item of a list:
    ``exclude={"profile": {"internal_notes"}, "sessions": {"__all__": {...}}}``.
    """
    return user.model_dump(
        exclude={
            "password_hash": True,
            "profile": {"internal_notes"},
            "sessions": {"__all__": {"token"}},
        }
    )


# ---------------------------------------------------------------------------
# Task 4: ExternalUser (alias, validation_alias, serialization_alias)
# ---------------------------------------------------------------------------
# A third-party API sends users in inconsistent shapes. Write an
# ``ExternalUser`` model:
#
#   | field        | type   | read from (validation)                         | written as (by_alias=True) |
#   |--------------|--------|------------------------------------------------|----------------------------|
#   | ``user_id``  | ``int`` | ``"id"``, ``"userId"`` or ``"user_id"``       | ``user_id``                |
#   | ``full_name`` | ``str`` | ``"fullName"`` only                          | ``fullName``               |
#   | ``email``    | ``str`` | ``"email"``                                   | ``emailAddress``           |
#   | ``is_admin`` | ``bool`` = ``False`` | nested ``{"permissions": {"admin": ...}}`` | ``is_admin``     |
#
# Hints: ``Field(validation_alias=AliasChoices(...))``, ``Field(alias=...)``
# (used for both directions), ``Field(serialization_alias=...)`` and
# ``AliasPath("permissions", "admin")``. Keys are only renamed on output
# when you call ``model_dump(by_alias=True)``.

class ExternalUser(BaseModel):
    user_id: int = Field(validation_alias=AliasChoices("id", "userId", "user_id"))
    full_name: str = Field(alias="fullName")
    email: str = Field(serialization_alias="emailAddress")
    is_admin: bool = Field(default=False, validation_alias=AliasPath("permissions", "admin"))


# ---------------------------------------------------------------------------
# Task 5: CamelModel base class and ProductOut (alias_generator)
# ---------------------------------------------------------------------------
# A JavaScript frontend wants camelCase JSON, your Python code wants
# snake_case. Write:
#
# ``CamelModel(BaseModel)`` with a ``model_config`` that
#   * generates a camelCase alias for every field (``to_camel``),
#   * accepts BOTH the alias and the field name on input
#     (``validate_by_alias=True`` and ``validate_by_name=True``; older code
#     uses ``populate_by_name=True`` for the same idea),
#   * writes aliases on output by default (``serialize_by_alias=True``), so
#     plain ``model_dump()`` / ``model_dump_json()`` produce camelCase.
#
# ``ProductOut(CamelModel)`` with ``product_id: int``, ``display_name: str``,
# ``unit_price_cents: int``, ``is_active: bool = True``.
#
# >>> ProductOut(product_id=1, display_name="Pen", unit_price_cents=150).model_dump()
# {'productId': 1, 'displayName': 'Pen', 'unitPriceCents': 150, 'isActive': True}

class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_alias=True,
        validate_by_name=True,
        serialize_by_alias=True,
    )


class ProductOut(CamelModel):
    product_id: int
    display_name: str
    unit_price_cents: int
    is_active: bool = True


# ---------------------------------------------------------------------------
# Task 6: Cart (computed_field)
# ---------------------------------------------------------------------------
# Write two models whose derived values are part of the output
# (``model_dump``, ``model_dump_json`` and the serialization JSON Schema),
# but can never be set by the client:
#
# ``CartLine``: ``sku: str``, ``quantity: int`` (>= 1), ``unit_price_cents: int`` (>= 0),
#   computed ``line_total_cents: int`` = ``quantity * unit_price_cents``.
#
# ``Cart``: ``lines: list[CartLine] = []``, ``discount_cents: int = 0`` (>= 0),
#   computed ``item_count: int`` = sum of all quantities,
#   computed ``subtotal_cents: int`` = sum of all line totals,
#   computed ``total_cents: int`` = ``subtotal_cents - discount_cents``, but never below 0.
#
# Hint: stack ``@computed_field`` on top of ``@property`` and give the
# property a return type annotation (it becomes the schema type).

class CartLine(BaseModel):
    sku: str
    quantity: int = Field(ge=1)
    unit_price_cents: int = Field(ge=0)

    @computed_field
    @property
    def line_total_cents(self) -> int:
        return self.quantity * self.unit_price_cents


class Cart(BaseModel):
    lines: list[CartLine] = []
    discount_cents: int = Field(default=0, ge=0)

    @computed_field
    @property
    def item_count(self) -> int:
        return sum(line.quantity for line in self.lines)

    @computed_field
    @property
    def subtotal_cents(self) -> int:
        return sum(line.line_total_cents for line in self.lines)

    @computed_field
    @property
    def total_cents(self) -> int:
        return max(0, self.subtotal_cents - self.discount_cents)


# ---------------------------------------------------------------------------
# Task 7: Event (field_serializer)
# ---------------------------------------------------------------------------
# Write an ``Event`` model with ``name: str``, ``starts_at: datetime``,
# ``duration: timedelta`` and ``tags: set[str] = set()``, plus three
# ``@field_serializer``s:
#
#   * ``starts_at`` -- in JSON mode ONLY (``when_used="json"``): convert to
#     UTC and format as ``"%Y-%m-%dT%H:%M:%SZ"`` (no microseconds). A naive
#     datetime is treated as already UTC. In python mode the ``datetime``
#     object is returned unchanged.
#   * ``duration`` -- always: whole seconds as an ``int``
#     (``timedelta(minutes=90)`` -> ``5400``), instead of Pydantic's
#     default ISO 8601 ``"PT1H30M"``.
#   * ``tags`` -- always: a sorted ``list`` (sets have no stable order, which
#     breaks caching and snapshot tests).
#
# >>> e = Event(name="standup", starts_at="2026-03-01T10:00:00+02:00", duration=900, tags={"b", "a"})
# >>> e.model_dump_json()
# '{"name":"standup","starts_at":"2026-03-01T08:00:00Z","duration":900,"tags":["a","b"]}'

class Event(BaseModel):
    name: str
    starts_at: datetime
    duration: timedelta
    tags: set[str] = set()

    @field_serializer("starts_at", when_used="json")
    def _serialize_starts_at(self, value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    @field_serializer("duration")
    def _serialize_duration(self, value: timedelta) -> int:
        return int(value.total_seconds())

    @field_serializer("tags")
    def _serialize_tags(self, value: set[str]) -> list[str]:
        return sorted(value)


# ---------------------------------------------------------------------------
# Task 8: ApiError (model_serializer, Field(exclude=True))
# ---------------------------------------------------------------------------
# Write an ``ApiError`` model that serializes as an error envelope:
#
#   * fields: ``code: str``, ``message: str``,
#     ``details: dict[str, Any] | None = None``,
#     ``status_code: int = 400`` -- this one is for the HTTP layer only and
#     must NEVER appear in the output (``Field(exclude=True)``).
#   * a ``@model_serializer(mode="wrap")`` that calls the default ``handler``
#     and wraps its result as ``{"error": {...}}``, dropping ``details``
#     when it is ``None``.
#
# >>> ApiError(code="not_found", message="No such user").model_dump()
# {'error': {'code': 'not_found', 'message': 'No such user'}}
# >>> ApiError(code="invalid", message="Bad", details={"field": "age"}, status_code=422).model_dump_json()
# '{"error":{"code":"invalid","message":"Bad","details":{"field":"age"}}}'
#
# Hint: the wrap serializer signature is
# ``def _envelope(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]``.
# ``mode="plain"`` would be the alternative when you build the dict yourself.

class ApiError(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None
    status_code: int = Field(default=400, exclude=True)

    @model_serializer(mode="wrap")
    def _envelope(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        data = handler(self)
        if data.get("details") is None:
            data.pop("details", None)
        return {"error": data}


# ---------------------------------------------------------------------------
# Task 9: an LLM tool spec from model_json_schema
# ---------------------------------------------------------------------------
def tool_spec(model_cls: type[BaseModel]) -> dict[str, Any]:
    """Describe ``model_cls`` as a function/tool definition for an LLM.

    Tool-calling APIs (OpenAI, Anthropic, LangChain's ``bind_tools``) take a
    JSON Schema of the arguments. Build it from ``model_cls.model_json_schema()``:

    * ``"name"``: the class name in snake_case (``SearchDocuments`` ->
      ``"search_documents"``).
    * ``"description"``: the schema's ``"description"`` (Pydantic takes it
      from the class docstring), or ``""`` if there is none.
    * ``"parameters"``: a dict with
        - ``"type": "object"``,
        - ``"properties"``: the schema's ``"properties"``, unchanged,
        - ``"required"``: the schema's ``"required"`` list, or ``[]``,
        - ``"$defs"``: the schema's ``"$defs"``, ONLY if it has any (nested
          models are defined there and referenced with ``"$ref"``).

    Hint: ``from pydantic.alias_generators import to_snake``.
    """
    schema = model_cls.model_json_schema()
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": schema["properties"],
        "required": schema.get("required", []),
    }
    if schema.get("$defs"):
        parameters["$defs"] = schema["$defs"]
    return {
        "name": to_snake(model_cls.__name__),
        "description": schema.get("description", ""),
        "parameters": parameters,
    }
