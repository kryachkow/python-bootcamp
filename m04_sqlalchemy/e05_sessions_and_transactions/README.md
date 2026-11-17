# 4.5 Sessions and transactions

A `Session` is a *unit of work*: it records what you add, change, and delete,
and writes it all in one flush. It is also an *identity map*: within one
session, one database row is always the same Python object. This exercise
covers flushing versus committing, transaction boundaries, recovering from
constraint errors, savepoints, a repository class, optimistic locking, and
the `expire_on_commit` setting that confuses every new FastAPI project.

## Concepts

| Concept | What to remember |
|---------|------------------|
| identity map | `session.get(Model, pk)` twice returns the same object; `get` skips SQL on a hit |
| `flush()` | sends pending SQL inside the open transaction; ids get assigned; nothing is permanent |
| `commit()` | flushes, then commits; by default also expires all loaded objects |
| `rollback()` | required after a failed flush, or the session raises `PendingRollbackError` |
| `with factory.begin() as s:` | session + transaction: commit on success, rollback on error, then close |
| `with s.begin_nested():` | a `SAVEPOINT`: undo part of a transaction without losing the rest |
| repository | data access behind methods; it flushes but never commits (the caller owns the transaction) |
| `version_id_col` | optimistic locking: concurrent stale updates raise `StaleDataError` |
| `expire_on_commit=False` | objects stay readable after commit and close (needed for responses, mandatory in async) |

## Tasks

All tasks are in [`exercise.py`](exercise.py). Task 7 is one line in the
`Account` model at the top of the file.

| # | Task | What you practise |
|---|------|-------------------|
| 1 | `load_twice` | the identity map |
| 2 | `create_pending` | `flush()` vs `commit()`, rollback of flushed rows |
| 3 | `transfer` | `sessionmaker.begin()` as an atomic transaction boundary |
| 4 | `create_account_or_none` | catching `IntegrityError`, `rollback()`, reusable session |
| 5 | `open_accounts` | `begin_nested()` savepoints |
| 6 | `AccountRepository` | repository pattern: add / get / get_by_owner / list / delete |
| 7 | `Account.__mapper_args__` | `version_id_col`, `StaleDataError` |
| 8 | `make_api_session_factory`, `open_account_for_response` | `expire_on_commit`, `DetachedInstanceError` |

## Run the tests

```bash
uv run pytest m04_sqlalchemy/e05_sessions_and_transactions
uv run pytest m04_sqlalchemy/e05_sessions_and_transactions -k Task5   # one task only
```

## Further reading

- [Session basics](https://docs.sqlalchemy.org/en/21/orm/session_basics.html)
- [Transactions and connection management (savepoints)](https://docs.sqlalchemy.org/en/21/orm/session_transaction.html)
- [Configuring a version counter](https://docs.sqlalchemy.org/en/21/orm/versioning.html)
