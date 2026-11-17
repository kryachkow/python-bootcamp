from datetime import date

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import MultipleResultsFound, NoResultFound
from sqlalchemy.orm import Session

from m04_sqlalchemy.e04_querying.exercise import (
    Base,
    Department,
    DeptStats,
    Employee,
    Page,
    above_department_average,
    anyone_hired_after,
    department_stats,
    empty_departments,
    employee_departments,
    filter_employees,
    get_employee_by_email,
    paginate_employees,
    salary_ranks,
    sole_member_of,
    top_earners_per_department,
)

EMPLOYEES = [
    # name,   salary, department,    hired_on
    ("Alice", 120, "Engineering", date(2019, 3, 1)),
    ("Bob", 95, "Engineering", date(2021, 6, 15)),
    ("Carol", 130, "Engineering", date(2018, 1, 10)),
    ("Dave", 70, "Sales", date(2022, 2, 1)),
    ("Eve", 85, "Sales", date(2020, 9, 30)),
    ("Frank", 60, "Support", date(2023, 4, 12)),
    ("Grace", 50, None, date(2021, 1, 1)),
    ("Heidi", 95, "Engineering", date(2017, 5, 5)),
]


@pytest.fixture
def engine():
    eng = create_engine("sqlite://")
    yield eng
    eng.dispose()


@pytest.fixture
def session(engine):
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        depts = {n: Department(name=n) for n in ("Engineering", "Sales", "Support", "Legal")}
        s.add_all(depts.values())
        for name, salary, dept, hired in EMPLOYEES:
            s.add(
                Employee(
                    name=name,
                    email=f"{name.lower()}@corp.io",
                    salary=salary,
                    hired_on=hired,
                    department=depts[dept] if dept else None,
                )
            )
        s.commit()
        s.expunge_all()
        yield s


@pytest.fixture
def sql(engine):
    statements: list[str] = []
    event.listen(engine, "before_cursor_execute", lambda c, cur, stmt, *a: statements.append(stmt))
    return statements


class TestTask1FilterEmployees:
    def test_no_filters_returns_everyone_sorted(self, session):
        assert filter_employees(session) == sorted(e[0] for e in EMPLOYEES)

    def test_combined_filters(self, session):
        assert filter_employees(session, min_salary=90, department_names=["Engineering"]) == [
            "Alice", "Bob", "Carol", "Heidi"
        ]
        assert filter_employees(session, min_salary=100) == ["Alice", "Carol"]

    def test_in_multiple_departments(self, session):
        assert filter_employees(session, department_names=["Sales", "Support"]) == [
            "Dave", "Eve", "Frank"
        ]
        assert filter_employees(session, department_names=[]) == []

    def test_text_matches_name_or_email_case_insensitive(self, session):
        assert filter_employees(session, text="AL") == ["Alice"]
        assert filter_employees(session, text="@CORP") == sorted(e[0] for e in EMPLOYEES)
        assert filter_employees(session, text="e", min_salary=90) == ["Alice", "Heidi"]

    def test_single_query(self, session, sql):
        filter_employees(session, min_salary=1, department_names=["Sales"], text="a")
        assert len(sql) == 1


class TestTask2Paginate:
    def test_first_page(self, session):
        assert paginate_employees(session, 1, 3) == Page(
            items=["Alice", "Bob", "Carol"], total=8, page=1, pages=3
        )

    def test_last_partial_page_and_past_end(self, session):
        assert paginate_employees(session, 3, 3).items == ["Grace", "Heidi"]
        assert paginate_employees(session, 4, 3).items == []

    def test_pages_cover_everything_once(self, session):
        names = [n for p in (1, 2, 3, 4) for n in paginate_employees(session, p, 2).items]
        assert names == sorted(e[0] for e in EMPLOYEES)

    @pytest.mark.parametrize("page,per_page", [(0, 10), (1, 0), (-1, 5)])
    def test_invalid(self, session, page, per_page):
        with pytest.raises(ValueError):
            paginate_employees(session, page, per_page)

    def test_uses_count_and_limit(self, session, sql):
        paginate_employees(session, 2, 2)
        joined = " ".join(sql).upper()
        assert "COUNT(" in joined and "LIMIT" in joined and "OFFSET" in joined


class TestTask3OuterJoin:
    def test_includes_employee_without_department(self, session):
        rows = employee_departments(session)
        assert len(rows) == 8
        assert ("Grace", None) in rows
        assert rows[0] == ("Alice", "Engineering")

    def test_sorted_by_employee(self, session):
        assert [r[0] for r in employee_departments(session)] == sorted(e[0] for e in EMPLOYEES)

    def test_one_query(self, session, sql):
        employee_departments(session)
        assert len(sql) == 1 and "LEFT OUTER JOIN" in sql[0].upper()


class TestTask4DepartmentStats:
    def test_default_excludes_empty(self, session):
        assert department_stats(session) == [
            DeptStats("Engineering", 4, 440, 110.0),
            DeptStats("Sales", 2, 155, 77.5),
            DeptStats("Support", 1, 60, 60.0),
        ]

    def test_min_headcount_zero_includes_legal(self, session):
        stats = department_stats(session, min_headcount=0)
        assert DeptStats("Legal", 0, 0, None) in stats
        assert [s.name for s in stats] == ["Engineering", "Legal", "Sales", "Support"]

    def test_having(self, session):
        assert [s.name for s in department_stats(session, min_headcount=2)] == [
            "Engineering", "Sales"
        ]

    def test_aggregates_in_sql(self, session, sql):
        department_stats(session)
        assert len(sql) == 1
        assert "GROUP BY" in sql[0].upper() and "HAVING" in sql[0].upper()


class TestTask5AboveDepartmentAverage:
    def test_result(self, session):
        # Engineering avg 110 -> Alice 120, Carol 130; Sales avg 77.5 -> Eve 85.
        assert above_department_average(session) == ["Alice", "Carol", "Eve"]

    def test_uses_cte(self, session, sql):
        above_department_average(session)
        assert len(sql) == 1 and sql[0].upper().lstrip().startswith("WITH")

    def test_changes_with_data(self, session):
        support = session.get(Employee, 6).department  # Frank alone: salary == avg
        assert "Frank" not in above_department_average(session)
        session.get(Employee, 7).department = support  # Grace (50) joins: avg 55
        session.flush()
        assert "Frank" in above_department_average(session)


class TestTask6Exists:
    def test_empty_departments(self, session):
        assert empty_departments(session) == ["Legal"]

    def test_empty_departments_after_change(self, session):
        session.get(Employee, 6).department_id = None  # Frank leaves Support
        session.flush()
        assert empty_departments(session) == ["Legal", "Support"]

    def test_anyone_hired_after(self, session, sql):
        assert anyone_hired_after(session, date(2023, 1, 1)) is True
        assert anyone_hired_after(session, date(2023, 4, 12)) is False
        assert all("EXISTS" in s.upper() for s in sql)


class TestTask7ScalarOne:
    def test_get_found(self, session):
        emp = get_employee_by_email(session, "bob@corp.io")
        assert isinstance(emp, Employee) and emp.name == "Bob"

    def test_get_missing_raises(self, session):
        with pytest.raises(NoResultFound):
            get_employee_by_email(session, "nobody@corp.io")

    def test_sole_member(self, session):
        assert sole_member_of(session, "Support").name == "Frank"
        assert sole_member_of(session, "Legal") is None

    def test_sole_member_ambiguous(self, session):
        with pytest.raises(MultipleResultsFound):
            sole_member_of(session, "Sales")


class TestTask8SalaryRanks:
    def test_rank_with_ties(self, session):
        assert salary_ranks(session, "Engineering") == [
            ("Carol", 130, 1),
            ("Alice", 120, 2),
            ("Bob", 95, 3),
            ("Heidi", 95, 3),
        ]

    def test_other_department(self, session):
        assert salary_ranks(session, "Sales") == [("Eve", 85, 1), ("Dave", 70, 2)]

    def test_empty(self, session):
        assert salary_ranks(session, "Legal") == []
        assert salary_ranks(session, "Nope") == []

    def test_window_in_sql(self, session, sql):
        salary_ranks(session, "Sales")
        assert "OVER" in sql[0].upper()


class TestTask9TopEarners:
    def test_top_one(self, session):
        assert top_earners_per_department(session, 1) == {
            "Engineering": ["Carol"],
            "Sales": ["Eve"],
            "Support": ["Frank"],
        }

    def test_ties_do_not_add_rows(self, session):
        result = top_earners_per_department(session, 3)
        assert result["Engineering"] == ["Carol", "Alice", "Bob"]
        assert result["Sales"] == ["Eve", "Dave"]
        assert list(result) == ["Engineering", "Sales", "Support"]

    def test_zero(self, session):
        assert top_earners_per_department(session, 0) == {}

    def test_single_query_with_row_number(self, session, sql):
        top_earners_per_department(session, 2)
        assert len(sql) == 1 and "ROW_NUMBER()" in sql[0].upper()
