import inspect

import pytest


from sqlalchemy import func, inspect as sa_inspect, select  # noqa: E402
from sqlalchemy.exc import MissingGreenlet, StatementError  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from m04_sqlalchemy.e06_async.exercise import (  # noqa: E402
    Base,
    Conversation,
    Message,
    add_message,
    conversation_summaries,
    create_conversation,
    delete_conversation,
    fetch_titles_concurrently,
    get_conversation,
    init_models,
    make_session_factory,
    stream_contents,
)


@pytest.fixture
async def engine(tmp_path):
    """A file database: each session gets its own connection from the pool."""
    eng = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'chat.db'}")
    yield eng
    await eng.dispose()


@pytest.fixture
async def factory(engine):
    """Schema + seed data, built without any exercise code."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        s.add_all(
            [
                Conversation(
                    title="Alpha",
                    messages=[
                        Message(role="system", content="be brief"),
                        Message(role="user", content="hi"),
                        Message(role="assistant", content="hello"),
                    ],
                ),
                Conversation(title="Beta", messages=[Message(role="user", content="?")]),
                Conversation(title="Gamma"),
            ]
        )
        await s.commit()
    return maker


@pytest.fixture
async def session(factory):
    async with factory() as s:
        yield s


async def count_messages(factory) -> int:
    async with factory() as s:
        return await s.scalar(select(func.count()).select_from(Message))


class TestTask1SessionFactory:
    async def test_factory_config(self, engine):
        factory = make_session_factory(engine)
        assert isinstance(factory, async_sessionmaker)
        assert factory.kw["expire_on_commit"] is False
        async with factory() as s:
            assert isinstance(s, AsyncSession)
            assert s.bind is engine

    async def test_attributes_readable_after_commit(self, engine):
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = make_session_factory(engine)
        async with factory() as s:
            conv = Conversation(title="T")
            s.add(conv)
            await s.commit()
            assert conv.title == "T" and conv.id == 1


class TestTask2InitModels:
    async def test_creates_tables(self, engine):
        await init_models(engine)
        async with engine.connect() as conn:
            names = await conn.run_sync(lambda c: sa_inspect(c).get_table_names())
        assert set(names) == {"conversations", "messages"}

    async def test_idempotent(self, engine):
        await init_models(engine)
        await init_models(engine)


class TestTask3CreateConversation:
    async def test_creates_with_messages(self, factory, session):
        conv = await create_conversation(session, "Delta", [("user", "q"), ("assistant", "a")])
        assert conv.id == 4
        assert [m.role for m in conv.messages] == ["user", "assistant"]
        assert await count_messages(factory) == 6

    async def test_no_messages(self, session):
        conv = await create_conversation(session, "Empty")
        assert conv.messages == []

    async def test_bad_role(self, factory, session):
        with pytest.raises(ValueError):
            await create_conversation(session, "Bad", [("user", "ok"), ("robot", "no")])
        assert not session.new
        assert await count_messages(factory) == 4


class TestTask4GetConversation:
    async def test_messages_loaded_after_session_closed(self, factory):
        async with factory() as s:
            conv = await get_conversation(s, 1)
        assert conv.title == "Alpha"
        assert [m.content for m in conv.messages] == ["be brief", "hi", "hello"]

    async def test_missing(self, session):
        assert await get_conversation(session, 999) is None

    async def test_lazy_load_would_fail(self, factory):
        """Why Task 4 exists: the same access without eager loading."""
        async with factory() as s:
            assert len((await get_conversation(s, 2)).messages) == 1
        async with factory() as s:
            lazy = await s.get(Conversation, 2)
            # SQLAlchemy 2.1 wraps MissingGreenlet in a StatementError
            with pytest.raises((MissingGreenlet, StatementError), match="greenlet_spawn"):
                _ = lazy.messages


class TestTask5AddMessage:
    async def test_adds(self, factory, session):
        msg = await add_message(session, 3, "user", "first!")
        assert msg.id is not None and msg.conversation_id == 3
        async with factory() as s:
            conv = await s.get(Conversation, 3)
            contents = await conv.awaitable_attrs.messages
        assert [m.content for m in contents] == ["first!"]

    async def test_missing_conversation(self, session):
        with pytest.raises(LookupError):
            await add_message(session, 999, "user", "x")

    async def test_bad_role(self, factory, session):
        with pytest.raises(ValueError):
            await add_message(session, 1, "robot", "x")
        assert await count_messages(factory) == 4


class TestTask6Summaries:
    async def test_counts(self, session):
        assert await conversation_summaries(session) == [("Alpha", 3), ("Beta", 1), ("Gamma", 0)]

    async def test_empty_db(self, engine):
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with async_sessionmaker(engine)() as s:
            assert await conversation_summaries(s) == []


class TestTask7Delete:
    async def test_deletes_with_messages(self, factory, session):
        assert await delete_conversation(session, 1) is True
        assert await count_messages(factory) == 1
        async with factory() as s:
            assert await s.get(Conversation, 1) is None

    async def test_missing(self, session):
        assert await delete_conversation(session, 999) is False


class TestTask8Concurrency:
    async def test_results_in_order(self, factory):
        assert await fetch_titles_concurrently(factory, [3, 1, 999, 2]) == [
            "Gamma", "Alpha", None, "Beta"
        ]

    async def test_one_session_per_id(self, factory):
        opened = []

        def counting_factory():
            s = factory()
            opened.append(s)
            return s

        await fetch_titles_concurrently(counting_factory, [1, 2, 3])
        assert len(opened) == 3 and len({id(s) for s in opened}) == 3

    async def test_empty(self, factory):
        assert await fetch_titles_concurrently(factory, []) == []


class TestTask9Stream:
    def test_is_async_generator(self):
        assert inspect.isasyncgenfunction(stream_contents)

    async def test_streams_in_order(self, session):
        assert [c async for c in stream_contents(session, 1)] == ["be brief", "hi", "hello"]

    async def test_empty(self, session):
        assert [c async for c in stream_contents(session, 3)] == []
