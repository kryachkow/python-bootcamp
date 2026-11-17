"""Exercise 2.1: Pydantic v2 model basics.

Each task asks you to write a model or a small function around one. The
docstrings say exactly what to build. Run the tests with:

    uv run pytest m02_pydantic/e01_models_basics
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError


# ---------------------------------------------------------------------------
# Task 1: Product (fields, defaults, optional fields, default_factory)
# ---------------------------------------------------------------------------
# Write a ``Product`` model with these fields:
#
#   | field         | type          | required? | default                          |
#   |---------------|---------------|-----------|----------------------------------|
#   | ``id``        | ``int``       | yes       |                                  |
#   | ``name``      | ``str``       | yes       |                                  |
#   | ``price``     | ``float``     | yes       |                                  |
#   | ``in_stock``  | ``bool``      | no        | ``True``                         |
#   | ``tags``      | ``list[str]`` | no        | a NEW empty list for each object |
#   | ``description`` | ``str | None`` | no     | ``None``                         |
#
# Use the default lax mode, so Pydantic coerces "obvious" input:
# ``Product(id="7", name="Pen", price="1.5", in_stock="yes")`` gives
# ``id == 7``, ``price == 1.5`` and ``in_stock is True``.
#
# Hint: ``Field(default_factory=list)``. (Pydantic copies a mutable default
# such as ``[]`` for you, but ``default_factory`` states the intent and works
# for any callable, e.g. ``uuid4`` or ``datetime.now``.)

# TODO: replace the placeholder below with the real definition(s).
class Product(BaseModel):
    """A catalogue item. TODO: add the fields from the table above."""


# ---------------------------------------------------------------------------
# Task 2: StrictPayment (strict mode)
# ---------------------------------------------------------------------------
# Money must never be guessed. Write a ``StrictPayment`` model that turns
# off coercion for the whole model (``ConfigDict(strict=True)``):
#
#   * ``amount_cents: int``: ``"100"``, ``100.0`` and ``True`` are rejected,
#     only a real ``int`` is accepted.
#   * ``currency: str``: a 3-letter code such as ``"EUR"`` (no extra checks).
#   * ``captured: bool = False``: ``"true"`` and ``1`` are rejected.
#
# ``StrictPayment(amount_cents="100", currency="EUR")`` raises a
# ``ValidationError`` whose error ``type`` is ``"int_type"``.
#
# Hint: you could also mark single fields with ``Field(strict=True)`` or
# validate one call strictly with ``Model.model_validate(data, strict=True)``.

# TODO: replace the placeholder below with the real definition(s).
class StrictPayment(BaseModel):
    """TODO: strict config + amount_cents, currency, captured."""


# ---------------------------------------------------------------------------
# Task 3: nested models (Address, OrderItem, Order)
# ---------------------------------------------------------------------------
# Write three models. Pydantic validates nested dicts into nested models and
# reports errors with the full path, e.g. ``("items", 1, "quantity")``.
#
# ``Address``:
#   * ``street: str``, ``city: str``, ``country_code: str = "UA"``
#
# ``OrderItem``:
#   * ``sku: str``
#   * ``quantity: int`` (must be >= 1, use ``Field(ge=1)``)
#   * ``unit_price: Decimal`` (``"9.99"`` and ``9.99`` both become a Decimal)
#
# ``Order``:
#   * ``id: int``
#   * ``shipping_address: Address``
#   * ``items: list[OrderItem]`` (required, may be empty)
#   * ``note: str | None = None``
#   * method ``total() -> Decimal``: the sum of ``quantity * unit_price`` over
#     all items, ``Decimal("0")`` for an order with no items.
#
# >>> order = Order.model_validate({
# ...     "id": 1,
# ...     "shipping_address": {"street": "Khreshchatyk 1", "city": "Kyiv"},
# ...     "items": [{"sku": "A", "quantity": 2, "unit_price": "1.25"}],
# ... })
# >>> order.total()
# Decimal('2.50')

# TODO: replace the placeholder below with the real definition(s).
class Address(BaseModel):
    """TODO: street, city, country_code."""


class OrderItem(BaseModel):
    """TODO: sku, quantity (>= 1), unit_price (Decimal)."""


class Order(BaseModel):
    """TODO: id, shipping_address, items, note, and total()."""

    def total(self) -> Decimal:
        raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 4: parse an incoming order
# ---------------------------------------------------------------------------
def parse_order(payload: str | bytes | dict[str, Any]) -> Order:
    """Validate an order that arrives as a JSON string, JSON bytes, or a dict.

    * ``str`` or ``bytes``: parse it with ``Order.model_validate_json``. Do not
      call ``json.loads`` first: Pydantic's JSON parser is faster and reports
      invalid JSON as a ``ValidationError`` (error type ``"json_invalid"``).
    * ``dict``: use ``Order.model_validate``.
    * Any other type: raise ``TypeError``.
    * Validation errors propagate unchanged as ``ValidationError``.

    >>> parse_order('{"id": 1, "shipping_address": {"street": "s", "city": "c"}, "items": []}').id
    1
    """
    raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 5: turn a ValidationError into an API error body
# ---------------------------------------------------------------------------
def format_errors(exc: ValidationError) -> list[dict[str, str]]:
    """Convert ``exc`` into a list of simple, JSON-friendly error dicts.

    Return one dict per entry of ``exc.errors()``, in the same order, with:

    * ``"field"``: the ``loc`` tuple joined with ``"."``; integer indexes
      become strings, e.g. ``("items", 0, "quantity")`` -> ``"items.0.quantity"``.
      An empty ``loc`` (a model-level error) becomes ``"__root__"``.
    * ``"code"``: the error ``type``, e.g. ``"missing"`` or ``"int_parsing"``.
    * ``"message"``: the error ``msg``, e.g. ``"Field required"``.

    This is the shape many APIs return instead of FastAPI's default 422 body.

    Hint: ``exc.errors()`` returns a list of dicts with keys ``type``,
    ``loc``, ``msg``, ``input`` (and more).
    """
    raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 6: apply a discount with model_copy
# ---------------------------------------------------------------------------
def apply_discount(product: Product, percent: float) -> Product:
    """Return a copy of ``product`` with its price lowered by ``percent``.

    * ``percent`` is between 0 and 100 inclusive, otherwise raise ``ValueError``.
    * The new price is ``round(price * (1 - percent / 100), 2)``.
    * Do not change the original product. Every other field stays the same.

    >>> apply_discount(Product(id=1, name="Pen", price=10.0), 25).price
    7.5

    Hint: ``product.model_copy(update={...})``.
    """
    raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 7: a validated copy
# ---------------------------------------------------------------------------
def with_changes[M: BaseModel](model: M, **changes: Any) -> M:
    """Return a new instance of ``type(model)`` with ``changes`` applied and VALIDATED.

    ``model_copy(update=...)`` does NOT validate: ``p.model_copy(update={"price": "abc"})``
    happily stores the string ``"abc"``. This helper must instead:

    * merge ``model.model_dump()`` with ``changes`` (changes win),
    * validate the result with ``type(model).model_validate(...)``, so values
      are coerced (``price="9.5"`` -> ``9.5``) and bad values raise
      ``ValidationError``,
    * leave ``model`` unchanged.

    It works for any model, not only ``Product``.
    """
    raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 8: clone an order (deep copy)
# ---------------------------------------------------------------------------
def clone_order(order: Order, new_id: int) -> Order:
    """Return an independent copy of ``order`` with ``id`` set to ``new_id``.

    The copy must share NO mutable state with the original: appending to
    ``clone.items`` or changing ``clone.shipping_address.city`` must not
    affect ``order``.

    Hint: ``model_copy`` is shallow by default; pass ``deep=True``.
    """
    raise NotImplementedError("TODO: implement this task")
