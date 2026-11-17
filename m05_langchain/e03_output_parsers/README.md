# 5.3 Output parsers

Models return text. Output parsers turn it into the types your code needs,
tell the model which format to use (`get_format_instructions()`), and raise
`OutputParserException` when the reply does not match, so you can retry or
fail cleanly instead of passing garbage downstream.

## Concepts

| Parser | Output | Notes |
|--------|--------|-------|
| `StrOutputParser` | `str` | streams token by token; use it instead of `lambda m: m.content` |
| `JsonOutputParser` | `dict` / `list` | handles code fences; streams *partial* objects |
| `PydanticOutputParser(pydantic_object=M)` | `M` | format instructions embed `M`'s JSON schema; validation errors become `OutputParserException` |
| `CommaSeparatedListOutputParser` | `list[str]` | simple tag/keyword lists |
| subclass `BaseOutputParser[T]` | `T` | implement `parse`, `get_format_instructions`, `_type` |

In production, prefer the provider's native structured output
(`llm.with_structured_output(Model)`) when it exists. Parsers are still what
you use for providers without it, for streaming partial JSON, and for custom
text formats, and they are how `with_structured_output` works underneath.

## Tasks

All tasks are in [`exercise.py`](exercise.py).

| # | Task | What you practise |
|---|------|-------------------|
| 1 | `build_summary_chain` | `StrOutputParser`, streaming through a parser |
| 2 | `parse_json_reply` | `JsonOutputParser.parse`, fenced JSON, `OutputParserException` |
| 3 | `build_tags_chain` | format instructions via `.partial`, post-processing a list |
| 4 | `build_invoice_chain` | `PydanticOutputParser`, schema in the prompt, validation errors |
| 5 | `stream_json_progress` | streaming partial JSON objects |
| 6 | `AnswerWithConfidenceParser` | writing a `BaseOutputParser` subclass |
| 7 | `ask_with_retry` | parse, or retry once with the error fed back to the model |

## Run the tests

```bash
uv run pytest m05_langchain/e03_output_parsers
uv run pytest m05_langchain/e03_output_parsers -k Task7   # one task only
```

No API keys needed.

## Further reading

- [Output parsers](https://python.langchain.com/docs/concepts/output_parsers/)
- [Structured outputs](https://python.langchain.com/docs/concepts/structured_outputs/)
