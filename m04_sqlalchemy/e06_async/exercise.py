"""Exercise 4.6: async SQLAlchemy with ``AsyncEngine`` and ``AsyncSession``.

This is the stack behind an async FastAPI service: ``create_async_engine``
with an async driver (``aiosqlite`` here, ``asyncpg`` in production),
``async_sessionmaker``, and ``await`` on every call that can do I/O. The
models (a chat history, as an LLM backend stores it) are given. Run the tests
with:

    uv run pytest m04_sqlalchemy/e06_async

The rule that shapes everything below: in async code an attribute access
cannot do I/O. A lazy load (``conversation.messages`` when it is not loaded
yet) raises ``sqlalchemy.exc.MissingGreenlet``. Load what you need up front
(``selectinload``), or await it explicitly (``await obj.awaitable_attrs.messages``).

Requires the ``greenlet`` package (``pip install "sqlalchemy[asyncio]"``):
since SQLAlchemy 2.1 it is no longer installed automatically.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Sequence

from sqlalchemy import ForeignKey, String, Text, func, select
from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, selectinload

ROLES = frozenset({"system", "user", "assistant"})


class Base(AsyncAttrs, DeclarativeBase):
    """``AsyncAttrs`` adds ``obj.awaitable_attrs.<name>`` for explicit async lazy loads."""


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    messages: Mapped[list[Message]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", order_by="Message.id"
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"))
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    conversation: Mapped[Conversation] = relationship(back_populates="messages")


# ---------------------------------------------------------------------------
# Task 1: session factory
# ---------------------------------------------------------------------------
def make_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Return an ``async_sessionmaker`` bound to ``engine`` with ``expire_on_commit=False``.

    With the default (``True``) every object is expired by ``commit()``, and
    the next attribute access (``obj.id``) needs a database round trip,
    which in async code raises ``MissingGreenlet``. Every async service sets
    it to ``False``.

    Usage: ``async with factory() as session: ...``.
    """
    return async_sessionmaker(engine, expire_on_commit=False)


# ---------------------------------------------------------------------------
# Task 2: create the schema
# ---------------------------------------------------------------------------
async def init_models(engine: AsyncEngine) -> None:
    """Create all tables of ``Base.metadata``.

    ``MetaData.create_all`` is synchronous: it takes a sync ``Connection``.
    ``AsyncConnection.run_sync(fn)`` calls ``fn(sync_connection)`` for you:

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ---------------------------------------------------------------------------
# Task 3: create
# ---------------------------------------------------------------------------
async def create_conversation(
    session: AsyncSession, title: str, messages: Sequence[tuple[str, str]] = ()
) -> Conversation:
    """Create a conversation with ``messages`` (``(role, content)`` pairs), commit,
    and return it.

    * Raise ``ValueError`` if a role is not in ``ROLES``; add nothing then.
    * ``session.add()`` is synchronous (it does no I/O); ``commit()`` is
      ``await``-ed.
    * The session comes from a factory with ``expire_on_commit=False``, so the
      returned object's ``id`` and ``messages`` are readable afterwards.
    """
    for role, _ in messages:
        if role not in ROLES:
            raise ValueError(f"unknown role {role!r}")
    conversation = Conversation(
        title=title,
        messages=[Message(role=role, content=content) for role, content in messages],
    )
    session.add(conversation)
    await session.commit()
    return conversation


# ---------------------------------------------------------------------------
# Task 4: eager loading instead of lazy loading
# ---------------------------------------------------------------------------
async def get_conversation(session: AsyncSession, conversation_id: int) -> Conversation | None:
    """Return the conversation with its ``messages`` loaded, or ``None``.

    The caller reads ``conversation.messages`` after the session has closed
    (a FastAPI handler serialising the response, say). ``session.get()``
    alone does not load the collection, and the later access would raise
    ``MissingGreenlet``.

    Hint: ``await session.scalar(select(Conversation).where(...)
    .options(selectinload(Conversation.messages)))``. (``session.get`` also
    accepts ``options=[selectinload(...)]``.)
    """
    stmt = (
        select(Conversation)
        .where(Conversation.id == conversation_id)
        .options(selectinload(Conversation.messages))
    )
    return await session.scalar(stmt)


# ---------------------------------------------------------------------------
# Task 5: add to a collection without lazy loading it
# ---------------------------------------------------------------------------
async def add_message(
    session: AsyncSession, conversation_id: int, role: str, content: str
) -> Message:
    """Append a message to a conversation, commit, and return the message.

    * Raise ``ValueError`` for an unknown role, ``LookupError`` if the
      conversation does not exist (``await session.get(...)``).
    * Do NOT write ``conversation.messages.append(...)``: that lazy-loads the
      whole collection first, which raises ``MissingGreenlet`` in async code
      (and would load every message just to add one). Create the ``Message``
      with ``conversation_id=`` and ``session.add()`` it.
    """
    if role not in ROLES:
        raise ValueError(f"unknown role {role!r}")
    if await session.get(Conversation, conversation_id) is None:
        raise LookupError(f"Conversation {conversation_id} not found")
    message = Message(conversation_id=conversation_id, role=role, content=content)
    session.add(message)
    await session.commit()
    return message


# ---------------------------------------------------------------------------
# Task 6: an aggregate query
# ---------------------------------------------------------------------------
async def conversation_summaries(session: AsyncSession) -> list[tuple[str, int]]:
    """Return ``(title, number of messages)`` for every conversation, sorted by
    title. Conversations without messages have count ``0``.

    Same ``select()`` as in sync code; only the execution is awaited:
    ``result = await session.execute(stmt)``. The ``Result`` is already
    buffered, so iterating it needs no ``await``.
    """
    stmt = (
        select(Conversation.title, func.count(Message.id))
        .outerjoin(Conversation.messages)
        .group_by(Conversation.id, Conversation.title)
        .order_by(Conversation.title)
    )
    result = await session.execute(stmt)
    return [tuple(row) for row in result]


# ---------------------------------------------------------------------------
# Task 7: delete with cascade
# ---------------------------------------------------------------------------
async def delete_conversation(session: AsyncSession, conversation_id: int) -> bool:
    """Delete a conversation and its messages, commit, and return ``True``;
    return ``False`` if it does not exist.

    Note: ``AsyncSession.delete()`` is a coroutine (``await session.delete(obj)``)
    because the cascade may need to load related rows, unlike the sync
    ``Session.delete()``. ``add()`` is NOT a coroutine.
    """
    conversation = await session.get(Conversation, conversation_id)
    if conversation is None:
        return False
    await session.delete(conversation)
    await session.commit()
    return True


# ---------------------------------------------------------------------------
# Task 8: concurrency
# ---------------------------------------------------------------------------
async def fetch_titles_concurrently(
    factory: async_sessionmaker[AsyncSession], conversation_ids: Sequence[int]
) -> list[str | None]:
    """Fetch each conversation's title concurrently; ``None`` for a missing id.

    * Run one coroutine per id with ``asyncio.gather`` (results keep input order).
    * Each coroutine opens ITS OWN session: ``async with factory() as session:``.
      An ``AsyncSession`` must never be shared by concurrent tasks; it is
      not safe for concurrent use.
    """
    async def one(conversation_id: int) -> str | None:
        async with factory() as session:
            conversation = await session.get(Conversation, conversation_id)
            return conversation.title if conversation is not None else None

    return list(await asyncio.gather(*(one(i) for i in conversation_ids)))


# ---------------------------------------------------------------------------
# Task 9: streaming results
# ---------------------------------------------------------------------------
async def stream_contents(session: AsyncSession, conversation_id: int) -> AsyncIterator[str]:
    """Yield the ``content`` of each message of a conversation, in id order,
    without buffering the whole result. Write it as an *async generator*
    (``async def`` with ``yield``).

    Hint: ``result = await session.stream_scalars(stmt)`` returns an
    ``AsyncScalarResult`` backed by a server-side cursor; read it with
    ``async for value in result``. Useful for exports and for feeding a long
    chat history to an LLM piece by piece.
    """
    stmt = (
        select(Message.content)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.id)
    )
    result = await session.stream_scalars(stmt)
    async for content in result:
        yield content
