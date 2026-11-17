# 4.1 Core basics: engines, `text()`, tables, CRUD

SQLAlchemy Core is the SQL expression layer under the ORM. You reach for it
in migrations, bulk jobs, reports, and anywhere one ORM object per row would
be wasteful. This exercise goes from a raw `text()` query to typed
`insert`/`select`/`update`/`delete` statements and a dialect-specific upsert.

## Concepts

| Tool | Use it for |
|------|------------|
| `create_engine(url)` | a pool of connections plus a dialect; create one per app, not per request |
| `event.listens_for(engine, "connect")` | per-connection setup such as `PRAGMA foreign_keys=ON` |
| `engine.begin()` | a connection inside a transaction: commit on success, rollback on error |
| `engine.connect()` | a connection; you call `conn.commit()` yourself |
| `text("... :name")` + params dict | raw SQL with **bound parameters**; never f-strings (SQL injection) |
| `MetaData`, `Table`, `Column` | the schema as Python objects; `metadata.create_all(conn)` |
| `default=` vs `server_default=` | value set by SQLAlchemy vs. a `DEFAULT` in the DDL |
| `insert/select/update/delete(table)` | typed statements; `.returning(...)` for generated values |
| `result.mappings()` | rows as dict-like `RowMapping` objects |
| `sqlite.insert(...).on_conflict_do_update` | one-statement upsert (same API for PostgreSQL) |

## Tasks

All tasks are in [`exercise.py`](exercise.py).

| # | Task | What you practise |
|---|------|-------------------|
| 1 | `create_sqlite_engine` | engine URLs, `connect` event listener |
| 2 | `execute_in_transaction` | `engine.begin()`, all-or-nothing transactions |
| 3 | `find_user_by_email` | `text()` with bound parameters, `.mappings()` |
| 4 | `users` / `orders` tables | `Table`, `Column`, constraints, `ForeignKey(ondelete=...)`, defaults |
| 5 | `insert_users` | multi-row `insert().returning(..., sort_by_parameter_order=True)` |
| 6 | `list_active_users` | `select().where().order_by()`, optional filters |
| 7 | `deactivate_user` | `update()`, `rowcount` |
| 8 | `purge_inactive_users` | `delete()`, database-side `ON DELETE CASCADE` |
| 9 | `upsert_user` | `INSERT ... ON CONFLICT DO UPDATE`, `excluded` |

## Run the tests

```bash
uv run pytest m04_sqlalchemy/e01_core_basics
uv run pytest m04_sqlalchemy/e01_core_basics -k Task3   # one task only
```

## Further reading

- [SQLAlchemy Unified Tutorial: working with transactions and the DBAPI](https://docs.sqlalchemy.org/en/21/tutorial/dbapi_transactions.html)
- [Working with data: insert, select, update, delete](https://docs.sqlalchemy.org/en/21/tutorial/data.html)
- [SQLite dialect: foreign keys and `ON CONFLICT`](https://docs.sqlalchemy.org/en/21/dialects/sqlite.html)
