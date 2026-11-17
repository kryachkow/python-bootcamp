# Module 4: SQLAlchemy 2.x

SQLAlchemy is the database layer of most serious Python backends, including
FastAPI services. This module uses the 2.x style throughout: `DeclarativeBase`,
`Mapped[...]` annotations, `mapped_column()`, `select()` with
`Session.execute()` / `Session.scalars()`, and the asyncio extension. Nothing
here uses the legacy `session.query()` API or `declarative_base()`. You start
with Core (engines, raw SQL, tables), then map models, wire up relationships,
write real queries, learn how the `Session` and its transactions behave, and
finish with the async stack a FastAPI app runs on. Every test uses a fresh
SQLite database (in memory or in pytest's `tmp_path`), so there is nothing to
install or start.

## Prerequisites

- Module 1 (Python core). Basic SQL: `SELECT`, `JOIN`, `GROUP BY`, primary
  and foreign keys.
- For exercise 6: `async`/`await` and `asyncio.gather`.

## Exercises

| # | Exercise | Topics |
|---|----------|--------|
| 1 | [Core basics](e01_core_basics/) | `create_engine`, `engine.begin()`, `text()` and bound parameters, SQL injection, `MetaData`/`Table`, Core CRUD, `RETURNING`, mappings, upsert |
| 2 | [ORM mapping](e02_orm_mapping/) | `DeclarativeBase`, `Mapped`, nullability, defaults vs server defaults, constraints and indexes, `type_annotation_map`, Enum and JSON columns |
| 3 | [Relationships](e03_relationships/) | one-to-many, many-to-many, association objects, cascades, `selectinload`/`joinedload`, counting queries to catch N+1 |
| 4 | [Querying](e04_querying/) | filters, pagination, joins, `group_by`/`having`, CTEs, `EXISTS`, `scalar_one` semantics, window functions |
| 5 | [Sessions and transactions](e05_sessions_and_transactions/) | identity map, flush vs commit, rollback, savepoints, repository pattern, optimistic locking, `expire_on_commit` |
| 6 | [Async](e06_async/) | `create_async_engine`, `async_sessionmaker`, `run_sync`, eager loading vs `MissingGreenlet`, concurrent sessions, streaming |

## Recommended order

Do them in order. Exercise 1 introduces the SQL concepts the ORM builds on;
exercises 2 and 3 are needed for everything after them; exercise 5 explains
behaviour you will meet in 3 and 4; exercise 6 assumes all of the above.

```bash
uv run pytest m04_sqlalchemy                    # the whole module
uv run pytest m04_sqlalchemy/e03_relationships  # one exercise
```

## Setup notes

No setup: SQLite ships with Python, and `aiosqlite` is a project dependency.
Exercise 6 needs `greenlet`, which SQLAlchemy 2.1 installs only with the
`sqlalchemy[asyncio]` extra. The project already depends on that extra, so
`uv sync` or `pip install -r requirements.txt` covers it.
