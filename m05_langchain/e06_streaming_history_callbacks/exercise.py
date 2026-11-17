"""Exercise 5.6: streaming, chat history and callbacks.

The runtime side of an LLM backend: stream tokens to the client (e.g. a
FastAPI ``StreamingResponse``), remember the conversation per session, and
observe what the models do via callbacks (token counting, tracing, logging).
Run the tests with:

    uv run pytest m05_langchain/e06_streaming_history_callbacks
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterator, Sequence
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.outputs import LLMResult
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import Runnable, RunnableConfig, RunnableLambda

ChatModel = BaseChatModel | Runnable[Any, Any]

CHAT_SYSTEM = "You are a helpful assistant."


# ---------------------------------------------------------------------------
# Task 1: sync token streaming
# ---------------------------------------------------------------------------
def stream_answer(model: ChatModel, question: str) -> Iterator[str]:
    """Stream the answer to ``question`` token by token.

    * Chain: ``ChatPromptTemplate`` (system ``CHAT_SYSTEM``, human
      ``"{question}"``) ``| model | StrOutputParser()``.
    * Yield every chunk from ``chain.stream(...)`` except empty strings.
      Joining the chunks gives the full answer.

    This is a generator function (use ``yield``), so the caller receives
    tokens as soon as the model produces them.
    """
    prompt = ChatPromptTemplate.from_messages([("system", CHAT_SYSTEM), ("human", "{question}")])
    chain = prompt | model | StrOutputParser()
    for chunk in chain.stream({"question": question}):
        if chunk:
            yield chunk


# ---------------------------------------------------------------------------
# Task 2: async streaming as Server-Sent Events
# ---------------------------------------------------------------------------
async def astream_sse(model: ChatModel, question: str) -> AsyncIterator[str]:
    """Async-stream the answer formatted as Server-Sent Events.

    Plug it straight into FastAPI:
    ``StreamingResponse(astream_sse(llm, q), media_type="text/event-stream")``.

    * Same chain as Task 1, consumed with ``chain.astream(...)``.
    * For every non-empty chunk yield ``f"data: {json.dumps({'token': chunk})}\\n\\n"``
      (JSON-encoding keeps newlines inside a token from breaking the SSE frame).
    * After the last chunk yield ``"data: [DONE]\\n\\n"``.
    * If the model fails mid-stream, yield one
      ``f"event: error\\ndata: {json.dumps({'error': str(exc)})}\\n\\n"``
      frame and stop: no ``[DONE]``, and the exception is **not** re-raised
      (the HTTP response has already started; you can only tell the client).
    """
    prompt = ChatPromptTemplate.from_messages([("system", CHAT_SYSTEM), ("human", "{question}")])
    chain = prompt | model | StrOutputParser()
    try:
        async for chunk in chain.astream({"question": question}):
            if chunk:
                yield f"data: {json.dumps({'token': chunk})}\n\n"
    except Exception as exc:
        yield f"event: error\ndata: {json.dumps({'error': str(exc)})}\n\n"
        return
    yield "data: [DONE]\n\n"


# ---------------------------------------------------------------------------
# Task 3: astream_events
# ---------------------------------------------------------------------------
async def stream_tokens_from_tagged_model(
    chain: Runnable, inputs: Any, tag: str
) -> list[str]:
    """Collect the tokens streamed by the chat model(s) tagged ``tag`` only.

    A chain may call several models (e.g. a cheap "rewrite the question"
    model, then the "answer" model) but the user should only see the
    answer tokens. ``chain.astream_events(inputs, version="v2")`` emits an
    event for every step; keep the ones where

    * ``event["event"] == "on_chat_model_stream"``, and
    * ``tag in event["tags"]`` (tags come from ``model.with_config(tags=[...])``)

    and return ``event["data"]["chunk"].content`` of each, skipping empty
    strings, in order.
    """
    tokens: list[str] = []
    async for event in chain.astream_events(inputs, version="v2"):
        if event["event"] == "on_chat_model_stream" and tag in event.get("tags", []):
            content = event["data"]["chunk"].content
            if content:
                tokens.append(content)
    return tokens


# ---------------------------------------------------------------------------
# Task 4: a per-session history store
# ---------------------------------------------------------------------------
class SessionStore:
    """In-memory chat history keyed by ``session_id`` (Redis/Postgres in production).

    * ``max_messages``: each session keeps only its newest ``max_messages``
      messages; older ones are dropped when new ones are appended.
    * ``get(session_id)`` returns a **copy** of the session's messages
      (``[]`` for an unknown session), so callers cannot corrupt the store.
    * ``append(session_id, messages)`` adds messages in order.
    * ``clear(session_id)`` forgets a session (no error if unknown).
    * ``session_ids()`` returns the known ids, sorted.
    * ``max_messages < 1`` raises ``ValueError``.

    Why not ``RunnableWithMessageHistory`` + ``InMemoryChatMessageHistory``?
    Both are deprecated in langchain-core 1.x (LangChain now points to
    LangGraph persistence). Managing history yourself is a few lines and
    makes the storage explicit.
    """

    def __init__(self, max_messages: int = 20) -> None:
        if max_messages < 1:
            raise ValueError("max_messages must be >= 1")
        self.max_messages = max_messages
        self._sessions: dict[str, list[BaseMessage]] = {}

    def get(self, session_id: str) -> list[BaseMessage]:
        return list(self._sessions.get(session_id, []))

    def append(self, session_id: str, messages: Sequence[BaseMessage]) -> None:
        history = self._sessions.setdefault(session_id, [])
        history.extend(messages)
        del history[: -self.max_messages]

    def clear(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def session_ids(self) -> list[str]:
        return sorted(self._sessions)


# ---------------------------------------------------------------------------
# Task 5: chat with memory, keyed by session_id in the config
# ---------------------------------------------------------------------------
HISTORY_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", CHAT_SYSTEM),
        MessagesPlaceholder("history"),
        ("human", "{question}"),
    ]
)


def build_chat_with_history(model: ChatModel, store: SessionStore) -> Runnable[dict, str]:
    """A chain that remembers the conversation of each session.

    Input ``{"question": str}``, output ``str``; the session comes from the
    config, just like ``RunnableWithMessageHistory`` did::

        chain.invoke({"question": "hi"}, config={"configurable": {"session_id": "abc"}})

    Return a ``RunnableLambda`` whose function takes ``(inputs, config)`` and:

    1. reads ``config["configurable"]["session_id"]``; missing -> ``ValueError``
    2. loads ``store.get(session_id)`` as ``history``
    3. runs ``HISTORY_PROMPT | model | StrOutputParser()`` with
       ``{"history": history, "question": question}``
    4. appends ``HumanMessage(question)`` and ``AIMessage(answer)`` to the
       session (only after the model succeeded) and returns the answer

    Sessions are independent: one session never sees another's messages.
    """
    chain = HISTORY_PROMPT | model | StrOutputParser()

    def chat(inputs: dict, config: RunnableConfig) -> str:
        session_id = (config.get("configurable") or {}).get("session_id")
        if not session_id:
            raise ValueError("config['configurable']['session_id'] is required")
        question = inputs["question"]
        answer = chain.invoke({"history": store.get(session_id), "question": question})
        store.append(session_id, [HumanMessage(question), AIMessage(answer)])
        return answer

    return RunnableLambda(chat)


# ---------------------------------------------------------------------------
# Task 6: a custom callback handler
# ---------------------------------------------------------------------------
class TokenCountingHandler(BaseCallbackHandler):
    """Count model activity: the building block of usage metrics and logging.

    Public attributes (all start at zero / empty):

    * ``chat_model_starts``: number of ``on_chat_model_start`` calls
      (chat models: ``GenericFakeChatModel``, ``ChatOpenAI``, ...)
    * ``llm_starts``: number of ``on_llm_start`` calls (plain text
      completion models such as ``FakeListLLM``)
    * ``tokens``: list of every token from ``on_llm_new_token`` (only fired
      while *streaming*)
    * ``llm_ends``: number of ``on_llm_end`` calls (fired for both kinds)
    * ``errors``: list of exceptions from ``on_llm_error``
    * ``tags``: set of all tags seen in any of the start callbacks
      (they arrive as the ``tags`` keyword argument)

    Accept ``**kwargs`` in every method: LangChain passes ``run_id``,
    ``parent_run_id``, ``tags``, ``metadata`` and more.

    Note: implementing ``on_chat_model_start`` matters. If a handler does
    not implement it, LangChain falls back to calling ``on_llm_start`` for
    chat models too.
    """

    def __init__(self) -> None:
        self.chat_model_starts = 0
        self.llm_starts = 0
        self.tokens: list[str] = []
        self.llm_ends = 0
        self.errors: list[BaseException] = []
        self.tags: set[str] = set()

    def on_chat_model_start(
        self, serialized: dict[str, Any], messages: list[list[BaseMessage]], **kwargs: Any
    ) -> None:
        self.chat_model_starts += 1
        self.tags.update(kwargs.get("tags") or [])

    def on_llm_start(self, serialized: dict[str, Any], prompts: list[str], **kwargs: Any) -> None:
        self.llm_starts += 1
        self.tags.update(kwargs.get("tags") or [])

    def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        self.tokens.append(token)

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        self.llm_ends += 1

    def on_llm_error(self, error: BaseException, **kwargs: Any) -> None:
        self.errors.append(error)


# ---------------------------------------------------------------------------
# Task 7: passing callbacks, tags and metadata via the config
# ---------------------------------------------------------------------------
def invoke_traced(
    chain: Runnable,
    inputs: Any,
    handler: BaseCallbackHandler,
    *,
    user_id: str,
    request_id: str,
) -> Any:
    """Invoke ``chain`` with per-request observability attached.

    Build a ``RunnableConfig`` with:

    * ``callbacks=[handler]``: request-scoped, so concurrent requests do
      not mix their counts (unlike callbacks set on the model itself)
    * ``tags=[f"user:{user_id}"]``
    * ``metadata={"user_id": user_id, "request_id": request_id}``
    * ``run_name="chat_request"``

    and return ``chain.invoke(inputs, config=config)``. Every nested step
    (prompt, model, parser) receives the same callbacks, tags and metadata.
    """
    config: RunnableConfig = {
        "callbacks": [handler],
        "tags": [f"user:{user_id}"],
        "metadata": {"user_id": user_id, "request_id": request_id},
        "run_name": "chat_request",
    }
    return chain.invoke(inputs, config=config)
