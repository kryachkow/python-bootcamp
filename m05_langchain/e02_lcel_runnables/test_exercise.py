import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda, RunnableParallel, RunnableSequence

from m05_langchain.e02_lcel_runnables.exercise import (
    ANSWER_SYSTEM,
    arun_batch,
    build_analysis_chain,
    build_answer_chain,
    build_enrich_chain,
    build_normalizer,
    build_personalized_chain,
    build_router,
    run_batch,
    with_backup,
    with_retries,
)


class SpyModel:
    """A fake chat model built from a RunnableLambda that records every call."""

    def __init__(self, reply="ok"):
        self.reply = reply
        self.prompts = []  # list[list[BaseMessage]]
        self.configs = []

        def _call(prompt_value, config):
            self.prompts.append(prompt_value.to_messages())
            self.configs.append(config)
            return AIMessage(self.reply)

        self.runnable = RunnableLambda(_call)


class Flaky:
    """Callable that raises ``error`` for the first ``failures`` calls."""

    def __init__(self, failures, error=ConnectionError("down"), result="done"):
        self.failures, self.error, self.result, self.calls = failures, error, result, 0

    def __call__(self, x):
        self.calls += 1
        if self.calls <= self.failures:
            raise self.error
        return self.result


class TestTask1Normalizer:
    def test_cleans_input(self):
        assert build_normalizer().invoke("  Hello \n\t WORLD  again ") == "hello world again"

    def test_is_three_step_sequence(self):
        chain = build_normalizer()
        assert isinstance(chain, RunnableSequence)
        assert len(chain.steps) == 3

    def test_batch_works_too(self):
        assert build_normalizer().batch(["A  B", " c "]) == ["a b", "c"]


class TestTask2AnswerChain:
    def test_returns_string(self):
        chain = build_answer_chain(FakeListChatModel(responses=["Paris."]))
        out = chain.invoke({"question": "Capital of France?"})
        assert out == "Paris."
        assert isinstance(out, str)

    def test_prompt_reaching_the_model(self):
        spy = SpyModel()
        build_answer_chain(spy.runnable).invoke({"question": "Why is the sky blue?"})
        [messages] = spy.prompts
        assert [(m.type, m.content) for m in messages] == [
            ("system", ANSWER_SYSTEM),
            ("human", "Why is the sky blue?"),
        ]

    def test_missing_question_raises(self):
        with pytest.raises(KeyError):
            build_answer_chain(FakeListChatModel(responses=["x"])).invoke({})


class TestTask3AnalysisChain:
    def test_collects_all_branches(self):
        chain = build_analysis_chain(FakeListChatModel(responses=["42."]))
        assert chain.invoke({"question": "what is the answer"}) == {
            "question": "what is the answer",
            "answer": "42.",
            "word_count": 4,
        }

    def test_is_parallel(self):
        chain = build_analysis_chain(FakeListChatModel(responses=["x"]))
        parallel = chain if isinstance(chain, RunnableParallel) else chain.first
        assert isinstance(parallel, RunnableParallel)
        assert set(parallel.steps__) == {"question", "answer", "word_count"}


class TestTask4EnrichChain:
    def test_adds_keys_and_keeps_existing(self):
        chain = build_enrich_chain(lambda q: [f"doc about {q}", "second"])
        inp = {"question": "cats", "user_id": 7}
        out = chain.invoke(inp)
        assert out == {
            "question": "cats",
            "user_id": 7,
            "snippets": ["doc about cats", "second"],
            "context": "doc about cats\nsecond",
        }
        assert inp == {"question": "cats", "user_id": 7}

    def test_retrieve_called_once(self):
        calls = []
        chain = build_enrich_chain(lambda q: calls.append(q) or ["x"])
        chain.invoke({"question": "q"})
        assert calls == ["q"]

    def test_no_snippets(self):
        out = build_enrich_chain(lambda q: []).invoke({"question": "q"})
        assert out["context"] == ""


class TestTask5Router:
    @staticmethod
    def _router():
        return build_router(
            {
                "billing": RunnableLambda(lambda x: f"billing:{x['q']}"),
                "tech": RunnableLambda(lambda x: f"tech:{x['q']}"),
            },
            default=RunnableLambda(lambda x: f"general:{x['q']}"),
        )

    def test_routes_by_topic(self):
        router = self._router()
        assert router.invoke({"topic": "billing", "q": "refund"}) == "billing:refund"
        assert router.invoke({"topic": "tech", "q": "500 error"}) == "tech:500 error"

    def test_case_and_whitespace_insensitive(self):
        router = self._router()
        assert router.invoke({"topic": "  TECH ", "q": "x"}) == "tech:x"

    def test_unknown_or_missing_topic_goes_to_default(self):
        router = self._router()
        assert router.invoke({"topic": "sales", "q": "x"}) == "general:x"
        assert router.invoke({"q": "y"}) == "general:y"

    def test_branch_receives_whole_input(self):
        seen = []
        router = build_router({"a": RunnableLambda(lambda x: seen.append(x) or "ok")},
                              default=RunnableLambda(lambda x: "default"))
        router.invoke({"topic": "a", "extra": 1})
        assert seen == [{"topic": "a", "extra": 1}]


class TestTask6WithBackup:
    def test_falls_back_on_timeout(self):
        primary = RunnableLambda(Flaky(failures=99, error=TimeoutError("slow")))
        backup = FakeListChatModel(responses=["from backup"])
        assert with_backup(primary, backup).invoke("hi").content == "from backup"

    def test_falls_back_on_connection_error(self):
        primary = RunnableLambda(Flaky(failures=99))
        assert with_backup(primary, RunnableLambda(lambda x: "b")).invoke("x") == "b"

    def test_other_errors_propagate_without_backup(self):
        backup_calls = []
        primary = RunnableLambda(Flaky(failures=99, error=ValueError("bad input")))
        backup = RunnableLambda(lambda x: backup_calls.append(x) or "b")
        with pytest.raises(ValueError, match="bad input"):
            with_backup(primary, backup).invoke("x")
        assert backup_calls == []

    def test_primary_success_skips_backup(self):
        chain = with_backup(RunnableLambda(lambda x: "primary"), RunnableLambda(lambda x: 1 / 0))
        assert chain.invoke("x") == "primary"


class TestTask7WithRetries:
    def test_succeeds_after_transient_failures(self):
        flaky = Flaky(failures=2)
        assert with_retries(RunnableLambda(flaky), attempts=3).invoke("x") == "done"
        assert flaky.calls == 3

    def test_gives_up_after_attempts(self):
        flaky = Flaky(failures=5)
        with pytest.raises(ConnectionError):
            with_retries(RunnableLambda(flaky), attempts=2).invoke("x")
        assert flaky.calls == 2

    def test_does_not_retry_other_errors(self):
        flaky = Flaky(failures=5, error=ValueError("nope"))
        with pytest.raises(ValueError):
            with_retries(RunnableLambda(flaky), attempts=4).invoke("x")
        assert flaky.calls == 1

    def test_invalid_attempts(self):
        with pytest.raises(ValueError):
            with_retries(RunnableLambda(lambda x: x), attempts=0)


def _maybe_fail(x):
    if x < 0:
        raise ValueError(f"negative: {x}")
    return x * 10


class TestTask8Batch:
    def test_all_succeed(self):
        assert run_batch(RunnableLambda(_maybe_fail), [1, 2, 3]) == ([10, 20, 30], {})

    def test_partial_failures(self):
        results, errors = run_batch(RunnableLambda(_maybe_fail), [1, -2, 3, -4], max_concurrency=2)
        assert results == [10, None, 30, None]
        assert errors == {1: "negative: -2", 3: "negative: -4"}

    def test_respects_max_concurrency(self):
        seen = []
        chain = RunnableLambda(lambda x, config: seen.append(config.get("max_concurrency")) or x)
        run_batch(chain, [1, 2], max_concurrency=1)
        assert seen == [1, 1]

    async def test_async_version(self):
        results, errors = await arun_batch(RunnableLambda(_maybe_fail), [-1, 5])
        assert results == [None, 50]
        assert errors == {0: "negative: -1"}


class TestTask9PersonalizedChain:
    def test_user_name_from_configurable(self):
        spy = SpyModel(reply="Hi Olena!")
        chain = build_personalized_chain(spy.runnable)
        out = chain.invoke({"question": "hello"}, config={"configurable": {"user_name": "Olena"}})
        assert out == "Hi Olena!"
        system, human = spy.prompts[0]
        assert system.content == "You are talking to Olena. Address them by name."
        assert human.content == "hello"

    def test_default_user(self):
        spy = SpyModel()
        build_personalized_chain(spy.runnable).invoke({"question": "q"})
        assert spy.prompts[0][0].content == "You are talking to guest. Address them by name."

    def test_run_name_and_tag_on_the_chain(self):
        chain = build_personalized_chain(SpyModel().runnable)
        assert chain.config["run_name"] == "personalized_chain"
        assert chain.config["tags"] == ["personalized"]

    def test_tags_reach_the_model_merged_with_callers(self):
        spy = SpyModel()
        build_personalized_chain(spy.runnable).invoke(
            {"question": "q"}, config={"tags": ["request-123"], "metadata": {"tenant": "acme"}}
        )
        config = spy.configs[0]
        assert {"personalized", "request-123"} <= set(config["tags"])
        assert config["metadata"]["tenant"] == "acme"
