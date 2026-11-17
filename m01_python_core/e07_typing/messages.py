"""Exercise 1.7, Task 4: TypedDict, Required / NotRequired, and Literal.

Why a separate module? On Python 3.12, ``from __future__ import annotations``
turns every annotation into a string, and the ``TypedDict`` machinery then no
longer sees ``Required[...]`` / ``NotRequired[...]``. The required and optional
key sets come out wrong, with no error. So this module, unlike ``exercise.py``,
does **not** use the future import. Remember this gotcha when you share
TypedDicts with code that does.
"""

from collections.abc import Mapping
from typing import Any, Literal, NotRequired, Required, TypedDict, get_args, get_type_hints

# ---------------------------------------------------------------------------
# Task 4: TypedDict + Literal
# ---------------------------------------------------------------------------
# Define ``Role`` as a ``Literal`` of the four chat roles, in this order:
# "system", "user", "assistant", "tool".
Role = str


class ChatMessage(TypedDict):
    """One message of an OpenAI-style chat payload. Write the keys:

    * ``role: Role`` and ``content: str``: required (the default for a
      ``total=True`` TypedDict).
    * ``name: NotRequired[str]``: optional.

    A ``TypedDict`` is a plain ``dict`` at runtime. ``ChatMessage(role="user",
    content="hi")`` returns a ``dict``. The class only describes its shape,
    for type checkers and for ``__required_keys__`` / ``__optional_keys__``.
    """

    pass


class ToolCall(TypedDict, total=False):
    """A tool call requested by the model. Write the keys:

    The class is ``total=False``, so every key is optional by default. Mark
    ``id: str`` and ``name: str`` as ``Required[...]``. Leave
    ``arguments: dict[str, Any]`` optional.
    """

    pass


def validate_message(data: Mapping[str, object]) -> ChatMessage:
    """Check untrusted data against ``ChatMessage`` at runtime and return a new dict.

    Get the rules from the TypedDict itself. Do not hard-code key names:

    * Every key in ``ChatMessage.__required_keys__`` must be present.
      Otherwise raise ``ValueError(f"missing key: {key}")``. Check the keys in
      sorted order, so the error is deterministic.
    * Keys outside ``__required_keys__ | __optional_keys__`` raise
      ``ValueError`` too.
    * ``role`` must be one of ``get_args(Role)``, otherwise ``ValueError``.
    * Every other present value must be an instance of its annotated type
      from ``get_type_hints(ChatMessage)`` (all ``str`` here), otherwise
      ``TypeError``.

    Return ``dict(data)`` (a new dict, not the input object).

    This is a tiny version of what Pydantic's ``TypeAdapter(ChatMessage)``
    does for you.
    """
    raise NotImplementedError("TODO: implement this task")
