# 2.4 Advanced types

Real payloads are rarely flat: an LLM stream mixes text and tool calls, list
endpoints wrap items in a page, and some values (money, versions) deserve a
type of their own. This exercise covers the Pydantic features for those
shapes.

## Concepts

| Tool | Use it for |
|------|------------|
| `StrEnum` / `IntEnum` fields | closed sets of values; input `"paid"` becomes a member, error type `enum` |
| `Annotated[A \| B \| C, Field(discriminator="type")]` | tagged unions: pick the model by a `Literal` tag; fast, clear errors |
| `class Page[T](BaseModel)` | generic models: `Page[User]`, `ApiResponse[list[Item]]` |
| `TypeAdapter(list[Model])` | `validate_python` / `validate_json` / `dump_json` for any type that is not a model |
| `RootModel[list[str]]` | a model whose JSON is a bare array or value, not an object |
| `children: list[Category]` | recursive (self-referencing) models such as trees |
| `Annotated[int, BeforeValidator, PlainSerializer, WithJsonSchema]` | a custom type built from parts, reusable in any model |
| `__get_pydantic_core_schema__` | full control for your own classes, through `pydantic_core.core_schema` |

Without a discriminator, Pydantic tries every union member ("smart mode")
and reports errors for all of them. With one, it validates against exactly
one model, and the error `loc` includes the tag:
`("events", 1, "tool_call", "name")`.

## Tasks

All tasks are in [`exercise.py`](exercise.py).

| # | Task | What you practise |
|---|------|-------------------|
| 1 | `Shipment` | `StrEnum`/`IntEnum` fields, a small state machine |
| 2 | `TextChunk`, `ToolCall`, `ErrorEvent`, `StreamEvent`, `AgentTurn` | discriminated union with `Literal` tags |
| 3 | `Page[T]`, `paginate` | generic model, computed fields |
| 4 | `ApiResponse[T]` | generic model + model validator + `Self` classmethods |
| 5 | `parse_events`, `dump_events`, `parse_stock` | module-level `TypeAdapter`s |
| 6 | `Tags` | `RootModel`, validators on `root`, container dunder methods |
| 7 | `Category` | recursive model, tree traversal, nested error paths |
| 8 | `MoneyCents` | `Annotated` custom type: `BeforeValidator`, `PlainSerializer`, `WithJsonSchema` |
| 9 | `SemVer.__get_pydantic_core_schema__` | `core_schema.json_or_python_schema`, `chain_schema`, custom serialization |

## Run the tests

```bash
uv run pytest m02_pydantic/e04_advanced_types
uv run pytest m02_pydantic/e04_advanced_types -k Task2   # one task only
```

## Further reading

- [Unions and discriminated unions](https://docs.pydantic.dev/latest/concepts/unions/)
- [Generic models](https://docs.pydantic.dev/latest/concepts/models/#generic-models) and [TypeAdapter](https://docs.pydantic.dev/latest/concepts/type_adapter/)
- [Custom types](https://docs.pydantic.dev/latest/concepts/types/#custom-types)
