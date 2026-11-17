import inspect
import json

import pytest
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.language_models import FakeListLLM
from langchain_core.language_models.fake_chat_models import (
    FakeListChatModel,
    GenericFakeChatModel,
)
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda

from m05_langchain.e06_streaming_history_callbacks.exercise import (
    CHAT_SYSTEM,
    SessionStore,
    TokenCountingHandler,
    astream_sse,
    build_chat_with_history,
    invoke_traced,
    stream_answer,
    stream_tokens_from_tagged_model,
)


def fake_model(*replies):
    """GenericFakeChatModel streams a reply word by word (spaces are separate chunks)."""
    return GenericFakeChatModel(messages=iter(replies))


class DictStore:
    """Test-local stand-in for SessionStore, so Task 5 does not depend on Task 4."""

    def __init__(self):
        self.data = {}

    def get(self, session_id):
        return list(self.data.get(session_id, []))

    def append(self, session_id, messages):
        self.data.setdefault(session_id, []).extend(messages)


class SpyModel:
    def __init__(self, *replies):
        self.replies = list(replies)
        self.prompts = []

        def _call(prompt_value):
            self.prompts.append(prompt_value.to_messages())
            return AIMessage(self.replies[len(self.prompts) - 1])

        self.runnable = RunnableLambda(_call)


class RecordingHandler(BaseCallbackHandler):
    """Test-local handler recording the kwargs of every chat-model start."""

    def __init__(self):
        self.starts = []

    def on_chat_model_start(self, serialized, messages, **kwargs):
        self.starts.append(kwargs)


class TestTask1StreamAnswer:
    def test_yields_tokens(self):
        chunks = list(stream_answer(fake_model("Hello there friend"), "hi"))
        assert chunks == ["Hello", " ", "there", " ", "friend"]

    def test_is_a_generator(self):
        assert inspect.isgenerator(stream_answer(fake_model("x"), "hi"))

    def test_prompt(self):
        spy = SpyModel("ok")
        assert list(stream_answer(spy.runnable, "What?")) == ["ok"]
        assert [(m.type, m.content) for m in spy.prompts[0]] == [
            ("system", CHAT_SYSTEM), ("human", "What?"),
        ]


class TestTask2AstreamSse:
    async def test_frames_and_done(self):
        frames = [f async for f in astream_sse(fake_model("Hi you"), "q")]
        assert frames == [
            'data: {"token": "Hi"}\n\n',
            'data: {"token": " "}\n\n',
            'data: {"token": "you"}\n\n',
            "data: [DONE]\n\n",
        ]

    async def test_tokens_with_newlines_stay_in_one_frame(self):
        frames = [f async for f in astream_sse(FakeListChatModel(responses=["a\nb"]), "q")]
        tokens = [json.loads(f.removeprefix("data: "))["token"] for f in frames[:-1]]
        assert "".join(tokens) == "a\nb"
        assert all(f.count("\n\n") == 1 and f.endswith("\n\n") for f in frames)

    async def test_error_mid_stream(self):
        model = FakeListChatModel(responses=["abcdef"], error_on_chunk_number=2)
        frames = [f async for f in astream_sse(model, "q")]
        assert frames[:2] == ['data: {"token": "a"}\n\n', 'data: {"token": "b"}\n\n']
        assert frames[-1].startswith("event: error\ndata: ")
        assert "error" in json.loads(frames[-1].split("data: ", 1)[1])
        assert "data: [DONE]\n\n" not in frames


class TestTask3StreamTokensFromTaggedModel:
    @staticmethod
    def two_model_chain():
        rewrite = fake_model("rewritten question").with_config(tags=["rewrite"])
        answer = fake_model("final answer here").with_config(tags=["answer"])
        return (
            ChatPromptTemplate.from_messages([("human", "{question}")])
            | rewrite
            | StrOutputParser()
            | RunnableLambda(lambda q: [HumanMessage(q)])
            | answer
            | StrOutputParser()
        )

    async def test_only_tagged_model_tokens(self):
        tokens = await stream_tokens_from_tagged_model(self.two_model_chain(), {"question": "q"}, "answer")
        assert tokens == ["final", " ", "answer", " ", "here"]

    async def test_other_tag(self):
        tokens = await stream_tokens_from_tagged_model(self.two_model_chain(), {"question": "q"}, "rewrite")
        assert "".join(tokens) == "rewritten question"

    async def test_unknown_tag(self):
        assert await stream_tokens_from_tagged_model(self.two_model_chain(), {"question": "q"}, "nope") == []


class TestTask4SessionStore:
    def test_append_and_get_copy(self):
        store = SessionStore()
        store.append("s1", [HumanMessage("hi"), AIMessage("hello")])
        history = store.get("s1")
        assert [m.content for m in history] == ["hi", "hello"]
        history.append(HumanMessage("sneaky"))
        assert len(store.get("s1")) == 2

    def test_unknown_session_and_clear(self):
        store = SessionStore()
        assert store.get("nope") == []
        store.append("a", [HumanMessage("x")])
        store.append("b", [HumanMessage("y")])
        assert store.session_ids() == ["a", "b"]
        store.clear("a")
        store.clear("never-existed")
        assert store.get("a") == []
        assert store.session_ids() == ["b"]

    def test_keeps_only_newest_messages(self):
        store = SessionStore(max_messages=3)
        store.append("s", [HumanMessage("1"), AIMessage("2")])
        store.append("s", [HumanMessage("3"), AIMessage("4")])
        assert [m.content for m in store.get("s")] == ["2", "3", "4"]

    def test_invalid_max(self):
        with pytest.raises(ValueError):
            SessionStore(max_messages=0)


class TestTask5ChatWithHistory:
    @staticmethod
    def cfg(session_id):
        return {"configurable": {"session_id": session_id}}

    def test_history_reaches_the_model(self):
        spy, store = SpyModel("Nice to meet you, Ann.", "Your name is Ann."), DictStore()
        chain = build_chat_with_history(spy.runnable, store)
        chain.invoke({"question": "I am Ann."}, config=self.cfg("s1"))
        answer = chain.invoke({"question": "What is my name?"}, config=self.cfg("s1"))
        assert answer == "Your name is Ann."
        assert [(type(m), m.content) for m in spy.prompts[1]] == [
            (SystemMessage, CHAT_SYSTEM),
            (HumanMessage, "I am Ann."),
            (AIMessage, "Nice to meet you, Ann."),
            (HumanMessage, "What is my name?"),
        ]
        assert [m.content for m in store.get("s1")] == [
            "I am Ann.", "Nice to meet you, Ann.", "What is my name?", "Your name is Ann.",
        ]

    def test_sessions_are_isolated(self):
        spy, store = SpyModel("a", "b"), DictStore()
        chain = build_chat_with_history(spy.runnable, store)
        chain.invoke({"question": "secret"}, config=self.cfg("alice"))
        chain.invoke({"question": "hi"}, config=self.cfg("bob"))
        assert len(spy.prompts[1]) == 2  # system + question only
        assert [m.content for m in store.get("bob")] == ["hi", "b"]

    def test_missing_session_id(self):
        chain = build_chat_with_history(SpyModel("x").runnable, DictStore())
        with pytest.raises(ValueError):
            chain.invoke({"question": "hi"})

    def test_failed_call_does_not_touch_history(self):
        def boom(_):
            raise ConnectionError("provider down")

        store = DictStore()
        chain = build_chat_with_history(RunnableLambda(boom), store)
        with pytest.raises(ConnectionError):
            chain.invoke({"question": "hi"}, config=self.cfg("s"))
        assert store.get("s") == []


class TestTask6TokenCountingHandler:
    def test_counts_streamed_tokens(self):
        handler = TokenCountingHandler()
        model = fake_model("one two three")
        list(model.stream("hi", config={"callbacks": [handler], "tags": ["chat"]}))
        assert handler.chat_model_starts == 1
        assert handler.llm_starts == 0
        assert handler.tokens == ["one", " ", "two", " ", "three"]
        assert handler.llm_ends == 1
        assert "chat" in handler.tags

    def test_invoke_has_no_tokens(self):
        handler = TokenCountingHandler()
        fake_model("a b").invoke("hi", config={"callbacks": [handler]})
        assert (handler.chat_model_starts, handler.tokens, handler.llm_ends) == (1, [], 1)

    def test_plain_llm_uses_on_llm_start(self):
        handler = TokenCountingHandler()
        FakeListLLM(responses=["x"]).invoke("hi", config={"callbacks": [handler], "tags": ["llm"]})
        assert (handler.llm_starts, handler.chat_model_starts, handler.llm_ends) == (1, 0, 1)
        assert handler.tags == {"llm"}

    def test_records_errors(self):
        handler = TokenCountingHandler()
        model = FakeListChatModel(responses=["abc"], error_on_chunk_number=1)
        with pytest.raises(Exception):
            list(model.stream("hi", config={"callbacks": [handler]}))
        assert len(handler.errors) == 1
        assert isinstance(handler.errors[0], Exception)
        assert handler.tokens == ["a"]  # the chunk before the failure

    def test_callbacks_propagate_through_a_chain(self):
        handler = TokenCountingHandler()
        chain = ChatPromptTemplate.from_messages([("human", "{q}")]) | fake_model("x y") | StrOutputParser()
        list(chain.stream({"q": "hi"}, config={"callbacks": [handler]}))
        assert handler.chat_model_starts == 1
        assert "".join(handler.tokens) == "x y"


class TestTask7InvokeTraced:
    @staticmethod
    def chain():
        return ChatPromptTemplate.from_messages([("human", "{q}")]) | fake_model("traced") | StrOutputParser()

    def test_returns_result_and_calls_handler(self):
        handler = RecordingHandler()
        assert invoke_traced(self.chain(), {"q": "hi"}, handler, user_id="u1", request_id="r1") == "traced"
        assert len(handler.starts) == 1

    def test_tags_and_metadata_reach_the_model(self):
        handler = RecordingHandler()
        invoke_traced(self.chain(), {"q": "hi"}, handler, user_id="u42", request_id="req-7")
        start = handler.starts[0]
        assert "user:u42" in start["tags"]
        assert start["metadata"]["user_id"] == "u42"
        assert start["metadata"]["request_id"] == "req-7"

    def test_run_name(self):
        names = []

        class ChainStartHandler(BaseCallbackHandler):
            def on_chain_start(self, serialized, inputs, **kwargs):
                names.append(kwargs.get("name"))

        invoke_traced(self.chain(), {"q": "hi"}, ChainStartHandler(), user_id="u", request_id="r")
        assert names[0] == "chat_request"
