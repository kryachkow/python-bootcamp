# 1.1 Data structures & `collections`

Most of the Python you write every day reshapes lists, dicts, and sets. This
exercise covers the idioms for that and the parts of `collections` that make
a hand-written loop unnecessary.

## Concepts

| Tool | Use it for |
|------|------------|
| list / dict / set comprehensions | building a collection in one expression |
| `dict` insertion order (3.7+) | removing duplicates while keeping order (`dict.fromkeys`) |
| `collections.Counter` | counting things; `most_common(n)` |
| `collections.defaultdict` | grouping without `if key not in d` |
| `collections.deque(maxlen=n)` | sliding windows; O(1) appends and pops at both ends |
| `collections.OrderedDict` | `move_to_end`, `popitem(last=False)`: LRU-style ordering |
| `sorted(key=...)` | multi-key sorting with a tuple key, e.g. `(-score, name)` |

## Tasks

All tasks are in [`exercise.py`](exercise.py).

| # | Task | What you practise |
|---|------|-------------------|
| 1 | `count_words` | `re.findall` + `Counter` |
| 2 | `group_by_first_letter` | `defaultdict(list)` |
| 3 | `flatten` | recursion, `isinstance` checks |
| 4 | `top_n` | sorting with a composite key |
| 5 | `unique_preserve_order` | `dict.fromkeys` |
| 6 | `invert_dict` | `dict.setdefault` |
| 7 | `merge_intervals` | sort first, then a single pass |
| 8 | `moving_average` | `deque(maxlen=...)`, generators, raising errors eagerly |
| 9 | `LRUCache` | `OrderedDict` |

## Run the tests

```bash
uv run pytest m01_python_core/e01_data_structures
uv run pytest m01_python_core/e01_data_structures -k Task4   # one task only
```

## Further reading

- [collections, container datatypes](https://docs.python.org/3/library/collections.html)
- [Sorting HOW TO](https://docs.python.org/3/howto/sorting.html)
