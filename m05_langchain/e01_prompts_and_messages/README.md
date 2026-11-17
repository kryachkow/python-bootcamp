# 5.1 Prompts & messages

Every chat-model call is a list of messages. In a backend that list is built
from a prompt template, the stored conversation, and the user's new input, and
it has to fit into the model's context window. This exercise covers the
message types, the templates that produce them, and how to trim history.

## Concepts

| Tool | Use it for |
|------|------------|
| `SystemMessage` / `HumanMessage` / `AIMessage` / `ToolMessage` | the four roles; `message.type` is `"system"`, `"human"`, `"ai"`, `"tool"` |
| `AIMessage.tool_calls` + `ToolMessage.tool_call_id` | a tool result must point at the call it answers |
| `ChatPromptTemplate.from_messages([...])` | `("system", "...{var}...")` tuples, placeholders, nested templates |
| `MessagesPlaceholder("history", optional=True)` | splice a list of messages (the conversation) into the prompt |
| `.partial(name="x", today=callable)` | pre-fill variables; a callable is evaluated on every format |
| `PromptTemplate.from_template` | plain-text prompts; write literal braces as `{{` and `}}` |
| `FewShotChatMessagePromptTemplate` | turn example dicts into human/AI message pairs |
| `trim_messages(..., strategy="last", include_system=True, start_on="human")` | keep the newest messages that fit a budget |

Common mistake: a history that starts with an `AIMessage` or an orphan
`ToolMessage` after trimming. Most providers reject it, so always cut at a
human turn.

## Tasks

All tasks are in [`exercise.py`](exercise.py).

| # | Task | What you practise |
|---|------|-------------------|
| 1 | `records_to_messages` | building each message type from DB rows, tool calls and tool-call ids |
| 2 | `messages_to_records` | `message.type`, serialising tool calls, round-tripping |
| 3 | `build_qa_prompt` | `ChatPromptTemplate.from_messages`, optional `MessagesPlaceholder` |
| 4 | `build_company_prompt` | `.partial` with values and callables |
| 5 | `build_extraction_prompt` | `PromptTemplate`, escaping literal JSON braces |
| 6 | `build_few_shot_prompt` | `FewShotChatMessagePromptTemplate` inside a chat prompt |
| 7 | `trim_history` | `trim_messages` with a message-count budget |
| 8 | `trim_to_token_budget` | writing a token-budget trimmer by hand |

## Run the tests

```bash
uv run pytest m05_langchain/e01_prompts_and_messages
uv run pytest m05_langchain/e01_prompts_and_messages -k Task4   # one task only
```

No API keys needed. Nothing here calls a model.

## Further reading

- [Messages](https://python.langchain.com/docs/concepts/messages/)
- [Prompt templates](https://python.langchain.com/docs/concepts/prompt_templates/)
- [How to trim messages](https://python.langchain.com/docs/how_to/trim_messages/)
