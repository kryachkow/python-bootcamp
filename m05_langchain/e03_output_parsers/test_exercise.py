import pytest
from langchain_core.exceptions import OutputParserException
from langchain_core.language_models.fake_chat_models import (
    FakeListChatModel,
    GenericFakeChatModel,
)
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.output_parsers import BaseOutputParser, CommaSeparatedListOutputParser
from langchain_core.runnables import RunnableLambda

from m05_langchain.e03_output_parsers.exercise import (
    RETRY_FEEDBACK,
    SUMMARY_SYSTEM,
    AnswerWithConfidence,
    AnswerWithConfidenceParser,
    Invoice,
    ask_with_retry,
    build_invoice_chain,
    build_summary_chain,
    build_tags_chain,
    parse_json_reply,
    stream_json_progress,
)


class SpyModel:
    """RunnableLambda-based fake model: returns scripted replies, records the prompts."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []  # list[list[BaseMessage]]

        def _call(prompt):
            messages = prompt.to_messages() if hasattr(prompt, "to_messages") else list(prompt)
            self.calls.append(messages)
            return AIMessage(self.replies[len(self.calls) - 1])

        self.runnable = RunnableLambda(_call)

    def invoke(self, messages):  # so it can be used directly as a "model"
        return self.runnable.invoke(messages)


class TestTask1SummaryChain:
    def test_invoke_returns_str(self):
        chain = build_summary_chain(FakeListChatModel(responses=["Short summary."]))
        assert chain.invoke({"text": "long text"}) == "Short summary."

    def test_prompt(self):
        spy = SpyModel("x")
        build_summary_chain(spy.runnable).invoke({"text": "the text"})
        assert [(m.type, m.content) for m in spy.calls[0]] == [
            ("system", SUMMARY_SYSTEM), ("human", "the text"),
        ]

    def test_stream_yields_string_tokens(self):
        model = GenericFakeChatModel(messages=iter(["the quick brown fox"]))
        chunks = list(build_summary_chain(model).stream({"text": "t"}))
        assert len(chunks) > 1
        assert all(isinstance(c, str) for c in chunks)
        assert "".join(chunks) == "the quick brown fox"


class TestTask2ParseJsonReply:
    def test_plain_json(self):
        assert parse_json_reply('{"a": 1, "b": [true, null]}') == {"a": 1, "b": [True, None]}

    def test_fenced_json(self):
        assert parse_json_reply('Sure!\n```json\n{"city": "Kyiv"}\n```') == {"city": "Kyiv"}

    def test_garbage_raises(self):
        with pytest.raises(OutputParserException):
            parse_json_reply("I cannot answer that.")


class TestTask3TagsChain:
    def test_normalises_tags(self):
        chain = build_tags_chain(FakeListChatModel(responses=["Billing, refund ,BILLING, "]))
        assert chain.invoke({"ticket": "I want my money back"}) == ["billing", "refund"]

    def test_format_instructions_in_prompt(self):
        spy = SpyModel("a, b")
        build_tags_chain(spy.runnable).invoke({"ticket": "my ticket"})
        system, human = spy.calls[0]
        instructions = CommaSeparatedListOutputParser().get_format_instructions()
        assert system.content == f"Suggest tags for the support ticket.\n{instructions}"
        assert human.content == "my ticket"

    def test_only_ticket_is_required(self):
        chain = build_tags_chain(FakeListChatModel(responses=["x"]))
        assert chain.input_schema.model_json_schema()["required"] == ["ticket"]


class TestTask4InvoiceChain:
    GOOD = '{"vendor": "Acme GmbH", "total": 120.5, "currency": "EUR", "due_date": "2026-12-01"}'

    def test_returns_invoice(self):
        chain = build_invoice_chain(FakeListChatModel(responses=[self.GOOD]))
        invoice = chain.invoke({"email": "Invoice from Acme..."})
        assert invoice == Invoice(vendor="Acme GmbH", total=120.5, currency="EUR", due_date="2026-12-01")

    def test_format_instructions_contain_schema(self):
        spy = SpyModel(self.GOOD)
        build_invoice_chain(spy.runnable).invoke({"email": "mail body"})
        system, human = spy.calls[0]
        assert system.content.startswith("Extract the invoice data from the e-mail.\n")
        assert "ISO 4217 code" in system.content  # field description from the schema
        assert '"vendor"' in system.content
        assert human.content == "mail body"

    def test_validation_error_becomes_parser_exception(self):
        bad = '{"vendor": "Acme", "total": -5, "currency": "EUR"}'
        with pytest.raises(OutputParserException):
            build_invoice_chain(FakeListChatModel(responses=[bad])).invoke({"email": "x"})

    def test_non_json_raises(self):
        with pytest.raises(OutputParserException):
            build_invoice_chain(FakeListChatModel(responses=["no idea"])).invoke({"email": "x"})


class TestTask5StreamJsonProgress:
    def test_yields_growing_dicts(self):
        model = GenericFakeChatModel(messages=iter(['{"city": "Kyiv", "temp": 21, "tags": ["sunny"]}']))
        snapshots = list(stream_json_progress(model, "weather?"))
        assert len(snapshots) > 2
        assert all(isinstance(s, dict) for s in snapshots)
        assert snapshots[-1] == {"city": "Kyiv", "temp": 21, "tags": ["sunny"]}
        # keys only ever get added
        for earlier, later in zip(snapshots, snapshots[1:]):
            assert set(earlier) <= set(later)

    def test_sees_partial_state(self):
        model = GenericFakeChatModel(messages=iter(['{"a": 1, "b": 2}']))
        snapshots = list(stream_json_progress(model, "q"))
        assert {"a": 1} in snapshots


class TestTask6AnswerWithConfidenceParser:
    @staticmethod
    def _parser():
        return AnswerWithConfidenceParser()

    def test_basic(self):
        parser = self._parser()
        assert parser.parse("Answer: Paris\nConfidence: 0.9") == AnswerWithConfidence(
            answer="Paris", confidence=0.9
        )

    def test_case_preamble_multiline_and_percent(self):
        parser = self._parser()
        text = "Let me think.\nANSWER:  Line one\nline two \n  confidence: 85%"
        result = parser.parse(text)
        assert result.answer == "Line one\nline two"
        assert result.confidence == pytest.approx(0.85)

    @pytest.mark.parametrize(
        "text",
        [
            "Paris",                              # no labels
            "Answer: Paris",                      # no confidence
            "Answer: \nConfidence: 0.5",          # empty answer
            "Answer: Paris\nConfidence: high",    # not a number
            "Answer: Paris\nConfidence: 1.5",     # out of range
        ],
    )
    def test_invalid_raises(self, text):
        parser = self._parser()
        with pytest.raises(OutputParserException):
            parser.parse(text)

    def test_format_instructions_and_type(self):
        parser = self._parser()
        instructions = parser.get_format_instructions()
        assert "Answer:" in instructions and "Confidence:" in instructions
        assert parser._type == "answer_with_confidence"

    def test_works_in_a_chain(self):
        parser = self._parser()
        chain = FakeListChatModel(responses=["Answer: 4\nConfidence: 1"]) | parser
        assert chain.invoke("2+2?") == AnswerWithConfidence(answer="4", confidence=1.0)


class _StrictIntParser(BaseOutputParser[int]):
    """Test helper: accepts only an integer reply."""

    def parse(self, text):
        try:
            return int(text.strip())
        except ValueError:
            raise OutputParserException(f"not an int: {text!r}") from None


class TestTask7AskWithRetry:
    MESSAGES = [SystemMessage("Reply with an integer."), HumanMessage("2+2?")]

    def test_first_reply_ok_calls_once(self):
        spy = SpyModel("4")
        assert ask_with_retry(spy, list(self.MESSAGES), _StrictIntParser()) == 4
        assert len(spy.calls) == 1

    def test_retries_with_error_feedback(self):
        spy = SpyModel("four", "4")
        messages = list(self.MESSAGES)
        assert ask_with_retry(spy, messages, _StrictIntParser()) == 4
        assert len(spy.calls) == 2
        second = spy.calls[1]
        assert second[:2] == self.MESSAGES
        assert isinstance(second[2], AIMessage) and second[2].content == "four"
        assert isinstance(second[3], HumanMessage)
        assert second[3].content.startswith("Your previous reply could not be parsed: ")
        assert "not an int: 'four'" in second[3].content
        assert second[3].content.endswith(RETRY_FEEDBACK.split("\n")[1])
        assert messages == self.MESSAGES  # not mutated

    def test_gives_up_after_one_retry(self):
        spy = SpyModel("four", "still four", "4")
        with pytest.raises(OutputParserException):
            ask_with_retry(spy, list(self.MESSAGES), _StrictIntParser())
        assert len(spy.calls) == 2

    def test_works_with_a_real_fake_chat_model(self):
        model = FakeListChatModel(responses=["dunno", " 4 "])
        assert ask_with_retry(model, list(self.MESSAGES), _StrictIntParser()) == 4
