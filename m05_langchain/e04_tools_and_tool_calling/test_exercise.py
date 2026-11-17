import asyncio
import json

import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableLambda
from langchain_core.tools import BaseTool, tool
from pydantic import ValidationError

from m05_langchain.e04_tools_and_tool_calling import exercise
from m05_langchain.e04_tools_and_tool_calling.exercise import (
    AgentResult,
    MaxIterationsError,
    arun_agent,
    build_divide_tool,
    build_search_orders_tool,
    execute_tool_call,
    run_agent,
    tool_specs,
)


def call(name, args, id_="call_1"):
    return {"name": name, "args": args, "id": id_, "type": "tool_call"}


def ai_calls(*tool_calls):
    return AIMessage("", tool_calls=[{k: v for k, v in tc.items() if k != "type"} for tc in tool_calls])


# Test-local tools, so the agent tests do not depend on Tasks 1-2.
@tool
def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b


@tool
def shout(text: str) -> str:
    """Upper-case a text."""
    return text.upper()


class ScriptedModel:
    """Fake chat model: returns the scripted replies in order, records what it was sent."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.seen = []  # snapshot of the message list for every call

        def _call(messages):
            self.seen.append(list(messages))
            return self.replies[len(self.seen) - 1]

        self.runnable = RunnableLambda(_call)


class TestTask1GetWeatherTool:
    def test_is_a_tool_with_metadata(self):
        t = exercise.get_weather
        assert isinstance(t, BaseTool)
        assert t.name == "get_weather"
        assert t.description == "Get the current temperature in a city."

    def test_args_schema_from_signature_and_docstring(self):
        args = exercise.get_weather.args
        assert set(args) == {"city", "unit"}
        assert args["city"]["description"] == "City name, e.g. Kyiv."
        assert args["unit"]["enum"] == ["celsius", "fahrenheit"]
        assert args["unit"]["default"] == "celsius"

    def test_invoke(self):
        t = exercise.get_weather
        assert t.invoke({"city": "Kyiv"}) == "Kyiv: 21.0°C"
        assert t.invoke({"city": "KYIV", "unit": "fahrenheit"}) == "KYIV: 69.8°F"

    def test_unknown_city(self):
        assert exercise.get_weather.invoke({"city": "Atlantis"}) == "Unknown city: Atlantis"

    def test_invalid_unit_rejected(self):
        with pytest.raises(ValidationError):
            exercise.get_weather.invoke({"city": "Kyiv", "unit": "kelvin"})


class TestTask2SearchOrdersTool:
    @staticmethod
    def _search():
        return build_search_orders_tool()

    def test_metadata(self):
        search = self._search()
        assert search.name == "search_orders"
        assert search.description == "Search customer orders by e-mail and/or status."
        assert search.args["limit"]["description"] == "Maximum number of orders to return"

    def test_filters_and_returns_json(self):
        search = self._search()
        out = search.invoke({"customer_email": "ann@example.com", "status": "pending"})
        assert isinstance(out, str)
        assert [o["id"] for o in json.loads(out)] == [3]

    def test_no_filters_and_limit(self):
        search = self._search()
        assert [o["id"] for o in json.loads(search.invoke({"limit": 2}))] == [1, 2]
        assert len(json.loads(search.invoke({}))) == 4

    @pytest.mark.parametrize("args", [{"limit": 0}, {"status": "lost"}, {"limit": 51}])
    def test_invalid_args(self, args):
        search = self._search()
        with pytest.raises(ValidationError):
            search.invoke(args)


class TestTask3ToolSpecs:
    def test_openai_format(self):
        [spec] = tool_specs([add])
        assert spec["type"] == "function"
        fn = spec["function"]
        assert fn["name"] == "add"
        assert fn["description"] == "Add two integers."
        assert fn["parameters"]["required"] == ["a", "b"]
        assert fn["parameters"]["properties"]["a"]["type"] == "integer"

    def test_keeps_order(self):
        assert [s["function"]["name"] for s in tool_specs([shout, add])] == ["shout", "add"]

    def test_duplicate_names_rejected(self):
        @tool("add")
        def other_add(x: int) -> int:
            """Another add."""
            return x

        with pytest.raises(ValueError, match="add"):
            tool_specs([add, other_add])


class TestTask4ExecuteToolCall:
    TOOLS = {"add": add, "shout": shout}

    def test_returns_tool_message_with_matching_id(self):
        msg = execute_tool_call(call("add", {"a": 2, "b": 3}, "call_42"), self.TOOLS)
        assert isinstance(msg, ToolMessage)
        assert msg.content == "5"
        assert msg.tool_call_id == "call_42"
        assert msg.name == "add"

    def test_unknown_tool_is_an_error_message(self):
        msg = execute_tool_call(call("delete_db", {}, "call_7"), self.TOOLS)
        assert isinstance(msg, ToolMessage)
        assert msg.content == "Error: unknown tool 'delete_db'"
        assert msg.tool_call_id == "call_7"
        assert msg.status == "error"


class TestTask5DivideTool:
    @staticmethod
    def _divide():
        return build_divide_tool()

    def test_happy_path(self):
        divide = self._divide()
        assert divide.name == "divide"
        assert divide.description == "Divide a by b."
        msg = divide.invoke(call("divide", {"a": 7, "b": 2}))
        assert msg.content == "3.5"
        assert msg.status == "success"

    def test_tool_exception_becomes_message(self):
        divide = self._divide()
        msg = divide.invoke(call("divide", {"a": 1, "b": 0}, "c9"))
        assert isinstance(msg, ToolMessage)
        assert msg.content == "Tool error: cannot divide by zero"
        assert msg.status == "error"
        assert msg.tool_call_id == "c9"

    def test_invalid_arguments_become_message(self):
        divide = self._divide()
        msg = divide.invoke(call("divide", {"a": "lots", "b": 1}))
        assert msg.content == "Tool error: invalid arguments"
        assert msg.status == "error"

    def test_plain_args_invoke_returns_error_text(self):
        divide = self._divide()
        # without a ToolCall there is no ToolMessage: you get the handled string back
        assert divide.invoke({"a": 1, "b": 0}) == "Tool error: cannot divide by zero"


class TestTask6RunAgent:
    def test_tool_round_trip(self):
        model = ScriptedModel(ai_calls(call("add", {"a": 2, "b": 3}, "call_1")), AIMessage("2 + 3 = 5"))
        result = run_agent(model.runnable, [add], "What is 2 + 3?", system_prompt="Use tools.")
        assert isinstance(result, AgentResult)
        assert result.answer == "2 + 3 = 5"
        assert result.model_calls == 2
        # what the model saw on its second call
        second = model.seen[1]
        assert isinstance(second[0], SystemMessage) and second[0].content == "Use tools."
        assert isinstance(second[1], HumanMessage) and second[1].content == "What is 2 + 3?"
        assert second[2].tool_calls[0]["id"] == "call_1"
        assert isinstance(second[3], ToolMessage)
        assert (second[3].tool_call_id, second[3].content) == ("call_1", "5")
        assert result.messages[-1].content == "2 + 3 = 5"
        assert len(result.messages) == 5

    def test_several_calls_in_one_reply_and_several_rounds(self):
        model = ScriptedModel(
            ai_calls(call("add", {"a": 1, "b": 1}, "a1"), call("shout", {"text": "hi"}, "s1")),
            ai_calls(call("add", {"a": 2, "b": 2}, "a2")),
            AIMessage("done"),
        )
        result = run_agent(model.runnable, [add, shout], "go")
        tool_msgs = [m for m in result.messages if isinstance(m, ToolMessage)]
        assert [(m.tool_call_id, m.content) for m in tool_msgs] == [("a1", "2"), ("s1", "HI"), ("a2", "4")]
        assert result.model_calls == 3
        assert not isinstance(result.messages[0], SystemMessage)

    def test_no_tools_needed(self):
        model = ScriptedModel(AIMessage("hello"))
        result = run_agent(model.runnable, [add], "hi")
        assert (result.answer, result.model_calls) == ("hello", 1)

    def test_max_iterations_guard(self):
        model = ScriptedModel(*[ai_calls(call("add", {"a": 1, "b": 1}, f"c{i}")) for i in range(10)])
        with pytest.raises(MaxIterationsError):
            run_agent(model.runnable, [add], "loop forever", max_iterations=3)
        assert len(model.seen) == 3

    def test_with_fake_chat_model(self):
        model = FakeMessagesListChatModel(
            responses=[ai_calls(call("shout", {"text": "ok"}, "x")), AIMessage("It says OK")]
        )
        assert run_agent(model, [shout], "shout ok").answer == "It says OK"


class TestTask7AsyncAgent:
    async def test_round_trip(self):
        model = FakeMessagesListChatModel(
            responses=[ai_calls(call("add", {"a": 4, "b": 5}, "c1")), AIMessage("nine")]
        )
        result = await arun_agent(model, [add], "4+5?")
        assert result.answer == "nine"
        assert result.model_calls == 2
        assert [m.content for m in result.messages if isinstance(m, ToolMessage)] == ["9"]

    async def test_tool_calls_run_concurrently_and_keep_order(self):
        event = asyncio.Event()

        @tool
        async def wait_for_signal() -> str:
            """Wait until `send_signal` ran."""
            await asyncio.wait_for(event.wait(), timeout=1)
            return "got it"

        @tool
        async def send_signal() -> str:
            """Release `wait_for_signal`."""
            event.set()
            return "sent"

        model = ScriptedModel(
            ai_calls(call("wait_for_signal", {}, "w"), call("send_signal", {}, "s")),
            AIMessage("both done"),
        )
        result = await arun_agent(model.runnable, [wait_for_signal, send_signal], "go")
        tool_msgs = [m for m in result.messages if isinstance(m, ToolMessage)]
        assert [(m.tool_call_id, m.content) for m in tool_msgs] == [("w", "got it"), ("s", "sent")]

    async def test_unknown_tool_and_guard(self):
        model = ScriptedModel(*[ai_calls(call("nope", {}, f"c{i}")) for i in range(5)])
        with pytest.raises(MaxIterationsError):
            await arun_agent(model.runnable, [add], "q", max_iterations=2)
        second = model.seen[1]
        assert second[-1].content == "Error: unknown tool 'nope'"
        assert len(model.seen) == 2
