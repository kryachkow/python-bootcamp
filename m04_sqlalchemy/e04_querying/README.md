# 4.4 Querying with `select()`

Every ORM query in 2.x is a `select()` construct run by `session.execute()`
or `session.scalars()`. The legacy `session.query()` API is not used. This
exercise works through the queries a backend service actually needs:
dynamic filters, pagination, joins, aggregates, CTEs, `EXISTS`, and window
functions. The database does the filtering, sorting, and counting, not Python.

## Concepts

| Construct | SQL |
|-----------|-----|
| `.where(a, b)`, `and_()`, `or_()`, `.in_()`, `.icontains()` | `WHERE`, `AND`, `OR`, `IN`, case-insensitive `LIKE` |
| `.order_by().limit().offset()` | pagination (order by a unique key too) |
| `.join(Rel)` / `.outerjoin(Rel)` | `JOIN` / `LEFT OUTER JOIN` along a relationship |
| `func.count/sum/avg`, `.group_by()`, `.having()` | aggregates; `HAVING` filters on them |
| `.cte("name")` / `.subquery()` | `WITH name AS (...)` / derived table |
| `exists().where(...)`, `~exists()` | correlated `EXISTS` / `NOT EXISTS` |
| `func.rank().over(partition_by=..., order_by=...)` | window functions |

| Result method | 0 rows | 1 row | 2+ rows |
|---------------|--------|-------|---------|
| `.first()` | `None` | row | first row (silently) |
| `.scalar_one()` / `.one()` | `NoResultFound` | value | `MultipleResultsFound` |
| `.scalar_one_or_none()` / `.one_or_none()` | `None` | value | `MultipleResultsFound` |

## Tasks

All tasks are in [`exercise.py`](exercise.py). The models and the seed data
(see the module docstring) are given.

| # | Task | What you practise |
|---|------|-------------------|
| 1 | `filter_employees` | building `WHERE` dynamically, `in_`, `or_`, `icontains` |
| 2 | `paginate_employees` | `limit`/`offset`, `COUNT(*)`, stable ordering |
| 3 | `employee_departments` | `outerjoin`, selecting columns from two entities |
| 4 | `department_stats` | `group_by`, `having`, `count`/`sum`/`avg`, `coalesce` |
| 5 | `above_department_average` | CTE joined back to the base table |
| 6 | `empty_departments`, `anyone_hired_after` | `NOT EXISTS`, `SELECT EXISTS` |
| 7 | `get_employee_by_email`, `sole_member_of` | `scalar_one` vs `scalar_one_or_none` |
| 8 | `salary_ranks` | `RANK()` window function |
| 9 | `top_earners_per_department` | `ROW_NUMBER()` in a subquery, top N per group |

## Run the tests

```bash
uv run pytest m04_sqlalchemy/e04_querying
uv run pytest m04_sqlalchemy/e04_querying -k Task9   # one task only
```

## Further reading

- [ORM querying guide: SELECT statements](https://docs.sqlalchemy.org/en/21/orm/queryguide/select.html)
- [Using SELECT statements (subqueries, CTEs, window functions)](https://docs.sqlalchemy.org/en/21/tutorial/data_select.html)
