# 1.7 Typing in practice

FastAPI builds request parsing from your annotations, Pydantic validates
against them, and LangChain's `@tool` turns a signature into a JSON schema.
Type hints are therefore part of how your code runs, not just comments for
mypy. This exercise covers the modern (3.12+) typing toolkit, and checks
what is visible **at runtime**: `isinstance` with protocols,
`__type_params__`, `__required_keys__`, `get_overloads`, `get_type_hints`,
and `inspect.signature`.

## Concepts

| Tool | Use it for |
|------|------------|
| `Protocol` + `@runtime_checkable` | structural ("duck") typing; `isinstance` checks that the methods exist |
| `class Repo[T: Bound]:` / `def f[T](...)` | PEP 695 generics: no more `TypeVar("T")` boilerplate |
| `type Alias = ...` | PEP 695 type alias (`TypeAliasType`, lazily evaluated) |
| `TypedDict`, `Required`, `NotRequired` | the shape of a plain `dict` (JSON payloads, LLM messages) |
| `Literal["a", "b"]` | a closed set of allowed values; `get_args()` lists them at runtime |
| `@overload` | different return types depending on the argument types |
| `TypeGuard[T]` / `TypeIs[T]` | user-defined narrowing functions for `if` checks |
| `**P` (`ParamSpec`) | decorators that keep the exact signature of the wrapped function |
| `Concatenate[S, P]` | "an `S` first, then `P`": decorators that inject or remove an argument |

**`TypeGuard` vs `TypeIs`.** `TypeIs[T]` narrows both branches of an `if`,
so it must return `True` for *every* value of type `T` (an `isinstance`
check is the typical case), and `T` must be a subtype of the input type.
Use `TypeGuard[T]` when either of those is not true, for example to narrow
`list[object]` to `list[str]` (lists are invariant).

**Gotcha (Python 3.12).** `from __future__ import annotations` hides
`Required` / `NotRequired` from `TypedDict`, so `__required_keys__` comes out
wrong without any error. That is why Task 4 lives in its own module,
[`messages.py`](messages.py), which does not use that import.

## Tasks

Tasks 1-3 and 5-8 are in [`exercise.py`](exercise.py). Task 4 is in
[`messages.py`](messages.py). In tasks 1-5 you write the typing construct
itself (decorator, protocol member, class or function header, `Literal`,
TypedDict keys, overloads). The comment or docstring at each one shows what
is expected.

| # | Task | What you practise |
|---|------|-------------------|
| 1 | `Retriever`, `retrieve_all` | `Protocol`, `@runtime_checkable`, structural `isinstance` |
| 2 | `InMemoryRepository[T: HasId]` | PEP 695 generic class with a bound, `__type_params__` |
| 3 | `index_by[T, K: Hashable]` | PEP 695 generic function |
| 4 | `Role`, `ChatMessage`, `ToolCall`, `validate_message` | `Literal`, `TypedDict`, `Required`/`NotRequired`, runtime validation from type metadata |
| 5 | `coerce` | `@overload`, `typing.get_overloads` |
| 6 | `is_str_list`, `is_json_scalar` | `TypeGuard`, `TypeIs`, `type` aliases |
| 7 | `logged` | `ParamSpec`-typed decorator factory, `functools.wraps`, `inspect.signature` |
| 8 | `with_session` | `Concatenate`, injecting an argument, rewriting `__signature__` |

## Run the tests

```bash
uv run pytest m01_python_core/e07_typing
uv run pytest m01_python_core/e07_typing -k Task4   # one task only
```

Optional: if you have mypy or pyright, run it on your solution as well. The
tests do not depend on it.

## Further reading

- [typing: support for type hints](https://docs.python.org/3/library/typing.html)
- [PEP 695: type parameter syntax](https://peps.python.org/pep-0695/)
- [Typing spec: narrowing with TypeGuard and TypeIs](https://typing.readthedocs.io/en/latest/spec/narrowing.html)
