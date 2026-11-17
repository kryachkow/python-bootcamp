"""Exercise 5.1: messages and prompt templates.

Every LLM call in a LangChain backend starts as a list of messages built from
a prompt template. Implement every function below; each docstring is the spec.
Run the tests with:

    uv run pytest m05_langchain/e01_prompts_and_messages
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
    trim_messages,
)
from langchain_core.prompts import (
    ChatPromptTemplate,
    FewShotChatMessagePromptTemplate,
    MessagesPlaceholder,
    PromptTemplate,
)


# ---------------------------------------------------------------------------
# Task 1: database rows -> message objects
# ---------------------------------------------------------------------------
def records_to_messages(records: Sequence[dict[str, Any]]) -> list[BaseMessage]:
    """Turn chat-history rows (as stored in a DB or sent by a frontend) into messages.

    Each record has a ``"role"`` and a ``"content"`` key. Map roles like this:

    ============  =====================================================
    role          message
    ============  =====================================================
    ``system``    ``SystemMessage(content)``
    ``user``      ``HumanMessage(content)``
    ``assistant`` ``AIMessage(content, tool_calls=record.get("tool_calls", []))``
    ``tool``      ``ToolMessage(content, tool_call_id=record["tool_call_id"])``
    ============  =====================================================

    * Keep the order of the records.
    * A ``tool`` record without ``"tool_call_id"`` raises ``ValueError``
      (a ToolMessage must always point at the tool call it answers).
    * An unknown role raises ``ValueError`` naming the role.

    >>> records_to_messages([{"role": "user", "content": "hi"}])
    [HumanMessage(content='hi', ...)]
    """
    messages: list[BaseMessage] = []
    for record in records:
        role, content = record["role"], record["content"]
        if role == "system":
            messages.append(SystemMessage(content))
        elif role == "user":
            messages.append(HumanMessage(content))
        elif role == "assistant":
            messages.append(AIMessage(content, tool_calls=record.get("tool_calls", [])))
        elif role == "tool":
            if "tool_call_id" not in record:
                raise ValueError("tool record needs a 'tool_call_id'")
            messages.append(ToolMessage(content, tool_call_id=record["tool_call_id"]))
        else:
            raise ValueError(f"unknown role: {role!r}")
    return messages


# ---------------------------------------------------------------------------
# Task 2: message objects -> database rows
# ---------------------------------------------------------------------------
def messages_to_records(messages: Sequence[BaseMessage]) -> list[dict[str, Any]]:
    """The inverse of Task 1: serialise messages to plain dicts for storage.

    * Every record has ``"role"`` and ``"content"``. The role comes from
      ``message.type``: ``"system"`` -> ``"system"``, ``"human"`` -> ``"user"``,
      ``"ai"`` -> ``"assistant"``, ``"tool"`` -> ``"tool"``.
    * An ``AIMessage`` with tool calls also gets ``"tool_calls"``: a list of
      ``{"name", "args", "id"}`` dicts. Leave the key out when there are none.
    * A ``ToolMessage`` also gets ``"tool_call_id"``.
    * Any other message type raises ``ValueError``.

    ``records_to_messages(messages_to_records(msgs))`` must round-trip.

    Hint: dispatch on ``message.type`` rather than ``isinstance``; chunks
    (``AIMessageChunk``) have ``type == "AIMessageChunk"`` and are rejected.
    """
    roles = {"system": "system", "human": "user", "ai": "assistant", "tool": "tool"}
    records: list[dict[str, Any]] = []
    for message in messages:
        if message.type not in roles:
            raise ValueError(f"cannot serialise message of type {message.type!r}")
        record: dict[str, Any] = {"role": roles[message.type], "content": message.content}
        if isinstance(message, AIMessage) and message.tool_calls:
            record["tool_calls"] = [
                {"name": tc["name"], "args": tc["args"], "id": tc["id"]} for tc in message.tool_calls
            ]
        if isinstance(message, ToolMessage):
            record["tool_call_id"] = message.tool_call_id
        records.append(record)
    return records


# ---------------------------------------------------------------------------
# Task 3: chat prompt with a history placeholder
# ---------------------------------------------------------------------------
def build_qa_prompt() -> ChatPromptTemplate:
    """Build the chat prompt used by a support assistant.

    The prompt has three parts, in this order:

    1. a system message, exactly:
       ``"You are {assistant_name}, a support assistant for {company}. Answer in {language}."``
    2. an *optional* ``MessagesPlaceholder`` called ``"history"``
       (the conversation so far; may be omitted on the first turn)
    3. a human message, exactly ``"{question}"``

    So ``input_variables`` is ``['assistant_name', 'company', 'language', 'question']``
    (sorted) and ``"history"`` is in ``optional_variables``.

    Hint: ``ChatPromptTemplate.from_messages([("system", ...), MessagesPlaceholder(...), ("human", ...)])``.
    """
    return ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are {assistant_name}, a support assistant for {company}. Answer in {language}.",
            ),
            MessagesPlaceholder("history", optional=True),
            ("human", "{question}"),
        ]
    )


# ---------------------------------------------------------------------------
# Task 4: partial variables
# ---------------------------------------------------------------------------
def build_company_prompt(
    company: str,
    get_language: Callable[[], str],
    assistant_name: str = "Ava",
) -> ChatPromptTemplate:
    """Pre-fill the Task 3 prompt so callers only pass ``question`` (and ``history``).

    * ``company`` and ``assistant_name`` are fixed *values*.
    * ``language`` is filled by calling ``get_language()`` **each time the
      prompt is formatted** (e.g. it reads a per-request setting), not once
      when the prompt is built.
    * The result's ``input_variables`` is ``['question']``.

    Hint: ``ChatPromptTemplate.partial`` accepts strings *and* zero-argument
    callables.
    """
    return build_qa_prompt().partial(
        company=company, assistant_name=assistant_name, language=get_language
    )


# ---------------------------------------------------------------------------
# Task 5: string template with literal braces
# ---------------------------------------------------------------------------
def build_extraction_prompt() -> PromptTemplate:
    """Build a plain-text ``PromptTemplate`` that asks for JSON output.

    Formatting it with ``text="Bob is 42"`` must give exactly::

        Extract the person from the text below.
        Reply with JSON like {"name": "Alice", "age": 30}.

        Text: Bob is 42

    * The only input variable is ``text``.

    Hint: f-string templates treat ``{`` as a variable; write a literal
    brace as ``{{`` / ``}}``.
    """
    return PromptTemplate.from_template(
        "Extract the person from the text below.\n"
        'Reply with JSON like {{"name": "Alice", "age": 30}}.\n'
        "\n"
        "Text: {text}"
    )


# ---------------------------------------------------------------------------
# Task 6: few-shot chat prompt
# ---------------------------------------------------------------------------
SENTIMENT_SYSTEM = "Classify the sentiment of the message as positive, negative or neutral."


def build_few_shot_prompt(examples: Sequence[dict[str, str]]) -> ChatPromptTemplate:
    """Build a few-shot sentiment classifier prompt.

    ``examples`` is a list of ``{"input": ..., "output": ...}`` dicts. The
    formatted messages must be:

    1. ``SystemMessage(SENTIMENT_SYSTEM)``
    2. for every example, in order: ``HumanMessage(input)`` then ``AIMessage(output)``
    3. ``HumanMessage("{input}")`` with the caller's input

    With no examples, only messages 1 and 3 remain. The only input variable
    is ``input``.

    Hint: ``FewShotChatMessagePromptTemplate(examples=..., example_prompt=...)``
    where ``example_prompt`` is a two-message ``ChatPromptTemplate``; put it
    inside the outer ``from_messages`` list.
    """
    example_prompt = ChatPromptTemplate.from_messages([("human", "{input}"), ("ai", "{output}")])
    few_shot = FewShotChatMessagePromptTemplate(
        examples=list(examples), example_prompt=example_prompt
    )
    return ChatPromptTemplate.from_messages(
        [("system", SENTIMENT_SYSTEM), few_shot, ("human", "{input}")]
    )


# ---------------------------------------------------------------------------
# Task 7: trim history by message count
# ---------------------------------------------------------------------------
def trim_history(messages: Sequence[BaseMessage], max_messages: int) -> list[BaseMessage]:
    """Keep at most ``max_messages`` messages from the end of a conversation.

    * A leading ``SystemMessage`` is always kept and **counts** towards
      ``max_messages``.
    * After trimming, the non-system part must start with a ``HumanMessage``
      (never with an orphan AI or tool message), so the result may be
      shorter than ``max_messages``.
    * ``max_messages < 1`` raises ``ValueError``.
    * The input is not modified.

    >>> trim_history([sys, h1, a1, h2, a2], 3)   # -> [sys, h2, a2]

    Hint: ``trim_messages(..., token_counter=len, strategy="last",
    include_system=True, start_on="human")``. With ``token_counter=len``
    every message costs one "token".
    """
    if max_messages < 1:
        raise ValueError("max_messages must be >= 1")
    return trim_messages(
        list(messages),
        max_tokens=max_messages,
        token_counter=len,
        strategy="last",
        include_system=True,
        start_on="human",
    )


# ---------------------------------------------------------------------------
# Task 8: trim history by a token budget
# ---------------------------------------------------------------------------
def trim_to_token_budget(
    messages: Sequence[BaseMessage],
    max_tokens: int,
    count_tokens: Callable[[str], int],
) -> list[BaseMessage]:
    """Fit a conversation into a context-window budget.

    ``count_tokens(text)`` returns the token cost of one message's content
    (in production: a tokenizer such as tiktoken; in tests: word count).

    Rules:

    * Every ``SystemMessage`` at the start of ``messages`` is always kept,
      and its cost is paid first. If the system messages alone cost more
      than ``max_tokens``, raise ``ValueError``.
    * Walk the remaining messages from newest to oldest and keep each one
      while the running total stays ``<= max_tokens``. Stop at the first
      message that does not fit (do not skip it and keep older ones).
    * Then drop messages from the *front* of the kept part until it starts
      with a ``HumanMessage``. (If none is left, return just the system
      messages.)
    * Return the system messages followed by the kept messages, in the
      original order.

    Example with ``count_tokens = lambda s: len(s.split())`` and budget 6:
    ``[System("be brief"), Human("a b"), AI("c d"), Human("e f"), AI("g")]``
    -> system costs 2; ``"g"`` (1), ``"e f"`` (2) fit; ``"c d"`` would make 7
    -> ``[System, Human("e f"), AI("g")]``.
    """
    messages = list(messages)
    n_system = 0
    while n_system < len(messages) and isinstance(messages[n_system], SystemMessage):
        n_system += 1
    system, rest = messages[:n_system], messages[n_system:]

    used = sum(count_tokens(m.text) for m in system)
    if used > max_tokens:
        raise ValueError("system prompt alone exceeds the token budget")

    kept: list[BaseMessage] = []
    for message in reversed(rest):
        cost = count_tokens(message.text)
        if used + cost > max_tokens:
            break
        used += cost
        kept.append(message)
    kept.reverse()

    while kept and not isinstance(kept[0], HumanMessage):
        kept.pop(0)
    return system + kept
