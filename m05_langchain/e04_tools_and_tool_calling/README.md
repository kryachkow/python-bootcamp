# 5.4 Tools & tool calling

A tool is a function with a name, a description and an argument schema. The
model never executes anything: it answers with `AIMessage.tool_calls`, your
code runs the tools, and sends each result back as a `ToolMessage` whose
`tool_call_id` matches the call. You repeat this until the model replies
without tool calls. That loop is the core of every agent framework; here you
write it yourself so you know exactly what LangGraph's prebuilt agents do.

## Concepts

| Tool | Use it for |
|------|------------|
| `@tool` / `@tool(parse_docstring=True)` | name from the function, description and arg docs from the docstring, schema from type hints |
| `StructuredTool.from_function(func, name, description, args_schema=Model)` | explicit Pydantic schema with `Field(description=..., ge=...)` validation |
| `tool.name` / `.description` / `.args` / `.tool_call_schema` | what the model sees |
| `convert_to_openai_tool(tool)` | the JSON spec `bind_tools` sends to the provider |
| `tool.invoke(tool_call)` | given a full ToolCall dict, returns a `ToolMessage` with the right id |
| `ToolException` + `handle_tool_error` / `handle_validation_error` | turn expected failures into messages the model can react to |
| `llm.bind_tools(tools)` | real providers only; the fake models here return scripted tool calls instead |

```
Human -> model -> AIMessage(tool_calls=[{id: "c1", ...}])
              -> run tool -> ToolMessage(tool_call_id="c1")
      -> model -> AIMessage("final answer")   (no tool_calls: stop)
```

## Tasks

All tasks are in [`exercise.py`](exercise.py). Tests drive the agent with
`FakeMessagesListChatModel` and a scripted `RunnableLambda` model that records
every message list it was sent.

| # | Task | What you practise |
|---|------|-------------------|
| 1 | `get_weather` | `@tool(parse_docstring=True)`, `Literal` args |
| 2 | `build_search_orders_tool` | `StructuredTool.from_function`, Pydantic `args_schema`, validation |
| 3 | `tool_specs` | `convert_to_openai_tool`, what the provider receives |
| 4 | `execute_tool_call` | ToolCall to `ToolMessage`, matching ids, unknown tools |
| 5 | `build_divide_tool` | `ToolException`, `handle_tool_error`, `handle_validation_error` |
| 6 | `run_agent` | the tool-calling loop with a `max_iterations` guard |
| 7 | `arun_agent` | async loop, parallel tool calls with `asyncio.gather` |

## Run the tests

```bash
uv run pytest m05_langchain/e04_tools_and_tool_calling
uv run pytest m05_langchain/e04_tools_and_tool_calling -k Task6   # one task only
```

No API keys needed. To run your agent for real:
`run_agent(ChatOpenAI(model="gpt-4o-mini").bind_tools(tools), tools, "...")`.

## Further reading

- [Tools](https://python.langchain.com/docs/concepts/tools/)
- [Tool calling](https://python.langchain.com/docs/concepts/tool_calling/)
