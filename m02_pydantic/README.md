# Module 2: Pydantic v2

Pydantic is the contract layer of a modern Python backend: FastAPI request
and response bodies, structured LLM output, tool-call arguments, message
payloads, and application settings are all Pydantic models. This module goes
from the basics of `BaseModel` through validators, serialization, and
advanced types (discriminated unions, generics, custom types) to
`pydantic-settings`. Everything uses the v2 API; the deprecated v1 names
(`@validator`, `.dict()`, `parse_obj`, `class Config`) do not appear.

## Prerequisites

- Python type hints: `list[str]`, `X | None`, `Annotated`, `Literal`, generics
  (`class Box[T]`).
- [Module 1](../m01_python_core) helps but is not required.

## Exercises

| # | Exercise | Topics |
|---|----------|--------|
| 2.1 | [Model basics](e01_models_basics) | fields, defaults, `default_factory`, lax vs strict, nested models, `model_validate(_json)`, `ValidationError.errors()`, `model_copy` |
| 2.2 | [Fields & validators](e02_fields_and_validators) | `Field` constraints, `Annotated` validators, `@field_validator`, `@model_validator` (before/after), `ConfigDict` (`extra`, `frozen`, `str_strip_whitespace`, `validate_assignment`) |
| 2.3 | [Serialization](e03_serialization) | `model_dump(mode="json")`, `include`/`exclude`/`exclude_unset`, aliases, `alias_generator`, `computed_field`, `field_serializer`, `model_serializer`, JSON Schema |
| 2.4 | [Advanced types](e04_advanced_types) | enums, discriminated unions, generic models, `TypeAdapter`, `RootModel`, recursive models, custom types |
| 2.5 | [Settings](e05_settings) | `BaseSettings`, `env_prefix`, nested config, `SecretStr`, `.env` files, validation, cached `get_settings()` |

## Recommended order

Do the exercises in order, 2.1 to 2.5. Each one assumes the previous ones,
but its code is self-contained. Inside an exercise, the tasks go from easy to
harder, and a few later tasks reuse a model from an earlier task in the same
file (the docstring says so).

## Run the tests

```bash
uv run pytest m02_pydantic                       # the whole module
uv run pytest m02_pydantic/e03_serialization     # one exercise
uv run pytest m02_pydantic/e03_serialization -k Task4
```

## Setup notes

None. `pydantic` and `pydantic-settings` are in the project dependencies.
The settings tests (2.5) only use variables prefixed `BCAMP05_` and run in a
temporary directory, so your shell environment and `.env` files do not matter.
