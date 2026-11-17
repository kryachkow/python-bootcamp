import pytest
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate

from m05_langchain.e01_prompts_and_messages.exercise import (
    SENTIMENT_SYSTEM,
    build_company_prompt,
    build_extraction_prompt,
    build_few_shot_prompt,
    build_qa_prompt,
    messages_to_records,
    records_to_messages,
    trim_history,
    trim_to_token_budget,
)


def _kinds(messages):
    return [(type(m).__name__, m.content) for m in messages]


@pytest.fixture
def conversation():
    return [
        SystemMessage("be brief"),
        HumanMessage("h1"),
        AIMessage("a1"),
        HumanMessage("h2"),
        AIMessage("a2"),
        HumanMessage("h3"),
    ]


class TestTask1RecordsToMessages:
    def test_maps_every_role(self):
        records = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "weather?"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [{"name": "weather", "args": {"city": "Kyiv"}, "id": "c1"}],
            },
            {"role": "tool", "content": "sunny", "tool_call_id": "c1"},
            {"role": "assistant", "content": "It is sunny."},
        ]
        msgs = records_to_messages(records)
        assert [type(m) for m in msgs] == [
            SystemMessage, HumanMessage, AIMessage, ToolMessage, AIMessage,
        ]
        assert msgs[2].tool_calls[0]["name"] == "weather"
        assert msgs[2].tool_calls[0]["args"] == {"city": "Kyiv"}
        assert msgs[3].tool_call_id == "c1"
        assert msgs[4].content == "It is sunny."

    def test_tool_without_call_id_raises(self):
        with pytest.raises(ValueError):
            records_to_messages([{"role": "tool", "content": "x"}])

    def test_unknown_role_raises(self):
        with pytest.raises(ValueError, match="moderator"):
            records_to_messages([{"role": "moderator", "content": "x"}])

    def test_empty(self):
        assert records_to_messages([]) == []


class TestTask2MessagesToRecords:
    def test_serialises_roles_and_extras(self):
        msgs = [
            SystemMessage("sys"),
            HumanMessage("hi"),
            AIMessage("", tool_calls=[{"name": "f", "args": {"x": 1}, "id": "c9"}]),
            ToolMessage("42", tool_call_id="c9"),
            AIMessage("done"),
        ]
        assert messages_to_records(msgs) == [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "", "tool_calls": [{"name": "f", "args": {"x": 1}, "id": "c9"}]},
            {"role": "tool", "content": "42", "tool_call_id": "c9"},
            {"role": "assistant", "content": "done"},
        ]

    def test_round_trip(self):
        records = [
            {"role": "user", "content": "q"},
            {"role": "assistant", "content": "", "tool_calls": [{"name": "t", "args": {}, "id": "1"}]},
            {"role": "tool", "content": "r", "tool_call_id": "1"},
        ]
        msgs = [HumanMessage("q"), AIMessage("", tool_calls=[{"name": "t", "args": {}, "id": "1"}]),
                ToolMessage("r", tool_call_id="1")]
        assert messages_to_records(msgs) == records
        assert messages_to_records(records_to_messages(records)) == records

    def test_rejects_chunks(self):
        with pytest.raises(ValueError):
            messages_to_records([AIMessageChunk("partial")])


class TestTask3BuildQaPrompt:
    def test_variables(self):
        prompt = build_qa_prompt()
        assert isinstance(prompt, ChatPromptTemplate)
        assert sorted(prompt.input_variables) == ["assistant_name", "company", "language", "question"]
        assert "history" in prompt.optional_variables

    def test_format_without_history(self):
        msgs = build_qa_prompt().format_messages(
            assistant_name="Ava", company="Acme", language="English", question="Where is my order?"
        )
        assert _kinds(msgs) == [
            ("SystemMessage", "You are Ava, a support assistant for Acme. Answer in English."),
            ("HumanMessage", "Where is my order?"),
        ]

    def test_history_goes_between_system_and_question(self):
        history = [HumanMessage("hi"), AIMessage("hello!")]
        msgs = build_qa_prompt().format_messages(
            assistant_name="Ava", company="Acme", language="German", question="next", history=history
        )
        assert _kinds(msgs)[1:] == [
            ("HumanMessage", "hi"), ("AIMessage", "hello!"), ("HumanMessage", "next"),
        ]


class TestTask4BuildCompanyPrompt:
    def test_only_question_left(self):
        prompt = build_company_prompt("Acme", lambda: "English")
        assert prompt.input_variables == ["question"]

    def test_values_are_filled(self):
        msgs = build_company_prompt("Globex", lambda: "French", assistant_name="Max").format_messages(
            question="q"
        )
        assert msgs[0].content == "You are Max, a support assistant for Globex. Answer in French."

    def test_language_is_evaluated_on_every_format(self):
        languages = iter(["English", "Ukrainian"])
        prompt = build_company_prompt("Acme", lambda: next(languages))
        first = prompt.format_messages(question="q")[0].content
        second = prompt.format_messages(question="q")[0].content
        assert first.endswith("Answer in English.")
        assert second.endswith("Answer in Ukrainian.")


class TestTask5BuildExtractionPrompt:
    def test_formats_exactly(self):
        prompt = build_extraction_prompt()
        assert isinstance(prompt, PromptTemplate)
        assert prompt.format(text="Bob is 42") == (
            "Extract the person from the text below.\n"
            'Reply with JSON like {"name": "Alice", "age": 30}.\n'
            "\n"
            "Text: Bob is 42"
        )

    def test_only_text_variable(self):
        assert build_extraction_prompt().input_variables == ["text"]

    def test_missing_variable_raises(self):
        with pytest.raises(KeyError):
            build_extraction_prompt().format()


class TestTask6FewShotPrompt:
    EXAMPLES = [
        {"input": "I love it", "output": "positive"},
        {"input": "It broke after a day", "output": "negative"},
    ]

    def test_examples_become_message_pairs(self):
        msgs = build_few_shot_prompt(self.EXAMPLES).format_messages(input="It is fine")
        assert _kinds(msgs) == [
            ("SystemMessage", SENTIMENT_SYSTEM),
            ("HumanMessage", "I love it"),
            ("AIMessage", "positive"),
            ("HumanMessage", "It broke after a day"),
            ("AIMessage", "negative"),
            ("HumanMessage", "It is fine"),
        ]

    def test_no_examples(self):
        msgs = build_few_shot_prompt([]).format_messages(input="meh")
        assert _kinds(msgs) == [("SystemMessage", SENTIMENT_SYSTEM), ("HumanMessage", "meh")]

    def test_only_input_variable(self):
        assert build_few_shot_prompt(self.EXAMPLES).input_variables == ["input"]


class TestTask7TrimHistory:
    def test_keeps_system_and_latest(self, conversation):
        assert _kinds(trim_history(conversation, 4)) == [
            ("SystemMessage", "be brief"),
            ("HumanMessage", "h2"),
            ("AIMessage", "a2"),
            ("HumanMessage", "h3"),
        ]

    def test_starts_on_human(self, conversation):
        # 3 slots: system + last two would be [a2, h3] -> leading AI dropped
        assert _kinds(trim_history(conversation, 3)) == [
            ("SystemMessage", "be brief"),
            ("HumanMessage", "h3"),
        ]

    def test_no_trim_needed(self, conversation):
        assert trim_history(conversation, 100) == conversation

    def test_invalid_max_raises(self, conversation):
        with pytest.raises(ValueError):
            trim_history(conversation, 0)


class TestTask8TrimToTokenBudget:
    @staticmethod
    def words(text):
        return len(text.split())

    def test_docstring_example(self):
        msgs = [SystemMessage("be brief"), HumanMessage("a b"), AIMessage("c d"),
                HumanMessage("e f"), AIMessage("g")]
        assert _kinds(trim_to_token_budget(msgs, 6, self.words)) == [
            ("SystemMessage", "be brief"), ("HumanMessage", "e f"), ("AIMessage", "g"),
        ]

    def test_stops_at_first_message_that_does_not_fit(self):
        msgs = [HumanMessage("one"), AIMessage("a very long answer here"), HumanMessage("two words")]
        # "two words" (2) fits in 3, the long AI message does not -> stop, even though "one" would fit
        assert _kinds(trim_to_token_budget(msgs, 3, self.words)) == [("HumanMessage", "two words")]

    def test_drops_leading_tool_and_ai_messages(self):
        msgs = [
            HumanMessage("weather in Kyiv please"),
            AIMessage("", tool_calls=[{"name": "w", "args": {}, "id": "1"}]),
            ToolMessage("sunny", tool_call_id="1"),
            AIMessage("it is sunny"),
        ]
        # budget fits the tool + final AI message but not the human question -> nothing valid left
        assert trim_to_token_budget(msgs, 4, self.words) == []

    def test_system_over_budget_raises(self):
        with pytest.raises(ValueError):
            trim_to_token_budget([SystemMessage("one two three")], 2, self.words)

    def test_everything_fits_unchanged(self):
        msgs = [SystemMessage("s"), HumanMessage("h"), AIMessage("a")]
        assert trim_to_token_budget(msgs, 10, self.words) == msgs
