"""Exercise 5.4: tools and a hand-written tool-calling agent.

A *tool* is a Python function plus a name, a description and a JSON schema
for its arguments. The model never runs code: it replies with
``AIMessage.tool_calls``; your code runs the tools and sends the results
back as ``ToolMessage`` objects whose ``tool_call_id`` matches the call.
Repeat until the model answers without tool calls. That loop is what agent
frameworks (LangGraph's ``create_react_agent`` & co.) do for you; here you
write it yourself. Run the tests with:

    uv run pytest m05_langchain/e04_tools_and_tool_calling
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.messages.tool import ToolCall
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool, StructuredTool, ToolException, tool
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import BaseModel, Field

# Fake data the tools read from (in real life: an HTTP API or the database).
TEMPERATURES_C = {"kyiv": 21.0, "london": 14.0, "lisbon": 26.5}

ORDERS = [
    {"id": 1, "customer_email": "ann@example.com", "status": "shipped", "total": 30.0},
    {"id": 2, "customer_email": "bob@example.com", "status": "pending", "total": 12.5},
    {"id": 3, "customer_email": "ann@example.com", "status": "pending", "total": 99.9},
    {"id": 4, "customer_email": "cid@example.com", "status": "delivered", "total": 5.0},
]


# ---------------------------------------------------------------------------
# Task 1: the @tool decorator
# ---------------------------------------------------------------------------
# Define a tool called `get_weather` with the `@tool(parse_docstring=True)`
# decorator. The function signature:
#
#     get_weather(city: str, unit: Literal["celsius", "fahrenheit"] = "celsius") -> str
#
# * Its docstring (Google style) must produce:
#     - description: "Get the current temperature in a city."
#     - an `Args:` section describing `city` ("City name, e.g. Kyiv.") and
#       `unit` ("Temperature unit."). With parse_docstring=True these become
#       the argument descriptions in the JSON schema the model sees.
# * Look the city up in TEMPERATURES_C case-insensitively.
#   Return e.g. "Kyiv: 21.0°C" or, for fahrenheit, "Kyiv: 69.8°F"
#   (F = C * 9 / 5 + 32, one decimal place; keep the city as passed in).
# * Unknown city -> return "Unknown city: <city>" (a string the model can read,
#   not an exception).
#
get_weather = None  # TODO: replace with the @tool-decorated function


# ---------------------------------------------------------------------------
# Task 2: StructuredTool with a Pydantic args_schema
# ---------------------------------------------------------------------------
class SearchOrdersInput(BaseModel):
    """Arguments of the `search_orders` tool. The descriptions are what the model reads."""

    customer_email: str | None = Field(default=None, description="Only orders of this customer")
    status: Literal["pending", "shipped", "delivered"] | None = Field(
        default=None, description="Only orders in this status"
    )
    limit: int = Field(default=10, ge=1, le=50, description="Maximum number of orders to return")


def build_search_orders_tool() -> StructuredTool:
    """Build the ``search_orders`` tool with ``StructuredTool.from_function``.

    * ``name="search_orders"``,
      ``description="Search customer orders by e-mail and/or status."``,
      ``args_schema=SearchOrdersInput``.
    * The function filters ``ORDERS``: keep orders matching every filter
      that is not ``None``, in ``ORDERS`` order, at most ``limit`` of them.
    * It returns the matches as a **JSON string** (``json.dumps(list_of_dicts)``).
      Tools should return text: it goes straight into a ``ToolMessage``.
    * Invalid arguments (e.g. ``limit=0``, ``status="lost"``) are rejected
      by the schema: ``tool.invoke`` raises ``pydantic.ValidationError``.
    """
    raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 3: what the provider sees
# ---------------------------------------------------------------------------
def tool_specs(tools: Sequence[BaseTool]) -> list[dict[str, Any]]:
    """Return the OpenAI-style function specs that ``bind_tools`` would send.

    * One spec per tool, in order, made by
      ``langchain_core.utils.function_calling.convert_to_openai_tool``:
      ``{"type": "function", "function": {"name", "description", "parameters"}}``.
    * Providers reject duplicate tool names, so two tools with the same
      ``.name`` raise ``ValueError`` naming the duplicate.
    """
    raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 4: execute one tool call
# ---------------------------------------------------------------------------
def execute_tool_call(tool_call: ToolCall, tools_by_name: Mapping[str, BaseTool]) -> ToolMessage:
    """Run the tool a model asked for and wrap the result in a ``ToolMessage``.

    ``tool_call`` is one entry of ``AIMessage.tool_calls``:
    ``{"name": ..., "args": {...}, "id": "call_1", "type": "tool_call"}``.

    * Known tool: ``tool.invoke(tool_call)``. Passing the whole ToolCall
      (not just the args) makes LangChain return a ``ToolMessage`` with the
      right ``tool_call_id`` and ``name``.
    * Unknown tool: do **not** raise (the model hallucinated a name; let it
      recover). Return ``ToolMessage(content=f"Error: unknown tool '{name}'",
      tool_call_id=<id>, name=<name>, status="error")``.
    """
    raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 5: tool error handling
# ---------------------------------------------------------------------------
def build_divide_tool() -> StructuredTool:
    """Build a ``divide(a: float, b: float) -> float`` tool that fails *politely*.

    * ``name="divide"``, description ``"Divide a by b."``.
    * ``b == 0`` raises ``ToolException("cannot divide by zero")`` inside the
      function. With ``handle_tool_error`` set to a callable, calling the tool
      with a ToolCall returns a ``ToolMessage`` with
      ``content="Tool error: cannot divide by zero"`` and ``status="error"``
      instead of crashing the agent.
    * Invalid arguments (``{"a": "x", "b": 1}``) also become a ToolMessage
      with content ``"Tool error: invalid arguments"`` (``handle_validation_error``).
    * Called with a plain args dict instead of a ToolCall, the tool returns
      the handled string itself: ``"Tool error: cannot divide by zero"``.
    * Any *other* exception (a bug in the tool) is still raised:
      ``handle_tool_error`` only catches ``ToolException``.

    Hint: ``StructuredTool.from_function(func, name=..., description=...,
    handle_tool_error=..., handle_validation_error=...)``.
    """
    raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 6: the agent loop
# ---------------------------------------------------------------------------
class MaxIterationsError(RuntimeError):
    """The model kept calling tools for longer than ``max_iterations``."""


@dataclass
class AgentResult:
    answer: str  # text of the final AIMessage (the one without tool calls)
    messages: list[BaseMessage]  # the full transcript, final AIMessage included
    model_calls: int


def run_agent(
    model: BaseChatModel | Runnable[Any, AIMessage],
    tools: Sequence[BaseTool],
    question: str,
    *,
    system_prompt: str | None = None,
    max_iterations: int = 5,
) -> AgentResult:
    """A minimal ReAct-style tool-calling loop.

    ``model`` must already know about the tools, e.g. ``llm.bind_tools(tools)``
    in production; in tests, a fake that returns scripted ``AIMessage`` s.

    1. ``messages = [SystemMessage(system_prompt)]`` (only if given)
       ``+ [HumanMessage(question)]``.
    2. Call ``model.invoke(messages)`` and append the reply.
    3. If the reply has no ``tool_calls``, return
       ``AgentResult(answer=reply.text, messages=messages, model_calls=n)``.
    4. Otherwise run **every** tool call in order with ``execute_tool_call``
       (Task 4) and append each ``ToolMessage``; go back to step 2.
    5. ``max_iterations`` limits the number of model calls. If the model
       still asks for tools on the last allowed call, raise
       ``MaxIterationsError`` (never loop forever, never run those tools).
    """
    raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 7: async agent with parallel tool calls
# ---------------------------------------------------------------------------
async def arun_agent(
    model: BaseChatModel | Runnable[Any, AIMessage],
    tools: Sequence[BaseTool],
    question: str,
    *,
    max_iterations: int = 5,
) -> AgentResult:
    """Async version of ``run_agent`` (no system prompt).

    * Use ``await model.ainvoke(messages)``.
    * When one reply contains several tool calls, run them **concurrently**
      with ``asyncio.gather`` over ``tool.ainvoke(tool_call)``, then append
      the ToolMessages in the **same order as the tool calls** (gather keeps
      order).
    * Unknown tools produce the same error ToolMessage as Task 4.
    * Same ``max_iterations`` rule and ``MaxIterationsError`` as Task 6.
    """
    raise NotImplementedError("TODO: implement this task")
