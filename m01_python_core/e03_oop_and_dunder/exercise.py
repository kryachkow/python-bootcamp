"""Exercise 1.3: classes, properties, dunder methods, ABCs, and mixins.

Implement every method marked as a task below. Each one says what it must do
in its docstring. Run the tests with:

    uv run pytest m01_python_core/e03_oop_and_dunder
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation
from functools import total_ordering
from typing import Any, NamedTuple, overload


# ---------------------------------------------------------------------------
# Task 1: properties with validation
# ---------------------------------------------------------------------------
class Temperature:
    """A temperature, stored in degrees Celsius.

    * ``celsius`` is a read/write property. The setter raises ``TypeError``
      if the value is not an ``int`` or ``float`` (``bool`` is rejected too,
      even though it is a subclass of ``int``). It raises ``ValueError`` if the
      value is below absolute zero (``-273.15``). It stores the value as a
      ``float`` in ``self._celsius``.
    * ``fahrenheit`` is a read/write property computed from ``celsius``
      (``F = C * 9 / 5 + 32``). Setting it converts back and goes through the
      ``celsius`` setter, so the same validation applies.
    * ``kelvin`` is a read-only property (``K = C + 273.15``). Assigning to it
      must raise ``AttributeError``. A property without a setter does that
      for you.

    >>> t = Temperature(100)
    >>> t.fahrenheit
    212.0
    >>> t.fahrenheit = 32
    >>> t.celsius
    0.0
    """

    ABSOLUTE_ZERO_C = -273.15

    def __init__(self, celsius: float) -> None:
        self.celsius = celsius  # goes through the property setter

    @property
    def celsius(self) -> float:
        return self._celsius

    @celsius.setter
    def celsius(self, value: float) -> None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"temperature must be a number, got {type(value).__name__}")
        if value < self.ABSOLUTE_ZERO_C:
            raise ValueError(f"{value} is below absolute zero")
        self._celsius = float(value)

    @property
    def fahrenheit(self) -> float:
        return self.celsius * 9 / 5 + 32

    @fahrenheit.setter
    def fahrenheit(self, value: float) -> None:
        self.celsius = (value - 32) * 5 / 9

    @property
    def kelvin(self) -> float:
        return self.celsius - self.ABSOLUTE_ZERO_C


# ---------------------------------------------------------------------------
# Money: a value object used by tasks 2-4. ``__init__`` and the read-only
# properties are given.
# ---------------------------------------------------------------------------
class CurrencyMismatchError(ValueError):
    """Raised when an operation mixes two different currencies."""


CENT = Decimal("0.01")


@total_ordering
class Money:
    """An amount of money in one currency, such as ``Money("12.50", "USD")``.

    A ``Money`` is immutable: there are no setters, and every operation
    returns a new object. That is what makes it safe to hash.

    * ``amount`` is a ``Decimal`` rounded to cents (banker's rounding).
      ``float`` is rejected because ``0.1 + 0.2 != 0.3`` in binary floating
      point.
    * ``currency`` is a three-letter code, stored uppercase.
    """

    def __init__(self, amount: Decimal | int | str, currency: str) -> None:
        if isinstance(amount, float):
            raise TypeError("use Decimal, int or str for money, never float")
        try:
            value = Decimal(amount)
        except InvalidOperation:
            raise ValueError(f"invalid amount: {amount!r}") from None
        code = currency.strip().upper()
        if len(code) != 3 or not code.isalpha():
            raise ValueError(f"invalid currency code: {currency!r}")
        self._amount = value.quantize(CENT, rounding=ROUND_HALF_EVEN)
        self._currency = code

    @property
    def amount(self) -> Decimal:
        return self._amount

    @property
    def currency(self) -> str:
        return self._currency

    # -----------------------------------------------------------------------
    # Task 2: value semantics (__repr__, __str__, __eq__, __hash__)
    # -----------------------------------------------------------------------
    def __repr__(self) -> str:
        """Return ``Money('12.50', 'USD')``: the amount as a quoted string."""
        return f"Money({str(self.amount)!r}, {self.currency!r})"

    def __str__(self) -> str:
        """Return ``12.50 USD``."""
        return f"{self.amount} {self.currency}"

    def __eq__(self, other: object) -> bool:
        """Two ``Money`` objects are equal if amount and currency are equal.

        Comparing with anything that is not a ``Money`` returns
        ``NotImplemented`` (not ``False``), so Python can try the other
        operand and then fall back to identity, which makes ``==`` give
        ``False``.
        """
        if not isinstance(other, Money):
            return NotImplemented
        return (self.amount, self.currency) == (other.amount, other.currency)

    def __hash__(self) -> int:
        """Hash the same fields that ``__eq__`` compares.

        A class that defines ``__eq__`` gets ``__hash__ = None`` unless it
        defines ``__hash__`` too. Equal objects must have equal hashes.
        """
        return hash((self.amount, self.currency))

    # -----------------------------------------------------------------------
    # Task 3: arithmetic operators
    # -----------------------------------------------------------------------
    def __add__(self, other: Money) -> Money:
        """``Money + Money`` with the same currency returns a new ``Money``.

        * Different currencies: raise ``CurrencyMismatchError``.
        * Any other type: return ``NotImplemented``, so Python raises
          ``TypeError`` for you.
        """
        if not isinstance(other, Money):
            return NotImplemented
        self._check_currency(other)
        return Money(self.amount + other.amount, self.currency)

    def __radd__(self, other: object) -> Money:
        """Support ``sum(list_of_money)``.

        ``sum`` starts with ``0 + first_item``, and ``int.__add__`` does not
        know ``Money``, so Python calls ``first_item.__radd__(0)``. Return
        ``self`` when ``other == 0`` (and is not a ``bool``). Otherwise return
        ``NotImplemented``.
        """
        if isinstance(other, int) and not isinstance(other, bool) and other == 0:
            return self
        return NotImplemented

    def __sub__(self, other: Money) -> Money:
        """Same rules as ``__add__``, but subtracts. The result may be negative."""
        if not isinstance(other, Money):
            return NotImplemented
        self._check_currency(other)
        return Money(self.amount - other.amount, self.currency)

    def __neg__(self) -> Money:
        """``-Money("5", "USD")`` is ``Money("-5", "USD")``."""
        return Money(-self.amount, self.currency)

    def __mul__(self, factor: int | Decimal) -> Money:
        """Multiply by an ``int`` or ``Decimal``. The result is rounded to cents.

        Return ``NotImplemented`` for ``float``, ``bool``, ``Money``, and
        anything else. ``Money * Money`` has no meaning.
        """
        if isinstance(factor, bool) or not isinstance(factor, (int, Decimal)):
            return NotImplemented
        return Money(self.amount * factor, self.currency)

    def __rmul__(self, factor: int | Decimal) -> Money:
        """Support ``3 * money`` with the same rules as ``__mul__``."""
        return self.__mul__(factor)

    def _check_currency(self, other: Money) -> None:
        if self.currency != other.currency:
            raise CurrencyMismatchError(f"cannot combine {self.currency} and {other.currency}")

    # -----------------------------------------------------------------------
    # Task 4: ordering (total_ordering) and alternative constructors
    # -----------------------------------------------------------------------
    def __lt__(self, other: Money) -> bool:
        """Compare amounts of the same currency.

        * Different currencies: raise ``CurrencyMismatchError``. There is no
          meaningful order between 5 USD and 4 EUR without an exchange rate.
        * Non-``Money``: return ``NotImplemented``.

        ``@total_ordering`` on the class derives ``<=``, ``>``, and ``>=``
        from ``__lt__`` and ``__eq__``, so you only write this one.
        """
        if not isinstance(other, Money):
            return NotImplemented
        self._check_currency(other)
        return self.amount < other.amount

    @classmethod
    def zero(cls, currency: str) -> Money:
        """Return a zero amount: ``Money.zero("usd") == Money("0", "USD")``."""
        return cls(0, currency)

    @classmethod
    def from_cents(cls, cents: int, currency: str) -> Money:
        """Build from an integer number of cents: ``from_cents(1250, "USD")`` is 12.50 USD.

        Raise ``TypeError`` if ``cents`` is not an ``int`` (``bool`` included).
        Payment providers such as Stripe send amounts this way.
        """
        if isinstance(cents, bool) or not isinstance(cents, int):
            raise TypeError("cents must be an int")
        return cls(Decimal(cents) / 100, currency)

    @classmethod
    def parse(cls, text: str) -> Money:
        """Parse ``"12.50 USD"`` (amount, whitespace, currency).

        Extra whitespace around the parts is fine. Anything else, for example
        ``"12.50"``, ``"USD 12.50"``, or ``"1 2 USD"``, raises ``ValueError``.

        Use ``cls(...)``, not ``Money(...)``, so subclasses get instances of
        their own type.
        """
        parts = text.split()
        if len(parts) != 2:
            raise ValueError(f"expected '<amount> <currency>', got {text!r}")
        amount, currency = parts
        return cls(amount, currency)


# ---------------------------------------------------------------------------
# Task 5: the container protocol
# ---------------------------------------------------------------------------
class Message(NamedTuple):
    role: str
    content: str


ROLES = frozenset({"system", "user", "assistant", "tool"})


class MessageHistory:
    """The message list of an LLM chat, which behaves like a read-only sequence.

    ``MessageHistory(messages=(), *, max_messages=None)`` takes an iterable of
    ``(role, content)`` pairs and appends them one by one.

    * ``append(role, content)``: raise ``ValueError`` if ``role`` is not in
      ``ROLES``. Store a ``Message``. If ``max_messages`` is set and the
      history is now longer than that, drop the **oldest non-system**
      message: the system prompt must survive trimming. (If every message
      is a system message, drop the oldest one.)
    * ``len(history)``: the number of messages.
    * ``history[i]``: a ``Message``, negative indexes included.
      ``history[1:3]``: a **new** ``MessageHistory`` with the same
      ``max_messages``.
    * ``iter(history)``: iterates over the ``Message`` objects in order.
    * ``x in history``: if ``x`` is a ``str``, check whether any message has
      that content. If ``x`` is a ``Message`` (or any tuple), check for an
      equal message.

    >>> h = MessageHistory([("system", "be brief"), ("user", "hi")], max_messages=2)
    >>> h.append("assistant", "hello")
    >>> [m.role for m in h], "be brief" in h, len(h)
    (['system', 'assistant'], True, 2)
    """

    def __init__(self, messages: Iterable[tuple[str, str]] = (), *, max_messages: int | None = None) -> None:
        self.max_messages = max_messages
        self._messages: list[Message] = []
        for role, content in messages:
            self.append(role, content)

    def append(self, role: str, content: str) -> None:
        if role not in ROLES:
            raise ValueError(f"unknown role {role!r}; expected one of {sorted(ROLES)}")
        self._messages.append(Message(role, content))
        if self.max_messages is not None and len(self._messages) > self.max_messages:
            for i, msg in enumerate(self._messages):
                if msg.role != "system":
                    del self._messages[i]
                    break
            else:
                del self._messages[0]

    def __len__(self) -> int:
        return len(self._messages)

    @overload
    def __getitem__(self, index: int) -> Message: ...
    @overload
    def __getitem__(self, index: slice) -> MessageHistory: ...
    def __getitem__(self, index: int | slice) -> Message | MessageHistory:
        if isinstance(index, slice):
            return type(self)(self._messages[index], max_messages=self.max_messages)
        return self._messages[index]

    def __iter__(self) -> Iterator[Message]:
        return iter(self._messages)

    def __contains__(self, item: object) -> bool:
        if isinstance(item, str):
            return any(m.content == item for m in self._messages)
        return item in self._messages


# ---------------------------------------------------------------------------
# Task 6: abstract base classes
# ---------------------------------------------------------------------------
class Notifier(ABC):
    """Base class for notification channels.

    Write the class body:

    * ``channel``: an **abstract property** that returns a ``str``. Stack
      ``@property`` on top of ``@abstractmethod``.
    * ``send(self, recipient: str, message: str) -> str``: an **abstract
      method**. Implementations return a delivery receipt, or raise
      ``ValueError`` for an invalid recipient.
    * ``notify_all(self, recipients: Iterable[str], message: str) -> dict[str, str]``:
      a **concrete** method (template method pattern). It calls ``send`` for
      each recipient and returns ``{recipient: receipt}``. When ``send``
      raises ``ValueError``, the value is ``f"error: {exc}"`` and the loop
      goes on.

    Once you have done that, ``Notifier()`` and any subclass that does not
    implement both abstract members raise ``TypeError`` when instantiated.
    """

    @property
    @abstractmethod
    def channel(self) -> str: ...

    @abstractmethod
    def send(self, recipient: str, message: str) -> str: ...

    def notify_all(self, recipients: Iterable[str], message: str) -> dict[str, str]:
        results: dict[str, str] = {}
        for recipient in recipients:
            try:
                results[recipient] = self.send(recipient, message)
            except ValueError as exc:
                results[recipient] = f"error: {exc}"
        return results


class EmailNotifier(Notifier):
    """``channel`` is ``"email"``.

    ``send`` raises ``ValueError`` if ``recipient`` has no ``"@"``. Otherwise
    it returns ``f"email from {self.sender} to {recipient}: {message}"``.
    """

    def __init__(self, sender: str) -> None:
        self.sender = sender

    @property
    def channel(self) -> str:
        return "email"

    def send(self, recipient: str, message: str) -> str:
        if "@" not in recipient:
            raise ValueError(f"invalid email address: {recipient!r}")
        return f"email from {self.sender} to {recipient}: {message}"


class SmsNotifier(Notifier):
    """``channel`` is ``"sms"``.

    * ``send`` raises ``ValueError`` unless ``recipient`` is ``"+"``
      followed by one or more digits.
    * A message longer than ``MAX_LENGTH`` is cut to ``MAX_LENGTH - 3``
      characters plus ``"..."``, so the result is exactly ``MAX_LENGTH`` long.
    * Return ``f"sms to {recipient}: {text}"``.
    """

    MAX_LENGTH = 160

    @property
    def channel(self) -> str:
        return "sms"

    def send(self, recipient: str, message: str) -> str:
        if not (recipient.startswith("+") and recipient[1:].isdigit()):
            raise ValueError(f"invalid phone number: {recipient!r}")
        if len(message) > self.MAX_LENGTH:
            message = message[: self.MAX_LENGTH - 3] + "..."
        return f"sms to {recipient}: {message}"


# ---------------------------------------------------------------------------
# Task 7: cooperative multiple inheritance with super()
# ---------------------------------------------------------------------------
class Model:
    """Root of the hierarchy (given). Rejects keyword arguments nobody consumed."""

    def __init__(self, **kwargs: Any) -> None:
        if kwargs:
            raise TypeError(f"unexpected field(s): {', '.join(sorted(kwargs))}")
        super().__init__()

    def to_dict(self) -> dict[str, Any]:
        return {}


class TimestampMixin:
    """Adds ``created_at``, like the mixins of an SQLAlchemy model base.

    * ``__init__`` takes a keyword-only ``created_at`` (default: now in UTC),
      stores it, and passes **every other** keyword argument on with
      ``super().__init__(**kwargs)``.
    * ``to_dict`` returns ``super().to_dict()`` plus
      ``"created_at": created_at.isoformat()``.

    Mixins do not know which class comes after them in the MRO. Always
    calling ``super()`` lets every class in the chain run exactly once.
    """

    def __init__(self, *, created_at: datetime | None = None, **kwargs: Any) -> None:
        self.created_at = created_at if created_at is not None else datetime.now(UTC)
        super().__init__(**kwargs)

    def to_dict(self) -> dict[str, Any]:
        return {**super().to_dict(), "created_at": self.created_at.isoformat()}  # type: ignore[misc]


class SoftDeleteMixin:
    """Adds ``deleted_at`` (keyword-only, default ``None``).

    * ``__init__``: store ``deleted_at`` and pass the rest on, like
      ``TimestampMixin``.
    * ``is_deleted``: a property, true when ``deleted_at`` is not ``None``.
    * ``soft_delete(when)``: set ``deleted_at``. Raise ``RuntimeError`` if the
      object is already deleted.
    * ``to_dict``: ``super().to_dict()`` plus ``"deleted_at"`` (ISO string or
      ``None``).
    """

    def __init__(self, *, deleted_at: datetime | None = None, **kwargs: Any) -> None:
        self.deleted_at = deleted_at
        super().__init__(**kwargs)

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def soft_delete(self, when: datetime) -> None:
        if self.is_deleted:
            raise RuntimeError("already deleted")
        self.deleted_at = when

    def to_dict(self) -> dict[str, Any]:
        deleted = self.deleted_at.isoformat() if self.deleted_at else None
        return {**super().to_dict(), "deleted_at": deleted}  # type: ignore[misc]


class Article(TimestampMixin, SoftDeleteMixin, Model):
    """An article with a required keyword-only ``title``.

    * ``__init__(self, *, title, **kwargs)``: store ``title``, pass the rest on.
    * ``to_dict``: ``super().to_dict()`` plus ``"title"``.

    With the MRO ``Article -> TimestampMixin -> SoftDeleteMixin -> Model``,
    the keys come out as ``deleted_at``, ``created_at``, ``title``. An
    unknown keyword such as ``Article(title="x", author="me")`` travels up the
    chain until ``Model`` rejects it with ``TypeError``.
    """

    def __init__(self, *, title: str, **kwargs: Any) -> None:
        self.title = title
        super().__init__(**kwargs)

    def to_dict(self) -> dict[str, Any]:
        return {**super().to_dict(), "title": self.title}


# ---------------------------------------------------------------------------
# Task 8: __slots__ and numeric dunders
# ---------------------------------------------------------------------------
class Vector:
    """An immutable N-dimensional vector of floats, such as an embedding.

    * Declare ``__slots__ = ("_components",)``. Instances then have no
      ``__dict__``, use less memory, and assigning an unknown attribute
      (``v.foo = 1``) raises ``AttributeError``. That matters when you hold
      millions of them.
    * ``Vector(*components)`` stores ``tuple(float(c) for c in components)``.
      Raise ``ValueError`` if there are no components.
    * ``repr(Vector(1, 2))`` is ``"Vector(1.0, 2.0)"``.
    * ``len``, iteration (so ``x, y = v`` works), and ``==`` (only with
      another ``Vector``, otherwise ``NotImplemented``). Equal vectors hash
      equally.
    * ``abs(v)``: the Euclidean norm. ``bool(v)``: false only for the zero
      vector.
    * ``a @ b``: the dot product. Raise ``ValueError`` if the lengths differ.
    * ``cosine_similarity(other)``: ``(a @ b) / (abs(a) * abs(b))``. Raise
      ``ValueError`` if either vector is zero.

    >>> Vector(3, 4) @ Vector(1, 0), abs(Vector(3, 4))
    (3.0, 5.0)
    """

    __slots__ = ("_components",)

    def __init__(self, *components: float) -> None:
        if not components:
            raise ValueError("a vector needs at least one component")
        self._components = tuple(float(c) for c in components)

    def __repr__(self) -> str:
        return f"Vector({', '.join(map(repr, self._components))})"

    def __len__(self) -> int:
        return len(self._components)

    def __iter__(self) -> Iterator[float]:
        return iter(self._components)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Vector):
            return NotImplemented
        return self._components == other._components

    def __hash__(self) -> int:
        return hash(self._components)

    def __abs__(self) -> float:
        return math.hypot(*self._components)

    def __bool__(self) -> bool:
        return any(self._components)

    def __matmul__(self, other: Vector) -> float:
        if not isinstance(other, Vector):
            return NotImplemented
        if len(self) != len(other):
            raise ValueError(f"dimension mismatch: {len(self)} != {len(other)}")
        return sum(a * b for a, b in zip(self, other, strict=True))

    def cosine_similarity(self, other: Vector) -> float:
        if not self or not other:
            raise ValueError("cosine similarity is undefined for a zero vector")
        return (self @ other) / (abs(self) * abs(other))
