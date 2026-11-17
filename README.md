# python-bootcamp

Hands-on exercises for the modern Python backend stack: **Python core,
Pydantic, FastAPI, SQLAlchemy, LangChain**. Each exercise has a short concept
brief, stubbed tasks with precise docstrings, and a pytest suite that turns
green once your implementation is correct.

The format is inspired by [bobocode-projects](https://github.com/bobocode-projects).

## How it works

1. Pick an exercise and read its `README.md`.
2. Open `exercise.py`. Each task is a function or class whose body raises
   `NotImplementedError`, and its docstring is the spec.
3. Implement it and run the exercise's tests until they all pass.
4. Stuck? The **`completed`** branch has a reference solution for every
   task:

   ```bash
   git diff main completed -- m02_pydantic/e02_fields_and_validators
   ```

## Setup

You need **Python 3.12+**. Nothing else: no API keys, no Docker, no database
server. SQLAlchemy uses SQLite, FastAPI uses the in-process `TestClient`, and
LangChain uses the fake chat models and embeddings that ship with
`langchain-core`.

### Option A: uv (recommended)

```bash
# install uv once: https://docs.astral.sh/uv/getting-started/installation/
uv sync                 # creates .venv and installs everything
uv run pytest           # runs ALL tests (they fail until you solve the tasks)
```

`.python-version` pins Python 3.12, and `uv` downloads it if you don't
have it. `uv.lock` pins the exact library versions the tests were checked
against.

### Option B: plain pip

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pytest
```

With pip, drop the `uv run` prefix from the commands below.

## Running tests

Run commands from the repository root, so pytest picks up the config in
`pyproject.toml`.

```bash
uv run pytest m01_python_core                              # one theme
uv run pytest m01_python_core/e01_data_structures          # one exercise
uv run pytest m01_python_core/e01_data_structures -k Task3 # one task
uv run pytest -x --lf                                      # stop at first failure, rerun last failures
```

Tests are grouped as `TestTask<N><Name>` classes, so `-k TaskN` selects
exactly one task.

## Themes

| # | Theme | Exercises |
|---|-------|-----------|
| 1 | [Python core](m01_python_core/README.md) | data structures, functions & decorators, OOP & dunder methods, dataclasses & enums, iterators & generators, context managers & exceptions, typing, asyncio |
| 2 | [Pydantic](m02_pydantic/README.md) | model basics, fields & validators, serialization & aliases, advanced types, settings |
| 3 | [FastAPI](m03_fastapi/README.md) | routing, request/response models, dependencies, errors/middleware/lifespan, CRUD with SQLAlchemy, streaming & background tasks |
| 4 | [SQLAlchemy](m04_sqlalchemy/README.md) | Core basics, ORM mapping, relationships, querying, sessions & transactions, async |
| 5 | [LangChain](m05_langchain/README.md) | prompts & messages, LCEL runnables, output parsers, tools & tool calling, retrieval/RAG, streaming/history/callbacks |

Suggested order: work through themes 1 → 5, since later themes build on
earlier ones. Each exercise is self-contained, though, so you can jump to
whatever you need right now.

## Repository layout

```
mNN_<theme>/
├── README.md               # theme overview
└── eNN_<subtheme>/
    ├── README.md           # concepts + task list
    ├── exercise.py         # your work goes here
    └── test_exercise.py    # the tests that check it
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the conventions to follow when
you add new exercises.

## Branches

| Branch | Contents |
|--------|----------|
| `main` | exercises with stubs. Tests fail until you implement the tasks |
| `completed` | reference solutions. All tests pass |
