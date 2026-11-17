"""Exercise 5.3: output parsers.

A model returns text; your backend needs a ``str``, a ``list``, a ``dict`` or
a validated Pydantic object. Output parsers do that conversion, describe the
expected format to the model (``get_format_instructions``), and raise
``OutputParserException`` when the reply does not match. Run the tests with:

    uv run pytest m05_langchain/e03_output_parsers
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

from langchain_core.exceptions import OutputParserException
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.output_parsers import (
    BaseOutputParser,
    CommaSeparatedListOutputParser,
    JsonOutputParser,
    PydanticOutputParser,
    StrOutputParser,
)
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableLambda
from pydantic import BaseModel, Field

ChatModel = BaseChatModel | Runnable[Any, Any]


# ---------------------------------------------------------------------------
# Task 1: StrOutputParser (and why it beats `lambda m: m.content`)
# ---------------------------------------------------------------------------
SUMMARY_SYSTEM = "Summarise the user's text in one sentence."


def build_summary_chain(model: ChatModel) -> Runnable[dict, str]:
    """``prompt | model | StrOutputParser()`` with input ``{"text": str}``.

    * Prompt: system ``SUMMARY_SYSTEM``, human ``"{text}"``.
    * ``invoke`` returns the reply as a ``str``.
    * ``stream`` must yield the reply **token by token** as ``str`` chunks.
      ``StrOutputParser`` is a streaming-aware transformer; a
      ``RunnableLambda(lambda m: m.content)`` would wait for the whole
      message and yield it once.
    """
    raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 2: JsonOutputParser
# ---------------------------------------------------------------------------
def parse_json_reply(text: str) -> Any:
    """Parse a model reply that should contain JSON.

    * Plain JSON (``'{"a": 1}'``) and JSON inside a Markdown code fence
      (`````json ... `````) are both accepted, since models love fences.
    * Anything that is not JSON raises ``OutputParserException``.

    Hint: ``JsonOutputParser().parse(text)`` already does all of this.
    """
    raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 3: CommaSeparatedListOutputParser + format instructions
# ---------------------------------------------------------------------------
TAGS_SYSTEM = "Suggest tags for the support ticket.\n{format_instructions}"


def build_tags_chain(model: ChatModel) -> Runnable[dict, list[str]]:
    """Return tags for a ticket as a clean list of strings.

    Input: ``{"ticket": str}``.

    * Prompt: system ``TAGS_SYSTEM`` with ``format_instructions`` pre-filled
      (``.partial``) from ``CommaSeparatedListOutputParser().get_format_instructions()``;
      human ``"{ticket}"``. So the only input variable left is ``ticket``.
    * Parse with ``CommaSeparatedListOutputParser``, then normalise: strip
      and lowercase every tag, drop empty ones, remove duplicates keeping
      the first occurrence.

    A reply ``"Billing, refund ,BILLING, "`` gives ``["billing", "refund"]``.
    """
    raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 4: PydanticOutputParser
# ---------------------------------------------------------------------------
class Invoice(BaseModel):
    """Structured data extracted from an invoice e-mail."""

    vendor: str = Field(description="Company that issued the invoice")
    total: float = Field(ge=0, description="Total amount due")
    currency: str = Field(min_length=3, max_length=3, description="ISO 4217 code, e.g. EUR")
    due_date: str | None = Field(default=None, description="Due date as YYYY-MM-DD, if present")


INVOICE_SYSTEM = "Extract the invoice data from the e-mail.\n{format_instructions}"


def build_invoice_chain(model: ChatModel) -> Runnable[dict, Invoice]:
    """Extract an ``Invoice`` from ``{"email": str}``.

    * Prompt: system ``INVOICE_SYSTEM`` with ``format_instructions`` taken
      from ``PydanticOutputParser(pydantic_object=Invoice).get_format_instructions()``
      (it embeds the JSON schema, field descriptions included); human ``"{email}"``.
    * Parse with that ``PydanticOutputParser``: the chain returns an
      ``Invoice`` instance.
    * A reply that is not JSON, or JSON that fails validation (e.g. a
      negative total), raises ``OutputParserException``.
    """
    raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 5: streaming partial JSON
# ---------------------------------------------------------------------------
def stream_json_progress(model: ChatModel, question: str) -> Iterator[dict]:
    """Stream a JSON reply as a series of ever-more-complete dicts.

    Build ``ChatPromptTemplate.from_messages([("human", "{question}")]) | model | JsonOutputParser()``
    and yield what its ``.stream({"question": question})`` produces.

    ``JsonOutputParser`` parses the *partial* JSON seen so far, so a UI can
    render fields as they arrive: for a reply ``{"city": "Kyiv", "temp": 21}``
    streamed word by word you get e.g. ``{}``, ``{"city": "Kyiv"}``, ...,
    ``{"city": "Kyiv", "temp": 21}``. The last yielded dict is the full
    object.

    This is a generator function: use ``yield from``.
    """
    raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 6: a custom output parser
# ---------------------------------------------------------------------------
class AnswerWithConfidence(BaseModel):
    answer: str
    confidence: float


class AnswerWithConfidenceParser(BaseOutputParser[AnswerWithConfidence]):
    """Parse replies in this format into ``AnswerWithConfidence``::

        Answer: Paris is the capital of France.
        Confidence: 0.9

    Rules for ``parse(text)``:

    * Labels are case-insensitive (``answer:``, ``CONFIDENCE:``); whitespace
      around labels and values is ignored. Text before ``Answer:`` is ignored.
    * The answer is everything between ``Answer:`` and the ``Confidence:``
      line; it may span several lines (strip it, keep inner newlines).
    * Confidence must be a number in ``[0, 1]``; ``"85%"`` is accepted and
      means ``0.85``.
    * A missing label, an empty answer, a non-numeric confidence or one out
      of range raises ``OutputParserException`` (include the offending text
      in the message, set ``llm_output=text``).

    Also implement:

    * ``get_format_instructions()``: a string that tells the model to answer
      with the two lines above; it must mention ``Answer:`` and ``Confidence:``.
    * the ``_type`` property returning ``"answer_with_confidence"``.

    Hint: ``re.search(r"answer:\\s*(.*?)\\s*confidence:\\s*(\\S+)", text, re.I | re.S)``.
    """

    pass


# ---------------------------------------------------------------------------
# Task 7: parse, or retry once with the error as feedback
# ---------------------------------------------------------------------------
RETRY_FEEDBACK = (
    "Your previous reply could not be parsed: {error}\n"
    "Reply again and follow the format instructions exactly."
)


def ask_with_retry(model: ChatModel, messages: list[BaseMessage], parser: BaseOutputParser) -> Any:
    """Call ``model`` and parse its reply; on a parse error, retry **once**.

    1. ``reply = model.invoke(messages)``; return ``parser.parse(reply.content)``.
    2. If that raises ``OutputParserException`` as ``e``, call the model a
       second time with the conversation extended by the bad reply and the
       feedback::

           messages + [AIMessage(<bad reply text>),
                       HumanMessage(RETRY_FEEDBACK.format(error=e))]

       and return the parsed second reply.
    3. If the second reply cannot be parsed either, let its
       ``OutputParserException`` propagate. Never call the model more than
       twice. Do not mutate ``messages``.

    Other exceptions (e.g. from the model) are not caught.

    This is what LangChain's old ``RetryWithErrorOutputParser`` did; writing
    it by hand keeps the retry visible and testable.
    """
    raise NotImplementedError("TODO: implement this task")
