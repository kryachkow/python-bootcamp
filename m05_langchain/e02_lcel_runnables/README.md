# 5.2 LCEL & runnables

LCEL (LangChain Expression Language) composes `Runnable` objects with `|`.
Prompts, models, parsers, retrievers and plain functions are all runnables, so
they all have `invoke` / `batch` / `stream` and the async `ainvoke` / `abatch`
/ `astream`, and they can all be wrapped with retries, fallbacks and config.

## Concepts

| Tool | Use it for |
|------|------------|
| `a \| b \| c` | a `RunnableSequence`: the output of each step is the input of the next |
| `RunnableLambda(fn)` | wrap a function; give it a `config` parameter to receive the `RunnableConfig` |
| `{"a": r1, "b": r2}` / `RunnableParallel` | run branches on the same input and collect a dict |
| `RunnablePassthrough()` / `.assign(key=fn)` | pass the input through / add keys to a dict input |
| `RunnableBranch((cond, r), ..., default)` | routing; or a lambda that *returns* a runnable |
| `.with_fallbacks([backup], exceptions_to_handle=...)` | switch provider when the primary is down |
| `.with_retry(stop_after_attempt=..., retry_if_exception_type=...)` | retry transient errors |
| `.batch(inputs, config={"max_concurrency": n}, return_exceptions=True)` | many inputs, bounded concurrency, partial failures |
| `RunnableConfig`: `tags`, `metadata`, `configurable`, `callbacks`, `run_name` | per-request data and observability that flows to every nested step |
| `.with_config(run_name=..., tags=[...])` | bind config to a runnable |

## Tasks

All tasks are in [`exercise.py`](exercise.py). Every model is a parameter: the
tests pass `FakeListChatModel` or a `RunnableLambda` spy; your app passes
`ChatOpenAI(...)` / `AzureChatOpenAI(...)`.

| # | Task | What you practise |
|---|------|-------------------|
| 1 | `build_normalizer` | `\|` and `RunnableLambda` |
| 2 | `build_answer_chain` | `prompt \| model \| StrOutputParser()` |
| 3 | `build_analysis_chain` | `RunnableParallel` with dict syntax, `itemgetter` |
| 4 | `build_enrich_chain` | `RunnablePassthrough.assign`, chained assigns |
| 5 | `build_router` | `RunnableBranch` / dynamic routing |
| 6 | `with_backup` | `with_fallbacks` restricted to transient errors |
| 7 | `with_retries` | `with_retry`, which errors to retry |
| 8 | `run_batch` / `arun_batch` | `batch` / `abatch`, `max_concurrency`, `return_exceptions` |
| 9 | `build_personalized_chain` | reading `configurable` in a lambda, `with_config`, tag propagation |

## Run the tests

```bash
uv run pytest m05_langchain/e02_lcel_runnables
uv run pytest m05_langchain/e02_lcel_runnables -k Task6   # one task only
```

No API keys needed.

## Further reading

- [LCEL concepts](https://python.langchain.com/docs/concepts/lcel/)
- [Runnable interface](https://python.langchain.com/docs/concepts/runnables/)
- [How to add fallbacks](https://python.langchain.com/docs/how_to/fallbacks/)
