# 5.6 Streaming, chat history & callbacks

Runtime concerns of an LLM backend: stream tokens to the client as they are
generated, remember each user's conversation, and observe model calls for
metrics, logging and tracing.

## Concepts

| Tool | Use it for |
|------|------------|
| `chain.stream(...)` / `chain.astream(...)` | token chunks through the whole chain (parsers must be streaming-aware) |
| SSE frames `data: ...\n\n` | what a FastAPI `StreamingResponse(media_type="text/event-stream")` sends |
| `chain.astream_events(..., version="v2")` | every step's events; filter `on_chat_model_stream` by `tags` / `name` |
| per-session history | `dict[session_id, list[BaseMessage]]` (Redis/DB in production) + `MessagesPlaceholder` |
| `config={"configurable": {"session_id": ...}}` | pass the session through the config, as LangChain's own APIs do |
| `BaseCallbackHandler` | `on_chat_model_start`, `on_llm_start`, `on_llm_new_token`, `on_llm_end`, `on_llm_error`, `on_chain_start`, ... |
| `config={"callbacks": [...], "tags": [...], "metadata": {...}}` | request-scoped observability that reaches every nested step |

**Deprecation note:** in `langchain-core` 1.x, `RunnableWithMessageHistory` and
`InMemoryChatMessageHistory` emit `LangChainDeprecationWarning`s (LangChain now
recommends LangGraph persistence). This exercise therefore manages history
explicitly: a small `SessionStore` and a chain that loads/saves around the
model call. It is the same mechanism, with no hidden magic.

## Tasks

All tasks are in [`exercise.py`](exercise.py). `GenericFakeChatModel` streams
its reply word by word (spaces are separate chunks), and
`FakeListChatModel(error_on_chunk_number=n)` fails mid-stream.

| # | Task | What you practise |
|---|------|-------------------|
| 1 | `stream_answer` | `.stream` through `prompt \| model \| StrOutputParser()` |
| 2 | `astream_sse` | `.astream`, SSE framing, errors after the response started |
| 3 | `stream_tokens_from_tagged_model` | `astream_events` v2, filtering by event type and tag |
| 4 | `SessionStore` | per-session history with a size cap, defensive copies |
| 5 | `build_chat_with_history` | `session_id` from `configurable`, history in the prompt |
| 6 | `TokenCountingHandler` | a custom `BaseCallbackHandler` |
| 7 | `invoke_traced` | callbacks, tags, metadata and `run_name` via `RunnableConfig` |

## Run the tests

```bash
uv run pytest m05_langchain/e06_streaming_history_callbacks
uv run pytest m05_langchain/e06_streaming_history_callbacks -k Task5   # one task only
```

No API keys needed.

## Further reading

- [Streaming](https://python.langchain.com/docs/concepts/streaming/)
- [Callbacks](https://python.langchain.com/docs/concepts/callbacks/)
- [Short-term memory (LangChain docs)](https://docs.langchain.com/oss/python/langchain/short-term-memory)
