# 2.3 Serialization, aliases & JSON Schema

Validation is half of Pydantic. The other half is output: what your API
returns, what you put on a queue, what you send to an LLM. This exercise
covers the dump options, aliases for other people's naming conventions,
derived fields, custom serializers, and JSON Schema generation.

## Concepts

| Tool | Use it for |
|------|------------|
| `model_dump(mode="json")` / `model_dump_json()` | JSON-safe output: `UUID`, `datetime`, `Decimal` become strings |
| `exclude_none` / `exclude_unset` / `exclude_defaults` | drop `None` / fields not sent by the client (PATCH) / default values |
| `include=` / `exclude=` (nested, `"__all__"`) | pick or hide fields, also inside nested models and lists |
| `Field(alias=...)` | one external name for input and output |
| `Field(validation_alias=AliasChoices(...) \| AliasPath(...))` | accept several input names or a nested key |
| `Field(serialization_alias=...)` | output-only rename |
| `ConfigDict(alias_generator=to_camel, validate_by_name=True, serialize_by_alias=True)` | snake_case in Python, camelCase on the wire |
| `@computed_field` + `@property` | derived values in the output and the serialization schema |
| `@field_serializer("f", when_used=...)` | change how one field is written |
| `@model_serializer(mode="wrap" \| "plain")` | change the shape of the whole output (envelopes) |
| `Field(exclude=True)` | a field that is never serialized |
| `Model.model_json_schema(mode=...)` | JSON Schema for docs, OpenAPI, and LLM tool definitions |

Keys are renamed only when aliases are used for output: `by_alias=True`, or
`serialize_by_alias=True` in the config. FastAPI response models dump by
alias by default.

## Tasks

All tasks are in [`exercise.py`](exercise.py).

| # | Task | What you practise |
|---|------|-------------------|
| 1 | `to_json_dict` | `mode="json"`, `exclude_none` |
| 2 | `apply_patch` | `exclude_unset` for PATCH, `model_copy(update=...)` |
| 3 | `public_view` | nested `exclude`, `"__all__"` for lists |
| 4 | `ExternalUser` | `alias`, `validation_alias` (`AliasChoices`, `AliasPath`), `serialization_alias` |
| 5 | `CamelModel`, `ProductOut` | `alias_generator=to_camel`, `validate_by_name`, `serialize_by_alias` |
| 6 | `CartLine`, `Cart` | `@computed_field`, serialization vs validation schema |
| 7 | `Event` | `@field_serializer`, `when_used="json"`, stable output for sets |
| 8 | `ApiError` | `@model_serializer(mode="wrap")`, `Field(exclude=True)` |
| 9 | `tool_spec` | `model_json_schema()` as an LLM tool definition, `$defs` |

## Run the tests

```bash
uv run pytest m02_pydantic/e03_serialization
uv run pytest m02_pydantic/e03_serialization -k Task5   # one task only
```

## Further reading

- [Serialization](https://docs.pydantic.dev/latest/concepts/serialization/)
- [Alias](https://docs.pydantic.dev/latest/concepts/alias/)
- [JSON Schema](https://docs.pydantic.dev/latest/concepts/json_schema/)
