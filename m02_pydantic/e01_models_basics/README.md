# 2.1 Model basics

Every request body, LLM output and config object in a FastAPI service goes
through a `BaseModel`. This exercise covers the core of Pydantic v2: how you
declare fields, how input is coerced or rejected, how nested data is
validated, and how you read the errors when it fails.

## Concepts

| Tool | Use it for |
|------|------------|
| `name: str`, `x: int = 0`, `note: str \| None = None` | required field, default, optional field |
| `Field(default_factory=list)` | a fresh default per instance (lists, `uuid4`, `datetime.now`) |
| lax mode (default) | `"7"` -> `7`, `"yes"` -> `True`: friendly for query strings and forms |
| `ConfigDict(strict=True)` / `Field(strict=True)` | no coercion at all: money, IDs, flags |
| nested models, `list[Model]` | dicts are validated into models; errors carry the full `loc` path |
| `Model.model_validate(obj)` / `Model.model_validate_json(raw)` | validate a dict / a JSON string or bytes in one step |
| `ValidationError.errors()` | a list of `{"type", "loc", "msg", "input", ...}` dicts |
| `model.model_copy(update=..., deep=...)` | cheap copies; **`update` is not validated** |

Pydantic v1 names such as `.dict()`, `.json()`, `parse_obj()` and `copy()`
still exist in some tutorials. Do not use them: they are deprecated in v2.

## Tasks

All tasks are in [`exercise.py`](exercise.py).

| # | Task | What you practise |
|---|------|-------------------|
| 1 | `Product` | required/optional fields, defaults, `default_factory`, lax coercion |
| 2 | `StrictPayment` | `ConfigDict(strict=True)`, `int_type` / `bool_type` errors |
| 3 | `Address`, `OrderItem`, `Order` | nested models, `list[Model]`, `Decimal`, `Field(ge=...)` |
| 4 | `parse_order` | `model_validate` vs `model_validate_json`, `json_invalid` |
| 5 | `format_errors` | reading `ValidationError.errors()`: `loc`, `type`, `msg` |
| 6 | `apply_discount` | `model_copy(update=...)` |
| 7 | `with_changes` | why `model_copy` skips validation, and a validated alternative |
| 8 | `clone_order` | shallow vs deep copy (`deep=True`) |

## Run the tests

```bash
uv run pytest m02_pydantic/e01_models_basics
uv run pytest m02_pydantic/e01_models_basics -k Task3   # one task only
```

## Further reading

- [Models](https://docs.pydantic.dev/latest/concepts/models/)
- [Strict mode](https://docs.pydantic.dev/latest/concepts/strict_mode/) and the [conversion table](https://docs.pydantic.dev/latest/concepts/conversion_table/)
- [Validation errors](https://docs.pydantic.dev/latest/errors/validation_errors/)
