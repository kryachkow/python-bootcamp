# 1.2 Functions, closures & decorators

Decorators are everywhere in a FastAPI codebase: `@app.get`, `@lru_cache`,
`@retry` around a flaky LLM call, `@pytest.fixture`. This exercise covers
what they are built from: flexible signatures, closures, and
`functools`.

## Concepts

| Tool | Use it for |
|------|------------|
| `def f(a, /, b, *args, c, **kwargs)` | `/` makes earlier params positional-only; params after `*` are keyword-only |
| closures + `nonlocal` | state captured by an inner function, without a class |
| decorator | a function that takes a function and returns a replacement (`wrapper`) |
| `functools.wraps` | copy `__name__`, `__doc__`, and `__wrapped__` onto the wrapper |
| decorator factory | `@retry(attempts=3)`: a function that *returns* a decorator |
| `functools.partial` | pre-bind arguments; inspectable via `.func` / `.args` / `.keywords` |
| `functools.singledispatch` | one function, different implementations per argument type |

A decorator with parameters has three levels:

```python
def retry(attempts):            # 1. called with the options
    def decorator(func):        # 2. called with the function
        @functools.wraps(func)
        def wrapper(*a, **kw):  # 3. called on every call
            ...
        return wrapper
    return decorator
```

## Tasks

All tasks are in [`exercise.py`](exercise.py).

| # | Task | What you practise |
|---|------|-------------------|
| 1 | `build_url` | positional-only, `*args`, keyword-only, `**kwargs` |
| 2 | `make_counter` | closures, `nonlocal`, raising errors eagerly |
| 3 | `compose` | functions as values, validating eagerly |
| 4 | `make_alert_sender` | `functools.partial` |
| 5 | `count_calls` | a basic decorator, `functools.wraps`, function attributes |
| 6 | `memoize` | caching by arguments, hashability, `cache_clear` |
| 7 | `retry` | decorator factory, exception tuples, injectable `sleep`, backoff |
| 8 | `to_jsonable` | `functools.singledispatch` and `register` |

## Run the tests

```bash
uv run pytest m01_python_core/e02_functions_and_decorators
uv run pytest m01_python_core/e02_functions_and_decorators -k Task7   # one task only
```

## Further reading

- [Function definitions (parameter kinds)](https://docs.python.org/3/reference/compound_stmts.html#function-definitions)
- [functools: higher-order functions](https://docs.python.org/3/library/functools.html)
- [PEP 570: positional-only parameters](https://peps.python.org/pep-0570/)
