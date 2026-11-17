# 4.3 Relationships and loading strategies

Relationships turn foreign keys into Python attributes. This exercise covers
the three shapes you meet in every schema, the cascades that keep child rows
consistent, and the loader options that stop the N+1 query problem: one query
for the parents, then one more for *each* parent's children.

## Concepts

| Construct | Use it for |
|-----------|------------|
| `relationship(back_populates="...")` | two attributes that mirror each other, kept in sync in Python |
| `cascade="all, delete-orphan"` | children are deleted with the parent, or when removed from the collection |
| `relationship(secondary=table)` | many-to-many through a plain association `Table` |
| association object | a mapped link class when the link carries data (quantity, price) |
| `selectinload(A.children)` | eager-load a collection with one extra `SELECT ... WHERE id IN (...)` |
| `joinedload(B.parent)` | eager-load a many-to-one in the same query with a `LEFT OUTER JOIN` |
| `selectinload(...).joinedload(...)` | chain options along a path |
| `event.listen(engine, "before_cursor_execute", ...)` | count SQL statements in tests |

| Strategy | Queries for N parents | Best for |
|----------|-----------------------|----------|
| lazy (default) | 1 + N | rarely touched attributes |
| `selectinload` | 2 | one-to-many / many-to-many collections |
| `joinedload` | 1 | many-to-one / one-to-one |

## Tasks

All tasks are in [`exercise.py`](exercise.py). The model classes start as
plain placeholders: replace them with real mapped classes.

| # | Task | What you practise |
|---|------|-------------------|
| 1 | `Author` / `Book` | one-to-many, `back_populates`, `delete-orphan`, `order_by` |
| 2 | `post_tags` / `Post` / `Tag` | many-to-many with an association table |
| 3 | `Order` / `OrderLine` | association object with extra columns, composite PK |
| 4 | `tag_post` | get-or-create inside a many-to-many |
| 5 | `place_order` | building rows through an association object, price snapshot |
| 6 | `authors_with_books` | `selectinload`, proving there is no N+1 |
| 7 | `books_with_authors` | `joinedload` |
| 8 | `orders_with_details` | chained loader options |

## Run the tests

```bash
uv run pytest m04_sqlalchemy/e03_relationships
uv run pytest m04_sqlalchemy/e03_relationships -k Task6   # one task only
```

## Further reading

- [Basic relationship patterns](https://docs.sqlalchemy.org/en/21/orm/basic_relationships.html)
- [Cascades](https://docs.sqlalchemy.org/en/21/orm/cascades.html)
- [Relationship loading techniques](https://docs.sqlalchemy.org/en/21/orm/queryguide/relationships.html)
