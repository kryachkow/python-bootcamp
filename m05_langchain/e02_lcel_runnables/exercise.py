"""Exercise 5.2: LCEL and runnables.

LCEL (LangChain Expression Language) builds pipelines out of ``Runnable``
objects joined with ``|``. Every runnable has the same API: ``invoke``,
``batch``, ``stream`` and their async twins. Each task below builds or wraps
one. Models are passed in as parameters, so tests can use fakes and your app
can pass a real provider. Run the tests with:

    uv run pytest m05_langchain/e02_lcel_runnables
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from operator import itemgetter
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import (
    Runnable,
    RunnableBranch,
    RunnableConfig,
    RunnableLambda,
    RunnableParallel,
    RunnablePassthrough,
)

# A "model" here is anything runnable that turns a prompt into a message: a real
# chat model, a fake one, or a RunnableLambda spy in the tests.
ChatModel = BaseChatModel | Runnable[Any, Any]


# ---------------------------------------------------------------------------
# Task 1: the pipe operator
# ---------------------------------------------------------------------------
def build_normalizer() -> Runnable[str, str]:
    """Return a 3-step ``RunnableSequence`` that cleans user input.

    Steps, in this order, each one its own ``RunnableLambda`` joined with ``|``:

    1. strip leading/trailing whitespace
    2. collapse every run of whitespace (spaces, tabs, newlines) into one space
    3. lowercase

    >>> build_normalizer().invoke("  Hello \\n\\t WORLD ")
    'hello world'

    The returned object's ``.steps`` must have length 3.
    """
    return (
        RunnableLambda(str.strip)
        | RunnableLambda(lambda s: re.sub(r"\s+", " ", s))
        | RunnableLambda(str.lower)
    )


# ---------------------------------------------------------------------------
# Task 2: prompt | model | parser
# ---------------------------------------------------------------------------
ANSWER_SYSTEM = "You are a concise assistant. Answer in one sentence."


def build_answer_chain(model: ChatModel) -> Runnable[dict, str]:
    """The canonical LCEL chain: ``prompt | model | StrOutputParser()``.

    * The prompt has two messages: system ``ANSWER_SYSTEM`` and human
      ``"{question}"``.
    * Input: ``{"question": str}``. Output: the model's reply text as ``str``.
    """
    prompt = ChatPromptTemplate.from_messages([("system", ANSWER_SYSTEM), ("human", "{question}")])
    return prompt | model | StrOutputParser()


# ---------------------------------------------------------------------------
# Task 3: RunnableParallel (dict syntax)
# ---------------------------------------------------------------------------
def build_analysis_chain(model: ChatModel) -> Runnable[dict, dict]:
    """Run several branches on the same input and collect the results in a dict.

    Input: ``{"question": str}``. Output::

        {
            "question": <the question, unchanged>,
            "answer": <the Task 2 chain's output>,
            "word_count": <number of whitespace-separated words in the question>,
        }

    All three branches receive the same input. Build it with a plain dict
    literal of runnables / callables (LCEL coerces it into a
    ``RunnableParallel``), e.g. ``RunnableParallel({...})`` or
    ``{...} | RunnablePassthrough()``.

    Hint: ``operator.itemgetter("question")`` is a handy branch.
    """
    return RunnableParallel(
        {
            "question": itemgetter("question"),
            "answer": build_answer_chain(model),
            "word_count": lambda x: len(x["question"].split()),
        }
    )


# ---------------------------------------------------------------------------
# Task 4: RunnablePassthrough.assign
# ---------------------------------------------------------------------------
def build_enrich_chain(retrieve: Callable[[str], list[str]]) -> Runnable[dict, dict]:
    """Add keys to the input dict without losing the existing ones.

    Input: any dict with at least a ``"question"`` key. Output: the same dict
    plus

    * ``"snippets"``: ``retrieve(question)`` (called exactly once)
    * ``"context"``: the snippets joined with ``"\\n"`` (``""`` when there are none)

    ``context`` is computed *from* ``snippets``, so you need two ``.assign``
    steps: ``RunnablePassthrough.assign(snippets=...).assign(context=...)``.
    The input dict must not be mutated.
    """
    return RunnablePassthrough.assign(snippets=lambda x: retrieve(x["question"])).assign(
        context=lambda x: "\n".join(x["snippets"])
    )


# ---------------------------------------------------------------------------
# Task 5: routing
# ---------------------------------------------------------------------------
def build_router(routes: Mapping[str, Runnable], default: Runnable) -> Runnable[dict, Any]:
    """Send the input to a different runnable depending on ``input["topic"]``.

    * Match ``topic`` against the keys of ``routes`` case-insensitively and
      ignoring surrounding whitespace (keys are lowercase).
    * A missing or unknown topic goes to ``default``.
    * The chosen runnable receives the **whole** input dict, unchanged.

    Use ``RunnableBranch((condition, runnable), ..., default)`` or a
    ``RunnableLambda`` that *returns* a runnable (LCEL then invokes it).
    """
    def topic_of(x: dict) -> str:
        return str(x.get("topic") or "").strip().lower()

    branches = [
        (lambda x, key=key: topic_of(x) == key, runnable) for key, runnable in routes.items()
    ]
    if not branches:
        return default
    return RunnableBranch(*branches, default)


# ---------------------------------------------------------------------------
# Task 6: fallbacks
# ---------------------------------------------------------------------------
def with_backup(primary: Runnable, backup: Runnable) -> Runnable:
    """Return ``primary`` that falls back to ``backup`` on *transient* errors.

    * ``TimeoutError`` and ``ConnectionError`` (provider down, rate limited...)
      switch to ``backup``.
    * Any other exception (e.g. a ``ValueError`` from bad input) is raised as
      is; the backup is **not** called.

    Hint: ``primary.with_fallbacks([backup], exceptions_to_handle=(...))``.
    """
    return primary.with_fallbacks([backup], exceptions_to_handle=(TimeoutError, ConnectionError))


# ---------------------------------------------------------------------------
# Task 7: retries
# ---------------------------------------------------------------------------
def with_retries(runnable: Runnable, attempts: int) -> Runnable:
    """Retry ``runnable`` up to ``attempts`` times in total on ``ConnectionError``.

    * Only ``ConnectionError`` (and subclasses) is retried; other errors
      fail on the first attempt.
    * No waiting between attempts (keeps tests fast; in production you
      would keep the exponential back-off).
    * ``attempts < 1`` raises ``ValueError``.

    Hint: ``runnable.with_retry(stop_after_attempt=..., retry_if_exception_type=...,
    wait_exponential_jitter=False)``.
    """
    if attempts < 1:
        raise ValueError("attempts must be >= 1")
    return runnable.with_retry(
        stop_after_attempt=attempts,
        retry_if_exception_type=(ConnectionError,),
        wait_exponential_jitter=False,
    )


# ---------------------------------------------------------------------------
# Task 8: batch / abatch
# ---------------------------------------------------------------------------
def run_batch(
    chain: Runnable, inputs: Sequence[Any], max_concurrency: int = 4
) -> tuple[list[Any], dict[int, str]]:
    """Run ``chain`` over many inputs; one failure must not fail the whole batch.

    Returns ``(results, errors)``:

    * ``results[i]`` is the output for ``inputs[i]``, or ``None`` if it failed
    * ``errors`` maps the index of every failed input to ``str(exception)``

    Pass ``max_concurrency`` through the ``RunnableConfig``.

    Hint: ``chain.batch(inputs, config={...}, return_exceptions=True)``.
    """
    outputs = chain.batch(
        list(inputs), config={"max_concurrency": max_concurrency}, return_exceptions=True
    )
    results: list[Any] = []
    errors: dict[int, str] = {}
    for i, out in enumerate(outputs):
        if isinstance(out, Exception):
            results.append(None)
            errors[i] = str(out)
        else:
            results.append(out)
    return results, errors


async def arun_batch(
    chain: Runnable, inputs: Sequence[Any], max_concurrency: int = 4
) -> tuple[list[Any], dict[int, str]]:
    """Async version of ``run_batch`` built on ``chain.abatch``. Same contract."""
    outputs = await chain.abatch(
        list(inputs), config={"max_concurrency": max_concurrency}, return_exceptions=True
    )
    results: list[Any] = []
    errors: dict[int, str] = {}
    for i, out in enumerate(outputs):
        if isinstance(out, Exception):
            results.append(None)
            errors[i] = str(out)
        else:
            results.append(out)
    return results, errors


# ---------------------------------------------------------------------------
# Task 9: RunnableConfig and with_config
# ---------------------------------------------------------------------------
GREETING_SYSTEM = "You are talking to {user_name}. Address them by name."


def build_personalized_chain(model: ChatModel) -> Runnable[dict, str]:
    """A chain that reads per-request data from the ``RunnableConfig``.

    Input: ``{"question": str}``. Output: ``str``. Steps:

    1. A ``RunnableLambda`` whose function takes ``(input, config)`` and
       returns the input plus ``"user_name"``, read from
       ``config["configurable"]["user_name"]`` (default ``"guest"`` when it
       is missing).
    2. A prompt: system ``GREETING_SYSTEM``, human ``"{question}"``.
    3. ``model``, then ``StrOutputParser()``.

    Wrap the whole chain with ``.with_config(run_name="personalized_chain",
    tags=["personalized"])``, so the tag reaches every step (and tracing tools
    such as LangSmith show a nicely named run).

    Usage::

        chain.invoke({"question": "hi"}, config={"configurable": {"user_name": "Olena"}})

    Hint: LangChain passes the config to a lambda's function if it has a
    parameter named ``config``.
    """
    def add_user(x: dict, config: RunnableConfig) -> dict:
        user_name = (config.get("configurable") or {}).get("user_name", "guest")
        return {**x, "user_name": user_name}

    prompt = ChatPromptTemplate.from_messages([("system", GREETING_SYSTEM), ("human", "{question}")])
    chain = RunnableLambda(add_user) | prompt | model | StrOutputParser()
    return chain.with_config(run_name="personalized_chain", tags=["personalized"])
