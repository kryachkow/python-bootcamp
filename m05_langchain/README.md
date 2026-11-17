# Module 5: LangChain (`langchain-core` 1.x)

This module covers the parts of LangChain that a production LLM backend is
actually built from: messages and prompt templates, LCEL pipelines, output
parsers, tools and a hand-written tool-calling loop, retrieval/RAG, and the
runtime concerns (streaming, per-session chat history, callbacks). Everything
uses `langchain-core` and `langchain-text-splitters` only, and every task
takes the model (or embeddings, or retriever) as a parameter, so the tests can
inject fakes and your application can inject a real provider.

## Prerequisites

- Module 1 (Python core). Module 2 (Pydantic) helps for exercises 5.3 and 5.4.
- Basic async/await for the `a*` tasks (`ainvoke`, `astream`, `abatch`).

## Exercises

| # | Exercise | Topics |
|---|----------|--------|
| 5.1 | [Prompts & messages](e01_prompts_and_messages/) | System/Human/AI/ToolMessage, `ChatPromptTemplate`, `MessagesPlaceholder`, partials, `PromptTemplate` brace escaping, few-shot, `trim_messages`, token budgets |
| 5.2 | [LCEL & runnables](e02_lcel_runnables/) | `\|`, `RunnableLambda`, `RunnableParallel`, `RunnablePassthrough.assign`, `RunnableBranch`, `with_fallbacks`, `with_retry`, `batch`/`abatch`, `RunnableConfig`, `with_config` |
| 5.3 | [Output parsers](e03_output_parsers/) | `StrOutputParser`, `JsonOutputParser` (incl. partial streaming), `PydanticOutputParser`, `CommaSeparatedListOutputParser`, custom `BaseOutputParser`, retry with error feedback |
| 5.4 | [Tools & tool calling](e04_tools_and_tool_calling/) | `@tool`, `StructuredTool.from_function` + `args_schema`, `convert_to_openai_tool`, ToolCall to ToolMessage, `handle_tool_error`, sync and async agent loops |
| 5.5 | [Retrieval & RAG](e05_retrieval_rag/) | `Document`, `RecursiveCharacterTextSplitter`, custom `Embeddings`/`VectorStore`, metadata filters, `as_retriever`, citations, RAG chains |
| 5.6 | [Streaming, history & callbacks](e06_streaming_history_callbacks/) | `stream`/`astream`, SSE frames, `astream_events`, per-session history, `BaseCallbackHandler`, callbacks/tags/metadata via config |

Recommended order: 5.1 → 5.2 → 5.3, then 5.4, 5.5 and 5.6 in any order (each
builds on LCEL from 5.2).

## Setup notes

None. **The tests need no API keys and no network.** They use the fakes that
ship with `langchain_core` (`GenericFakeChatModel`, `FakeListChatModel`,
`FakeMessagesListChatModel`, `FakeListLLM`) plus small spy models
(`RunnableLambda`s that record the prompt they receive). The whole module runs
in well under a second.

Exercise 5.5 brings its own pure-Python `HashingEmbeddings`, because
`DeterministicFakeEmbedding` and `InMemoryVectorStore` from `langchain_core`
require `numpy`, which this repo does not install.

## Using a real model

Nothing in the exercises imports a provider package. To try your solutions
against a real LLM, install one in your own environment (it is deliberately
not a dependency of this repo) and pass it in:

```python
# uv pip install langchain-openai
from langchain_openai import AzureChatOpenAI, ChatOpenAI, OpenAIEmbeddings

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)          # reads OPENAI_API_KEY
# llm = AzureChatOpenAI(azure_deployment="gpt-4o", api_version="2024-10-21")

from m05_langchain.e02_lcel_runnables.exercise import build_answer_chain
print(build_answer_chain(llm).invoke({"question": "What is LCEL?"}))
```

For the agent in 5.4, pass `llm.bind_tools(tools)`; for 5.5, pass
`OpenAIEmbeddings()` instead of `HashingEmbeddings()`.
