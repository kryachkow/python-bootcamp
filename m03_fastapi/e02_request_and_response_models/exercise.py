"""Exercise 3.2: request bodies, response models, and validation.

You build a user-signup API and a fake chat-completions endpoint. The point
is the boundary between what clients send, what you store, and what you
return. A password goes in, and it must never come out.

The storage layer (``UserStore``) is given. Your job is the Pydantic schemas
and the path operations. Every route is registered on ``router``, and
``create_app`` includes it.

Run the tests with:

    uv run pytest m03_fastapi/e02_request_and_response_models
"""

import hashlib
from dataclasses import dataclass
from typing import Annotated, Literal

from fastapi import APIRouter, Body, FastAPI, HTTPException, Path, Query, Response, status
from pydantic import BaseModel, Field, SecretStr

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
USERNAME_PATTERN = r"^[a-z0-9_]+$"


# ---------------------------------------------------------------------------
# Given: the storage layer (do not change)
# ---------------------------------------------------------------------------
def hash_password(password: str) -> str:
    """A stand-in for bcrypt/argon2. Never store raw passwords."""
    return "sha256$" + hashlib.sha256(password.encode()).hexdigest()


@dataclass
class UserRecord:
    """What the "database" stores. Note ``hashed_password``: it must not leak."""

    id: int
    username: str
    email: str
    hashed_password: str
    full_name: str | None = None


class UserStore:
    """A tiny in-memory user table. The tests call ``store.clear()`` before each test."""

    def __init__(self) -> None:
        self._users: dict[int, UserRecord] = {}
        self._next_id = 1

    def clear(self) -> None:
        self._users.clear()
        self._next_id = 1

    def username_taken(self, username: str) -> bool:
        return any(u.username == username for u in self._users.values())

    def add(self, *, username: str, email: str, password: str, full_name: str | None) -> UserRecord:
        record = UserRecord(self._next_id, username, email, hash_password(password), full_name)
        self._users[record.id] = record
        self._next_id += 1
        return record

    def get(self, user_id: int) -> UserRecord | None:
        return self._users.get(user_id)

    def all(self) -> list[UserRecord]:
        return sorted(self._users.values(), key=lambda u: u.id)


store = UserStore()
router = APIRouter()


# ---------------------------------------------------------------------------
# Task 1: input and output schemas
# ---------------------------------------------------------------------------
# Define two Pydantic models.
#
# ``UserIn`` is the signup request body:
#   * ``username: str``: 3 to 32 characters, matching ``USERNAME_PATTERN``
#     (lowercase letters, digits, underscore).
#   * ``email: str``: must match ``EMAIL_PATTERN``. (``EmailStr`` would need the
#     extra ``email-validator`` package.)
#   * ``password: SecretStr``: at least 8 characters. ``SecretStr`` shows as
#     ``'**********'`` in reprs and logs. Read it with ``.get_secret_value()``.
#   * ``full_name: str | None = None``.
#
# ``UserOut`` is what the API returns. It has exactly the fields ``id: int``,
# ``username: str``, ``email: str``, and ``full_name: str | None = None``.
# It has no password field of any kind.
#
# Hint: ``Field(min_length=..., max_length=..., pattern=...)``.
#
# TODO: replace the placeholder classes below with the real models
class UserIn(BaseModel):
    pass


class UserOut(BaseModel):
    pass


# ---------------------------------------------------------------------------
# Task 2: create a user (201, response_model filtering, 409)
# ---------------------------------------------------------------------------
# ``POST /users`` takes a ``UserIn`` body.
#
# * If ``store.username_taken(...)``, raise ``409`` with
#   ``detail=f"Username '{username}' is already taken"``.
# * Otherwise call ``store.add(...)``, which returns a ``UserRecord``. Return
#   that record as is and let ``response_model=UserOut`` drop
#   ``hashed_password``.
# * Respond with ``201 Created`` and a ``Location: /users/<id>`` header. To
#   set a header, add a ``response: Response`` parameter and use
#   ``response.headers[...]``.
# * An invalid body (for example a short password) gives ``422``. FastAPI
#   does this for you.
#
# TODO: implement this task (see the spec above)


# ---------------------------------------------------------------------------
# Task 3: read one user (Path constraints, exclude_none)
# ---------------------------------------------------------------------------
# ``GET /users/{user_id}``
#
# * Declare ``user_id: Annotated[int, Path(ge=1)]``, so ``/users/0`` gives
#   ``422`` before your code runs.
# * Unknown id: ``404`` with ``detail=f"User {user_id} not found"``.
# * Return the user as ``UserOut`` with ``response_model_exclude_none=True``,
#   so a user without ``full_name`` comes back without that key at all.
#
# TODO: implement this task (see the spec above)


# ---------------------------------------------------------------------------
# Task 4: list users (Query constraints, list response)
# ---------------------------------------------------------------------------
# ``GET /users`` returns a JSON array of ``UserOut`` (``response_model=list[UserOut]``),
# ordered by id. Use the ``Annotated`` style for both query parameters:
#
# * ``q: str | None``, default ``None``, ``max_length=50``: keep only users
#   whose username contains ``q``.
# * ``limit: int``, default ``20``, from 1 to 100 (``ge``/``le``): the maximum
#   number of users to return.
#
# This route does *not* exclude ``None``: ``full_name`` is present (maybe ``null``).
#
# TODO: implement this task (see the spec above)


# ---------------------------------------------------------------------------
# Task 5: several body parameters
# ---------------------------------------------------------------------------
# ``POST /users/{user_id}/password`` changes a password. Declare two body
# parameters, ``old_password: Annotated[str, Body()]`` and
# ``new_password: Annotated[str, Body(min_length=8)]``. With more than one
# body parameter, FastAPI expects a JSON object with one key per parameter:
# ``{"old_password": "...", "new_password": "..."}``.
#
# * Unknown user: ``404`` with ``detail=f"User {user_id} not found"``.
# * ``hash_password(old_password)`` does not match the stored hash: ``403``
#   with ``detail="Old password is incorrect"``.
# * Otherwise store ``hash_password(new_password)`` on the record and respond
#   ``204 No Content``.
#
# TODO: implement this task (see the spec above)


# ---------------------------------------------------------------------------
# Task 6: nested request models for a chat API
# ---------------------------------------------------------------------------
# Define the request side of an OpenAI-style chat API.
#
# ``ChatMessage``:
#   * ``role: Literal["system", "user", "assistant"]``
#   * ``content: str``, at least 1 character
#
# ``ChatRequest``:
#   * ``model: str = "fake-gpt"``
#   * ``messages: list[ChatMessage]``, at least one message (``Field(min_length=1)``)
#   * ``temperature: float = 0.7``, between 0.0 and 2.0 inclusive
#   * ``max_tokens: int | None = None``, ``>= 1`` when given
#
# TODO: replace the placeholder classes below with the real models
class ChatMessage(BaseModel):
    pass


class ChatRequest(BaseModel):
    pass


class Usage(BaseModel):
    """Given."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatResponse(BaseModel):
    """Given."""

    model: str
    message: ChatMessage
    usage: Usage


# ---------------------------------------------------------------------------
# Task 7: the chat-completions endpoint
# ---------------------------------------------------------------------------
# ``POST /chat/completions`` takes a ``ChatRequest`` and returns a
# ``ChatResponse``. The return annotation ``-> ChatResponse`` is enough: no
# ``response_model=`` is needed when you return the model itself.
#
# A fake model is enough here:
#   * Find the last message with ``role == "user"``. If there is none, raise
#     ``400`` with ``detail="At least one user message is required"``.
#   * The reply is ``"You said: " + <that message's content>``. If
#     ``max_tokens`` is set, keep only the first ``max_tokens``
#     whitespace-separated words of the reply, joined by single spaces.
#   * "Tokens" are whitespace-separated words. ``prompt_tokens`` counts the
#     words in all request messages, ``completion_tokens`` counts the words in
#     the (truncated) reply, and ``total_tokens`` is their sum.
#   * The response ``model`` echoes the request's model, and ``message`` has
#     ``role="assistant"``.
#
# TODO: implement this task (see the spec above)


def create_app() -> FastAPI:
    """Build the application (given)."""
    app = FastAPI(title="Request and response models")
    app.include_router(router)
    return app
