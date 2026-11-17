# 4.2 ORM mapping: `DeclarativeBase`, `Mapped`, `mapped_column`

In SQLAlchemy 2.x the type annotation *is* the column definition:
`Mapped[str | None]` means a nullable string column. `mapped_column()` adds
whatever the annotation cannot express (length, uniqueness, defaults). In this
exercise you write two models from a spec, then the session code that
creates, reads, and updates them.

## Concepts

| Construct | Meaning |
|-----------|---------|
| `class Base(DeclarativeBase)` | the registry and `MetaData` all models share (replaces `declarative_base()`) |
| `type_annotation_map` | maps Python types to SQL types once, e.g. `dict[str, Any] -> JSON` |
| `Mapped[X]` / `Mapped[X \| None]` | `NOT NULL` / nullable column of type `X` |
| `mapped_column(String(50), unique=True, index=True)` | explicit type and constraints |
| `default=` / `server_default=` / `onupdate=` | Python-side insert default / DDL default / value on every UPDATE |
| `__table_args__ = (CheckConstraint(...), Index(...))` | table-level constraints and composite indexes |
| `Enum(MyEnum, values_callable=...)` | store enum *values*, not member names |
| `session.add / commit / refresh / get` | insert, make permanent, reload server values, get by PK |
| JSON mutation | in-place changes to a plain `JSON` dict are not tracked: assign a new dict |

## Tasks

All tasks are in [`exercise.py`](exercise.py). The model classes start as
plain placeholders: replace them with real mapped classes.

| # | Task | What you practise |
|---|------|-------------------|
| 1 | `Base.type_annotation_map` | JSON, timezone-aware `DateTime`, value-stored `Enum` |
| 2 | `TimestampMixin` | mixins, `server_default=func.now()`, `onupdate` |
| 3 | `User` model | `Mapped`, `Optional` -> nullable, unique index, `__repr__` |
| 4 | `Product` model | `Numeric`, callable defaults, `CheckConstraint`, composite `Index` |
| 5 | `init_db` | `create_all`, `sessionmaker` |
| 6 | `create_user` | `add`, `commit`, `refresh` |
| 7 | `get_user_or_raise` | `session.get` and the identity map |
| 8 | `add_product` | `IntegrityError` and `rollback()` |
| 9 | `set_product_attribute` | change tracking on JSON columns |

## Run the tests

```bash
uv run pytest m04_sqlalchemy/e02_orm_mapping
uv run pytest m04_sqlalchemy/e02_orm_mapping -k Task4   # one task only
```

## Further reading

- [ORM declarative table configuration](https://docs.sqlalchemy.org/en/21/orm/declarative_tables.html)
- [Customizing the type map](https://docs.sqlalchemy.org/en/21/orm/declarative_tables.html#customizing-the-type-map)
- [Mutation tracking (`MutableDict`)](https://docs.sqlalchemy.org/en/21/orm/extensions/mutable.html)
