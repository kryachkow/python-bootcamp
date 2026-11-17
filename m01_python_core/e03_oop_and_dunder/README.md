# 1.3 Classes, dunder methods, ABCs & mixins

Pydantic models, SQLAlchemy declarative classes, and LangChain runnables all
rely on the Python data model: special ("dunder") methods, properties,
abstract base classes, and cooperative `super()`. This exercise has you
write those pieces by hand, so the frameworks stop being magic.

## Concepts

| Tool | Use it for |
|------|------------|
| `@property` / `@x.setter` | computed attributes and validation on assignment; no setter = read-only |
| `__repr__` / `__str__` | debugging output vs. user-facing text |
| `__eq__` + `__hash__` | value objects; return `NotImplemented` for foreign types |
| `functools.total_ordering` | derive `<=`, `>`, `>=` from `__lt__` and `__eq__` |
| `__add__` / `__radd__` / `__mul__` / `__rmul__` | operator overloading; `__radd__` makes `sum()` work |
| `__len__` / `__getitem__` / `__iter__` / `__contains__` | the sequence (container) protocol |
| `@classmethod` | alternative constructors (`from_cents`, `parse`); use `cls(...)` |
| `abc.ABC` + `@abstractmethod` | interfaces that cannot be instantiated half-implemented |
| cooperative `super()` | mixins where every class in the MRO runs exactly once |
| `__slots__` | no per-instance `__dict__`: less memory, no typo attributes |

`NotImplemented` (the constant) is not `NotImplementedError` (the
exception). Return it from a binary dunder to say "I don't know this
operand". Python then tries the reflected method of the other operand, and
raises `TypeError` only if that fails too.

## Tasks

All tasks are in [`exercise.py`](exercise.py).

| # | Task | What you practise |
|---|------|-------------------|
| 1 | `Temperature` | properties, setters, validation, read-only property |
| 2 | `Money` value semantics | `__repr__`, `__str__`, `__eq__`, `__hash__` |
| 3 | `Money` arithmetic | `__add__`, `__radd__`, `__sub__`, `__neg__`, `__mul__`, `__rmul__`, `NotImplemented` |
| 4 | `Money` ordering & constructors | `total_ordering`, `@classmethod` (`zero`, `from_cents`, `parse`) |
| 5 | `MessageHistory` | the container protocol, slicing, trimming an LLM chat history |
| 6 | `Notifier` + subclasses | `abc.ABC`, abstract property, template method |
| 7 | `TimestampMixin`, `SoftDeleteMixin`, `Article` | MRO, cooperative `__init__(**kwargs)` and `super()` |
| 8 | `Vector` | `__slots__`, `__abs__`, `__bool__`, `__matmul__`, cosine similarity |

Tasks 2-4 build on each other (they all live on `Money`), so do them in order.

## Run the tests

```bash
uv run pytest m01_python_core/e03_oop_and_dunder
uv run pytest m01_python_core/e03_oop_and_dunder -k Task7   # one task only
```

## Further reading

- [Data model: special method names](https://docs.python.org/3/reference/datamodel.html#special-method-names)
- [abc: abstract base classes](https://docs.python.org/3/library/abc.html)
- [The Python 2.3 method resolution order (still how the MRO works)](https://docs.python.org/3/howto/mro.html)
