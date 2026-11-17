# Module 1: Python core

The frameworks in the later modules (Pydantic, FastAPI, SQLAlchemy,
LangChain) are built on plain Python: decorators, dunder methods,
dataclasses, generators, context managers, type hints, and asyncio. This
module covers those foundations one topic per exercise, with
production-style tasks such as retry decorators, money value objects,
paginators, transactions, typed repositories, and connection pools. When you
finish it, framework internals and error messages stop being mysterious.

## Prerequisites

- Python 3.12+ and the project dependencies installed (`uv sync`).
- Basic Python syntax. No framework knowledge is needed: this module uses
  only the standard library (plus `typing_extensions`, which Pydantic
  already installs, for `TypeIs` on Python 3.12).

## Exercises

| # | Exercise | Topics |
|---|----------|--------|
| 1.1 | [Data structures & `collections`](e01_data_structures/) | comprehensions, `Counter`, `defaultdict`, `deque`, `OrderedDict`, sorting keys |
| 1.2 | [Functions, closures & decorators](e02_functions_and_decorators/) | parameter kinds, `nonlocal`, `functools.wraps`, decorator factories (`retry`), `memoize`, `partial`, `singledispatch` |
| 1.3 | [Classes, dunder methods, ABCs & mixins](e03_oop_and_dunder/) | properties, `__eq__`/`__hash__`, `total_ordering`, operator overloading, container protocol, `classmethod`, `abc`, cooperative `super()`, `__slots__` |
| 1.4 | [Dataclasses, enums & NamedTuple](e04_dataclasses_and_enums/) | `frozen`/`order`/`kw_only`, `default_factory`, `__post_init__`, `replace`, `StrEnum`, `IntFlag`, `NamedTuple` |
| 1.5 | [Iterators, generators & `itertools`](e05_iterators_and_generators/) | iterator protocol, generators, `yield from`, lazy pipelines, `batched`/`groupby`/`accumulate`/`islice`, `send()` |
| 1.6 | [Exceptions & context managers](e06_context_managers_and_exceptions/) | exception hierarchies, `raise ... from`, `@contextmanager`, `__exit__` suppression, `suppress`, `ExitStack`, rollback, `ExceptionGroup`/`except*` |
| 1.7 | [Typing in practice](e07_typing/) | `Protocol`, PEP 695 generics, `TypedDict`, `Literal`, `@overload`, `TypeGuard`/`TypeIs`, `ParamSpec`, `Concatenate` |
| 1.8 | [asyncio](e08_asyncio/) | `gather`, `Semaphore`, `timeout`, `TaskGroup`, async generators, async context managers, `Queue`, `to_thread` |

## Recommended order

Do them in order: 1.1 to 1.8. Each exercise is self-contained, but later
ones assume the earlier skills: 1.2 (decorators) before 1.7 (typed
decorators), 1.5 (generators) before 1.6 (`@contextmanager`) and 1.8 (async
generators), and 1.6 (`ExceptionGroup`) before 1.8 (`TaskGroup`). Inside an
exercise, tasks go from easy to hard.

## Running

```bash
uv run pytest m01_python_core                          # the whole module (a second or two)
uv run pytest m01_python_core/e03_oop_and_dunder       # one exercise
uv run pytest m01_python_core/e03_oop_and_dunder -k Task4   # one task
```

No special setup: no network, no API keys, no databases. The asyncio tests
run through `pytest-asyncio`, which is already configured in
`pyproject.toml`.
