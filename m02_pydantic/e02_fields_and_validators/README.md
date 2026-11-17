# 2.2 Fields, validators & model config

Type hints alone only check types. Real request bodies also need ranges,
formats, normalisation (strip, lowercase, reshape) and rules that span
several fields. This exercise shows where each kind of rule belongs in
Pydantic v2.

## Concepts

| Tool | Use it for |
|------|------------|
| `Field(gt=, ge=, lt=, le=, min_length=, max_length=, pattern=)` | declarative constraints, no code |
| `Annotated[T, BeforeValidator(f), AfterValidator(g)]` | a reusable type alias with its own validation (`Slug`, `CommaSeparated`) |
| `@field_validator("a", "b", mode="after")` | per-field logic on the already-typed value |
| `@field_validator("x", mode="before")` | reshape raw input (an `int` phone number, a messy string) before type checks |
| `@model_validator(mode="after")` | cross-field rules on the finished model (`start < end`, password confirmation) |
| `@model_validator(mode="before")` | normalise the raw input as a whole (renamed keys, string/list shapes) |
| `ConfigDict(extra="forbid")` | reject unknown keys instead of silently dropping typos |
| `ConfigDict(str_strip_whitespace=True)` | strip every `str` field |
| `ConfigDict(validate_assignment=True)` | re-validate on `model.field = value` |
| `ConfigDict(frozen=True)` | immutable, hashable value objects |

Order of execution for one field: **before** validators, then the type and
`Field` constraints, then **after** validators. An after `model_validator`
runs only when every field is valid. Raise `ValueError` in a validator; it
becomes a `ValidationError` entry with type `"value_error"`. The v1
decorators `@validator` and `@root_validator` are deprecated.

## Tasks

All tasks are in [`exercise.py`](exercise.py).

| # | Task | What you practise |
|---|------|-------------------|
| 1 | `CreateUserRequest` | `Field` constraints on strings, ints and lists |
| 2 | `Slug`, `CommaSeparated`, `Article` | reusable `Annotated` types, `BeforeValidator` / `AfterValidator` |
| 3 | `Contact` | `@field_validator` for several fields, `mode="before"` vs `"after"` |
| 4 | `Booking` | `@model_validator(mode="after")`: date range rules, `@property` |
| 5 | `RegisterRequest` | password confirmation, `Field(repr=False)` |
| 6 | `GeoPoint` | `@model_validator(mode="before")`: accept many input shapes |
| 7 | `Account` | `extra="forbid"`, `str_strip_whitespace`, `validate_assignment` |
| 8 | `Money` | `frozen=True` value object, hashing, `__add__` |

## Run the tests

```bash
uv run pytest m02_pydantic/e02_fields_and_validators
uv run pytest m02_pydantic/e02_fields_and_validators -k Task6   # one task only
```

## Further reading

- [Fields](https://docs.pydantic.dev/latest/concepts/fields/)
- [Validators](https://docs.pydantic.dev/latest/concepts/validators/)
- [Configuration](https://docs.pydantic.dev/latest/api/config/)
