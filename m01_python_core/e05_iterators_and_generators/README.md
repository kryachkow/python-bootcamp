# 1.5 Iterators, generators & `itertools`

Streaming LLM tokens, paginating an API, reading a huge CSV, sending texts
to an embeddings endpoint in batches: all of these are iteration problems.
Generators let you handle data one item at a time with constant memory, and
`itertools` has the building blocks, so you rarely need an index variable.

## Concepts

| Tool | Use it for |
|------|------------|
| `__iter__` + `__next__` | the iterator protocol; raise `StopIteration` at the end |
| generator function (`yield`) | an iterator written as a function; runs lazily, one step per `next()` |
| generator expression | `(f(x) for x in xs)`: a lazy `map` / `filter` |
| `yield from sub` | delegate to a sub-iterator (recursion, composition) |
| pipelines | `stage3(stage2(stage1(source)))`: each stage pulls one item at a time |
| `itertools.batched` | fixed-size chunks (3.12+) |
| `itertools.islice` | take *n* items from any iterator, including infinite ones |
| `itertools.groupby` | group **consecutive** items by key (sort first!) |
| `itertools.chain` / `zip_longest` | concatenate / merge iterables |
| `itertools.accumulate` | running totals, products, any binary function |
| `gen.send(value)` | push a value into a paused generator |

**Generators raise errors late.** The body of a generator function does not
run until the first `next()`. To validate arguments eagerly, do the checks
in a normal function and return a generator (or a generator expression), as
in tasks 5 and 7.

## Tasks

All tasks are in [`exercise.py`](exercise.py).

| # | Task | What you practise |
|---|------|-------------------|
| 1 | `Paginator` | the iterator protocol by hand, lazy page fetching |
| 2 | `clean_lines` | a generator function, lazy file processing |
| 3 | `parse_log_lines`, `errors_since` | a lazy pipeline of generators |
| 4 | `iter_leaves` | recursion with `yield from` |
| 5 | `chunked` | `itertools.batched`, eager validation |
| 6 | `daily_totals` | `itertools.groupby` and its "consecutive only" trap |
| 7 | `backoff_delays` | an infinite generator, `accumulate`, `islice` |
| 8 | `interleave` | `zip_longest`, `chain.from_iterable`, sentinel objects |
| 9 | `running_average` | `send()` and coroutine-style generators |

## Run the tests

```bash
uv run pytest m01_python_core/e05_iterators_and_generators
uv run pytest m01_python_core/e05_iterators_and_generators -k Task3   # one task only
```

## Further reading

- [Functional programming HOWTO: iterators and generators](https://docs.python.org/3/howto/functional.html)
- [itertools](https://docs.python.org/3/library/itertools.html)
- [Generator-iterator methods (`send`, `throw`, `close`)](https://docs.python.org/3/reference/expressions.html#generator-iterator-methods)
