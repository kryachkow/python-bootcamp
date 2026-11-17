# 1.4 Dataclasses, enums & NamedTuple

Not every record needs to be a Pydantic model. Inside your service layer,
`@dataclass` gives you typed, cheap value objects. `Enum` replaces magic
strings for statuses and roles, and `NamedTuple` is ideal for small immutable
rows. Pydantic, FastAPI, and SQLAlchemy all understand these types.

## Concepts

| Tool | Use it for |
|------|------------|
| `@dataclass(frozen=True)` | immutable, hashable value objects |
| `@dataclass(order=True)` | `<`, `>` etc. comparing fields as a tuple, in declaration order |
| `@dataclass(kw_only=True)` | force keyword arguments on construction |
| `field(default_factory=list)` | a fresh mutable default per instance |
| `field(compare=False)` | leave a field (timestamps, caches) out of `==` |
| `__post_init__` | validation and normalisation after the generated `__init__` |
| `dataclasses.replace` / `fields` | copy with changes (runs `__post_init__` again); introspect fields |
| `StrEnum` + `auto()` | members that *are* strings (`auto()` gives the lowercased name) |
| `IntFlag` | bit flags combined with `\|` and tested with `&` |
| `typing.NamedTuple` | a typed tuple with names: unpackable, hashable, lightweight |

Rule of thumb: use a `NamedTuple` for "a tuple with names", a `dataclass`
for an internal domain object, and a Pydantic model at the boundary
(parsing untrusted input, building API schemas).

## Tasks

All tasks are in [`exercise.py`](exercise.py). Tasks 1, 2, 3, and 6 ask you
to write the members or fields themselves. Tasks 4 and 6 ask you to replace
the plain `@dataclass` with one that has the right options.

| # | Task | What you practise |
|---|------|-------------------|
| 1 | `OrderStatus` | `StrEnum`, `auto()`, methods and properties on enums, a state machine |
| 2 | `Permission` | `IntFlag`, combining and testing bits, iterating a flag |
| 3 | `GeoPoint` | `NamedTuple` fields and defaults, `_replace`, classmethod parser |
| 4 | `Version` | `frozen=True`, `order=True`, `replace`, `__post_init__` |
| 5 | `LineItem` | `__post_init__` normalisation, `Decimal` vs `float` |
| 6 | `Order` | `kw_only`, `default_factory`, `compare=False`, `replace` |
| 7 | `AppConfig` | `fields()`, `get_type_hints`, frozen settings loaded from env vars |

## Run the tests

```bash
uv run pytest m01_python_core/e04_dataclasses_and_enums
uv run pytest m01_python_core/e04_dataclasses_and_enums -k Task6   # one task only
```

## Further reading

- [dataclasses](https://docs.python.org/3/library/dataclasses.html)
- [enum HOWTO](https://docs.python.org/3/howto/enum.html)
- [typing.NamedTuple](https://docs.python.org/3/library/typing.html#typing.NamedTuple)
