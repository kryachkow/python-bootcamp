import copy

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from m03_fastapi.e03_dependencies import exercise
from m03_fastapi.e03_dependencies.exercise import (
    Pagination,
    SortSpec,
    User,
    create_app,
    get_current_user,
    override_user,
    parse_sort,
)

ALICE = {"X-API-Key": "key-alice"}  # admin
BOB = {"X-API-Key": "key-bob"}  # regular user


@pytest.fixture(autouse=True)
def _restore_state():
    notes = copy.deepcopy(exercise.NOTES)
    exercise.SESSION_EVENTS.clear()
    exercise.AUDIT_LOG.clear()
    yield
    exercise.NOTES[:] = notes
    exercise.SESSION_EVENTS.clear()
    exercise.AUDIT_LOG.clear()


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
def client(app):
    return TestClient(app)


class TestTask1FunctionDependency:
    def test_parse_sort_directly(self):
        assert parse_sort("title") == SortSpec("title", False)
        assert parse_sort("-owner") == SortSpec("owner", True)

    def test_parse_sort_rejects_unknown_field(self):
        with pytest.raises(HTTPException) as info:
            parse_sort("-secret")
        assert info.value.status_code == 400
        assert info.value.detail == "Cannot sort by 'secret'"

    def test_endpoint_default_sort_is_id(self, client):
        assert [n["id"] for n in client.get("/notes").json()] == [1, 2, 3, 4, 5]

    def test_endpoint_descending_title(self, client):
        titles = [n["title"] for n in client.get("/notes", params={"sort": "-title"}).json()]
        assert titles == ["write tests", "deploy v2", "call mom", "buy milk", "answer emails"]

    def test_endpoint_bad_field_gives_400(self, client):
        response = client.get("/notes", params={"sort": "password"})
        assert response.status_code == 400
        assert response.json() == {"detail": "Cannot sort by 'password'"}


class TestTask2ClassDependency:
    def test_offset_and_apply(self):
        paging = Pagination(page=3, size=2)
        assert paging.offset == 4
        assert paging.apply(list(range(10))) == [4, 5]

    def test_defaults(self, client):
        body = client.get("/notes/page").json()
        assert (body["page"], body["size"], body["total"]) == (1, 10, 5)
        assert len(body["items"]) == 5

    def test_second_page(self, client):
        body = client.get("/notes/page", params={"page": 2, "size": 2}).json()
        assert [n["id"] for n in body["items"]] == [3, 4]

    def test_page_past_the_end_is_empty(self, client):
        assert client.get("/notes/page", params={"page": 9, "size": 2}).json()["items"] == []

    @pytest.mark.parametrize("params", [{"page": 0}, {"size": 51}, {"size": 0}])
    def test_constraints(self, client, params):
        assert client.get("/notes/page", params=params).status_code == 422


class TestTask3YieldDependency:
    def test_success_commits(self, client):
        response = client.post("/notes", json={"title": "learn depends"})
        assert response.status_code == 201
        assert response.json() == {"id": 6, "title": "learn depends", "owner": "anonymous"}
        assert exercise.SESSION_EVENTS == ["open", "add", "commit", "close"]
        assert exercise.NOTES[-1]["title"] == "learn depends"

    def test_conflict_rolls_back(self, client):
        response = client.post("/notes", json={"title": "buy milk"})
        assert response.status_code == 409
        assert response.json() == {"detail": "Note 'buy milk' already exists"}
        assert exercise.SESSION_EVENTS == ["open", "add", "rollback", "close"]
        assert len(exercise.NOTES) == 5

    def test_one_session_per_request(self, client):
        client.post("/notes", json={"title": "a"})
        client.post("/notes", json={"title": "b"})
        assert exercise.SESSION_EVENTS.count("open") == 2
        assert [n["id"] for n in exercise.NOTES[-2:]] == [6, 7]

    def test_generator_directly(self):
        gen = exercise.get_session()
        session = next(gen)
        assert isinstance(session, exercise.FakeSession)
        with pytest.raises(StopIteration):
            next(gen)
        assert exercise.SESSION_EVENTS == ["open", "commit", "close"]


class TestTask4ApiKeyAuth:
    def test_valid_key(self, client):
        assert client.get("/me", headers=BOB).json() == {"username": "bob", "is_admin": False}

    def test_missing_key(self, client):
        response = client.get("/me")
        assert response.status_code == 401
        assert response.json() == {"detail": "Missing API key"}
        assert response.headers["www-authenticate"] == "ApiKey"

    def test_invalid_key(self, client):
        response = client.get("/me", headers={"X-API-Key": "stolen"})
        assert response.status_code == 401
        assert response.json() == {"detail": "Invalid API key"}
        assert response.headers["www-authenticate"] == "ApiKey"

    def test_get_current_user_directly(self):
        assert get_current_user("key-alice").username == "alice"


class TestTask5RequireAdmin:
    def test_admin_can_delete(self, client):
        response = client.delete("/notes/2", headers=ALICE)
        assert response.status_code == 204
        assert 2 not in [n["id"] for n in exercise.NOTES]

    def test_non_admin_gets_403(self, client):
        response = client.delete("/notes/2", headers=BOB)
        assert response.status_code == 403
        assert response.json() == {"detail": "Admin privileges required"}
        assert len(exercise.NOTES) == 5

    def test_anonymous_gets_401_not_403(self, client):
        response = client.delete("/notes/2")
        assert response.status_code == 401
        assert response.json() == {"detail": "Missing API key"}

    def test_unknown_note_gives_404(self, client):
        response = client.delete("/notes/99", headers=ALICE)
        assert response.status_code == 404
        assert response.json() == {"detail": "Note 99 not found"}


class TestTask6RouterDependencies:
    def test_admin_stats(self, client):
        response = client.get("/admin/stats", headers=ALICE)
        assert response.status_code == 200
        assert response.json() == {"notes": 5, "api_keys": 2}

    def test_router_dependency_blocks_non_admin(self, client):
        assert client.get("/admin/stats", headers=BOB).status_code == 403
        assert client.get("/admin/stats").status_code == 401

    def test_audit_log(self, client):
        client.get("/admin/stats", headers=ALICE)
        assert exercise.AUDIT_LOG == ["alice GET /admin/stats"]

    def test_override_with_dependency_overrides(self, app, client):
        # The standard way to fake auth in tests: swap the dependency.
        app.dependency_overrides[get_current_user] = lambda: User(username="root", is_admin=True)
        try:
            assert client.get("/admin/stats").status_code == 200
            assert exercise.AUDIT_LOG == ["root GET /admin/stats"]
        finally:
            app.dependency_overrides.clear()


class TestTask7OverrideUser:
    def test_override_inside_block(self, app, client):
        with override_user(app, User(username="carol", is_admin=True)):
            assert client.get("/me").json() == {"username": "carol", "is_admin": True}

    def test_restored_after_block(self, app, client):
        with override_user(app, User(username="carol")):
            pass
        assert client.get("/me").status_code == 401
        assert get_current_user not in app.dependency_overrides

    def test_restored_after_exception(self, app):
        class Boom(Exception):
            pass

        with pytest.raises(Boom), override_user(app, User(username="carol")):
            raise Boom

        assert app.dependency_overrides == {}

    def test_nested_blocks(self, app, client):
        with override_user(app, User(username="outer")):
            with override_user(app, User(username="inner")):
                assert client.get("/me").json()["username"] == "inner"
            assert client.get("/me").json()["username"] == "outer"

    def test_override_flows_into_sub_dependencies(self, app, client):
        with override_user(app, User(username="dave", is_admin=False)):
            assert client.get("/admin/stats").status_code == 403
