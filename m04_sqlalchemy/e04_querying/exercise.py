"""Exercise 4.4: querying with ``select()``.

The models are given. Every task is one query function. Write each query
with the 2.x API (``select()``, ``session.execute()``, ``session.scalars()``,
``session.scalar()``) and let the database do the work: no filtering, sorting,
or counting in Python. Run the tests with:

    uv run pytest m04_sqlalchemy/e04_querying

The tests seed this data (salaries in thousands):

    Department   Employees (salary)
    Engineering  Carol 130, Alice 120, Bob 95, Heidi 95
    Sales        Eve 85, Dave 70
    Support      Frank 60
    Legal        (nobody)
    (none)       Grace 50          <- a contractor with no department
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import NamedTuple

from sqlalchemy import ForeignKey, String, and_, exists, func, or_, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    employees: Mapped[list[Employee]] = relationship(back_populates="department")


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    email: Mapped[str] = mapped_column(String(100), unique=True)
    salary: Mapped[int]
    hired_on: Mapped[date]
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"))
    department: Mapped[Department | None] = relationship(back_populates="employees")

    def __repr__(self) -> str:
        return f"Employee(id={self.id}, name={self.name!r})"


# ---------------------------------------------------------------------------
# Task 1: dynamic filters
# ---------------------------------------------------------------------------
def filter_employees(
    session: Session,
    *,
    min_salary: int | None = None,
    department_names: list[str] | None = None,
    text: str | None = None,
) -> list[str]:
    """Return the names of employees matching ALL given filters, sorted by name.

    * ``min_salary``: ``salary >= min_salary``.
    * ``department_names``: the employee's department name is one of these
      (``in_``). Employees without a department never match this filter.
    * ``text``: case-insensitive substring of the name OR of the email.
    * A filter that is ``None`` is not applied; no filters returns everyone.

    >>> filter_employees(session, min_salary=90, department_names=["Engineering"])  # doctest: +SKIP
    ['Alice', 'Bob', 'Carol', 'Heidi']

    Hint: collect conditions in a list and finish with ``.where(and_(*conds))``
    (or call ``.where()`` once per condition: repeated calls are ANDed).
    ``Employee.name.icontains(text)`` or ``.ilike(f"%{text}%")``; ``or_(a, b)``.
    """
    stmt = select(Employee.name)
    conditions = []
    if min_salary is not None:
        conditions.append(Employee.salary >= min_salary)
    if department_names is not None:
        stmt = stmt.join(Employee.department)
        conditions.append(Department.name.in_(department_names))
    if text is not None:
        conditions.append(or_(Employee.name.icontains(text), Employee.email.icontains(text)))
    if conditions:
        stmt = stmt.where(and_(*conditions))
    return list(session.scalars(stmt.order_by(Employee.name)))


# ---------------------------------------------------------------------------
# Task 2: pagination
# ---------------------------------------------------------------------------
@dataclass
class Page:
    items: list[str]
    total: int
    page: int
    pages: int


def paginate_employees(session: Session, page: int, per_page: int) -> Page:
    """Return one page of employee names, ordered by ``(name, id)``.

    * ``page`` starts at 1. Raise ``ValueError`` if ``page < 1`` or ``per_page < 1``.
    * ``total`` is the number of employees (a ``COUNT`` query, not ``len()``
      of all rows). ``pages`` is ``ceil(total / per_page)`` (0 when empty).
    * A page past the end has ``items == []``.

    Hint: ``.limit(per_page).offset((page - 1) * per_page)``;
    ``select(func.count()).select_from(Employee)``. Order by a unique key too,
    or rows can repeat or vanish between pages.
    """
    if page < 1 or per_page < 1:
        raise ValueError("page and per_page must be >= 1")
    total = session.scalar(select(func.count()).select_from(Employee)) or 0
    stmt = (
        select(Employee.name)
        .order_by(Employee.name, Employee.id)
        .limit(per_page)
        .offset((page - 1) * per_page)
    )
    return Page(
        items=list(session.scalars(stmt)),
        total=total,
        page=page,
        pages=-(-total // per_page),
    )


# ---------------------------------------------------------------------------
# Task 3: outer join
# ---------------------------------------------------------------------------
def employee_departments(session: Session) -> list[tuple[str, str | None]]:
    """Return ``(employee name, department name or None)`` for EVERY employee,
    sorted by employee name.

    An inner join would drop Grace, who has no department; use an outer join.

    Hint: ``select(Employee.name, Department.name).outerjoin(Employee.department)``;
    convert each ``Row`` with ``tuple(row)``.
    """
    stmt = (
        select(Employee.name, Department.name)
        .outerjoin(Employee.department)
        .order_by(Employee.name)
    )
    return [tuple(row) for row in session.execute(stmt)]


# ---------------------------------------------------------------------------
# Task 4: group by / having
# ---------------------------------------------------------------------------
class DeptStats(NamedTuple):
    name: str
    headcount: int
    total_salary: int
    avg_salary: float | None


def department_stats(session: Session, min_headcount: int = 1) -> list[DeptStats]:
    """Return per-department statistics, sorted by department name.

    * ``headcount``: number of employees (0 for an empty department).
    * ``total_salary``: sum of salaries, ``0`` (not ``None``) when empty.
    * ``avg_salary``: average salary as a float, ``None`` when empty.
    * Keep only departments with ``headcount >= min_headcount`` (a ``HAVING``
      clause, because it filters on an aggregate). With ``min_headcount=0``
      the empty Legal department is included.

    Hint: start from ``Department`` and ``outerjoin`` employees;
    ``func.count(Employee.id)`` counts only non-NULL ids, ``func.count()``
    would count the outer-joined NULL row as 1. ``func.coalesce(func.sum(...), 0)``.
    """
    headcount = func.count(Employee.id)
    stmt = (
        select(
            Department.name,
            headcount.label("headcount"),
            func.coalesce(func.sum(Employee.salary), 0).label("total_salary"),
            func.avg(Employee.salary).label("avg_salary"),
        )
        .outerjoin(Department.employees)
        .group_by(Department.id, Department.name)
        .having(headcount >= min_headcount)
        .order_by(Department.name)
    )
    return [
        DeptStats(name, count, total, float(avg) if avg is not None else None)
        for name, count, total, avg in session.execute(stmt)
    ]


# ---------------------------------------------------------------------------
# Task 5: CTE
# ---------------------------------------------------------------------------
def above_department_average(session: Session) -> list[str]:
    """Return names of employees who earn strictly more than the average of
    their own department, sorted by name. Employees without a department are
    ignored.

    Write it with a CTE:

    1. ``dept_avg = select(Employee.department_id, func.avg(Employee.salary).label("avg_salary"))
       .group_by(Employee.department_id).cte("dept_avg")``
    2. join ``Employee`` to ``dept_avg`` on ``department_id`` and filter on
       ``Employee.salary > dept_avg.c.avg_salary``.
    """
    dept_avg = (
        select(Employee.department_id, func.avg(Employee.salary).label("avg_salary"))
        .where(Employee.department_id.is_not(None))
        .group_by(Employee.department_id)
        .cte("dept_avg")
    )
    stmt = (
        select(Employee.name)
        .join(dept_avg, Employee.department_id == dept_avg.c.department_id)
        .where(Employee.salary > dept_avg.c.avg_salary)
        .order_by(Employee.name)
    )
    return list(session.scalars(stmt))


# ---------------------------------------------------------------------------
# Task 6: EXISTS
# ---------------------------------------------------------------------------
def empty_departments(session: Session) -> list[str]:
    """Return names of departments with no employees, sorted by name.

    Use ``~exists().where(Employee.department_id == Department.id)``: a
    correlated subquery. (``~Department.employees.any()`` generates the same
    SQL through the relationship.)
    """
    has_employees = exists().where(Employee.department_id == Department.id)
    stmt = select(Department.name).where(~has_employees).order_by(Department.name)
    return list(session.scalars(stmt))


def anyone_hired_after(session: Session, day: date) -> bool:
    """Return ``True`` if at least one employee was hired strictly after ``day``.

    Run ``SELECT EXISTS (...)`` and get a Python bool back; do not load rows.

    Hint: ``session.scalar(select(exists().where(...)))``.
    """
    return bool(session.scalar(select(exists().where(Employee.hired_on > day))))


# ---------------------------------------------------------------------------
# Task 7: scalar_one vs scalar_one_or_none
# ---------------------------------------------------------------------------
def get_employee_by_email(session: Session, email: str) -> Employee:
    """Return the employee with this email.

    Use ``session.scalars(stmt).one()`` (or ``session.execute(stmt).scalar_one()``):
    when nothing matches it raises ``sqlalchemy.exc.NoResultFound``. Let that
    exception propagate; "must exist" lookups should fail loudly.
    """
    return session.execute(select(Employee).where(Employee.email == email)).scalar_one()


def sole_member_of(session: Session, department_name: str) -> Employee | None:
    """Return the only employee of ``department_name``, or ``None`` if it has none.

    If the department has MORE than one employee, the
    ``sqlalchemy.exc.MultipleResultsFound`` raised by ``scalar_one_or_none()``
    must propagate. ``first()`` would hide that bug by picking a random one.
    """
    stmt = select(Employee).join(Employee.department).where(Department.name == department_name)
    return session.execute(stmt).scalar_one_or_none()


# ---------------------------------------------------------------------------
# Task 8: window function: rank
# ---------------------------------------------------------------------------
def salary_ranks(session: Session, department_name: str) -> list[tuple[str, int, int]]:
    """Return ``(name, salary, rank)`` for one department.

    * ``rank`` is ``RANK()`` by salary, highest first: equal salaries share a
      rank and the next rank is skipped (130 -> 1, 120 -> 2, 95 -> 3, 95 -> 3).
    * Sort by rank, then name.
    * An unknown or empty department returns ``[]``.

    Hint: ``func.rank().over(order_by=Employee.salary.desc()).label("rnk")``.
    """
    rnk = func.rank().over(order_by=Employee.salary.desc()).label("rnk")
    stmt = (
        select(Employee.name, Employee.salary, rnk)
        .join(Employee.department)
        .where(Department.name == department_name)
        .order_by(rnk, Employee.name)
    )
    return [tuple(row) for row in session.execute(stmt)]


# ---------------------------------------------------------------------------
# Task 9: window function: top N per group
# ---------------------------------------------------------------------------
def top_earners_per_department(session: Session, n: int) -> dict[str, list[str]]:
    """Return ``{department name: [names of its n best-paid employees]}``.

    * Within a department, order by salary (highest first), then name, and keep
      the first ``n`` (``ROW_NUMBER()``, so ties do not add extra people).
    * Departments without employees and employees without a department do
      not appear.
    * Dict keys in department-name order; lists in rank order.

    You cannot filter on a window function in ``WHERE`` directly: compute
    ``func.row_number().over(partition_by=..., order_by=(...))`` in a subquery
    (``.subquery()``), then select from it ``WHERE rn <= n``.
    """
    rn = (
        func.row_number()
        .over(partition_by=Employee.department_id, order_by=(Employee.salary.desc(), Employee.name))
        .label("rn")
    )
    ranked = (
        select(Department.name.label("dept"), Employee.name.label("emp"), rn)
        .join(Employee.department)
        .subquery()
    )
    stmt = select(ranked.c.dept, ranked.c.emp).where(ranked.c.rn <= n).order_by(
        ranked.c.dept, ranked.c.rn
    )
    result: dict[str, list[str]] = {}
    for dept, emp in session.execute(stmt):
        result.setdefault(dept, []).append(emp)
    return result
