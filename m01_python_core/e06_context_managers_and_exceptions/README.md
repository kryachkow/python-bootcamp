# 1.6 Exceptions & context managers

Good error handling is what separates a backend that returns a clean `404`
from one that returns `500` with a stack trace. Context managers are how
Python guarantees cleanup: `async with session.begin()`,
`with open(...)`, `with patch(...)`. This exercise covers both, plus the
3.11+ `ExceptionGroup` that `asyncio.TaskGroup` raises.

## Concepts

| Tool | Use it for |
|------|------------|
| exception hierarchy | one base (`AppError`) that the API layer maps to HTTP responses |
| `raise New(...) from err` | keep the low-level cause in `__cause__` (shown as "The above exception was the direct cause...") |
| `raise New(...) from None` | hide an implementation-detail exception (`__suppress_context__`) |
| `@contextmanager` | a context manager from a generator: setup, `yield`, cleanup in `finally` |
| `__enter__` / `__exit__` | class-based managers; `__exit__` returning a true value **suppresses** the exception |
| `ContextDecorator` | one class usable both as `with Timer():` and `@Timer()` |
| `contextlib.suppress` | `try: ... except X: pass` in one line |
| `contextlib.ExitStack` | a number of context managers known only at run time |
| `ExceptionGroup` / `except*` | raise and handle several unrelated errors at once |

`__exit__(exc_type, exc, tb)` gets `(None, None, None)` when the block
succeeded. Return `None` or `False` to let an exception propagate, which is
almost always what you want. Return `True` only when swallowing the error
is the purpose of the manager.

## Tasks

All tasks are in [`exercise.py`](exercise.py).

| # | Task | What you practise |
|---|------|-------------------|
| 1 | `AppError` + subclasses, `error_response` | exception hierarchy, class attributes, mapping errors to HTTP |
| 2 | `parse_payload` | `raise ... from err`, `raise ... from None` |
| 3 | `temporary_env` | `@contextmanager`, `try/finally`, restoring state |
| 4 | `Timer` | `__enter__`/`__exit__`, injectable clock, `ContextDecorator` |
| 5 | `Catch` | `__exit__` return value: suppressing vs. propagating |
| 6 | `delete_quietly`, `parse_ints` | `contextlib.suppress` |
| 7 | `acquire_all` | `ExitStack`, cleanup when entering fails halfway |
| 8 | `transaction` | snapshot + rollback on error, `deepcopy`, in-place restore |
| 9 | `run_all`, `count_failures` | `ExceptionGroup`, `add_note`, `except*` |

## Run the tests

```bash
uv run pytest m01_python_core/e06_context_managers_and_exceptions
uv run pytest m01_python_core/e06_context_managers_and_exceptions -k Task5   # one task only
```

## Further reading

- [Errors and exceptions tutorial (chaining, groups, notes)](https://docs.python.org/3/tutorial/errors.html)
- [contextlib](https://docs.python.org/3/library/contextlib.html)
- [With statement context managers (data model)](https://docs.python.org/3/reference/datamodel.html#with-statement-context-managers)
