# Exercise conventions

Follow these rules when you add or change an exercise, so every exercise
looks and runs the same way.

## Layout

```
mNN_<theme>/                    # module (theme), e.g. m02_pydantic
├── __init__.py
├── README.md                   # theme overview + table of its exercises
└── eNN_<subtheme>/             # one exercise (sub-theme)
    ├── __init__.py
    ├── README.md               # concepts, task table, run command, links
    ├── exercise.py             # the tasks (more modules are allowed)
    └── test_exercise.py        # pytest tests for every task
```

* Directory names start with `m`/`e` plus a number. They must not shadow
  real libraries (`m02_pydantic`, never `pydantic`).
* Tests import with absolute paths, for example
  `from m02_pydantic.e01_models_basics.exercise import User`.

## Tasks

* Each task is one function, one class, or one clearly separated part of a
  module. Put a banner comment above it:

  ```python
  # ---------------------------------------------------------------------------
  # Task 3: flatten
  # ---------------------------------------------------------------------------
  ```

* The docstring is the spec. It must give enough detail to solve the task
  without reading the tests: inputs, outputs, edge cases, errors to raise,
  and an example. A `Hint:` line is welcome.
* Stubs raise `NotImplementedError`. Importing a stubbed module must still
  work, so test collection never fails on the `main` branch.

## Tests

* Group the tests for each task in a class named `TestTask<N><Name>`, so you
  can run one task with `pytest -k Task3`.
* No network, API keys, or external services. Use SQLite (in-memory or
  `tmp_path`), FastAPI's `TestClient`, and the fake LLMs and embeddings in
  `langchain_core`.
* Tests must be deterministic. They must not depend on wall-clock timing
  beyond small `asyncio.sleep` values. The whole suite runs in seconds.
* Do not call exercise code at test-module import time. Use fixtures, so a
  stub fails as a test, not as a collection error.
