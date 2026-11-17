import copy

import pytest
from fastapi.testclient import TestClient

from m03_fastapi.e01_routing_basics import exercise
from m03_fastapi.e01_routing_basics.exercise import create_app


@pytest.fixture(autouse=True)
def _restore_documents():
    snapshot = copy.deepcopy(exercise.DOCUMENTS)
    yield
    exercise.DOCUMENTS[:] = snapshot


@pytest.fixture
def client():
    return TestClient(create_app())


class TestTask1TypedPathParams:
    def test_int_path_param_is_parsed(self, client):
        response = client.get("/items/42")
        assert response.status_code == 200
        assert response.json() == {"item_id": 42}

    @pytest.mark.parametrize("bad", ["abc", "4.2"])
    def test_non_int_gives_422(self, client, bad):
        response = client.get(f"/items/{bad}")
        assert response.status_code == 422
        assert response.json()["detail"][0]["loc"] == ["path", "item_id"]

    def test_path_converter_keeps_slashes(self, client):
        response = client.get("/files/reports/2024/q1.csv")
        assert response.status_code == 200
        assert response.json() == {"file_path": "reports/2024/q1.csv"}


class TestTask2EnumPath:
    def test_known_provider(self, client):
        assert client.get("/providers/anthropic").json() == {"provider": "anthropic", "local": False}

    def test_local_provider(self, client):
        assert client.get("/providers/ollama").json() == {"provider": "ollama", "local": True}

    def test_unknown_provider_gives_422(self, client):
        response = client.get("/providers/cohere")
        assert response.status_code == 422
        assert response.json()["detail"][0]["type"] == "enum"

    def test_enum_values_are_in_openapi(self, client):
        schema = client.get("/openapi.json").json()
        assert schema["components"]["schemas"]["Provider"]["enum"] == ["openai", "anthropic", "ollama"]


class TestTask3QueryParams:
    def test_defaults_hide_archived(self, client):
        body = client.get("/documents").json()
        assert body["total"] == 4
        assert [d["id"] for d in body["items"]] == [1, 2, 3, 5]

    def test_include_archived(self, client):
        body = client.get("/documents", params={"include_archived": "true"}).json()
        assert body["total"] == 5

    def test_q_is_case_insensitive(self, client):
        body = client.get("/documents", params={"q": "FASTAPI"}).json()
        assert body["total"] == 1
        assert body["items"][0]["title"] == "FastAPI tutorial"

    def test_paging_after_filtering(self, client):
        body = client.get("/documents", params={"limit": 2, "offset": 1}).json()
        assert body["total"] == 4
        assert [d["id"] for d in body["items"]] == [2, 3]

    def test_bad_limit_type_gives_422(self, client):
        assert client.get("/documents", params={"limit": "ten"}).status_code == 422


class TestTask4ListQuery:
    def test_any_mode_is_default(self, client):
        body = client.get("/tags/match", params=[("tag", "llm"), ("tag", "pydantic")]).json()
        assert body == {"tags": ["llm", "pydantic"], "mode": "any", "ids": [2, 3, 5]}

    def test_all_mode(self, client):
        body = client.get("/tags/match", params=[("tag", "python"), ("tag", "web"), ("mode", "all")]).json()
        assert body["ids"] == [1, 4]

    def test_tag_is_required(self, client):
        response = client.get("/tags/match")
        assert response.status_code == 422
        assert response.json()["detail"][0]["loc"] == ["query", "tag"]

    def test_invalid_mode_gives_422(self, client):
        assert client.get("/tags/match", params={"tag": "llm", "mode": "some"}).status_code == 422


class TestTask5StatusCodes:
    def test_reindex_is_accepted(self, client):
        response = client.post("/reindex")
        assert response.status_code == 202
        assert response.json() == {"status": "accepted"}

    def test_delete_returns_204_without_body(self, client):
        response = client.delete("/documents/3")
        assert response.status_code == 204
        assert response.content == b""
        assert 3 not in [d["id"] for d in exercise.DOCUMENTS]

    def test_delete_unknown_gives_404_with_detail(self, client):
        response = client.delete("/documents/99")
        assert response.status_code == 404
        assert response.json() == {"detail": "Document 99 not found"}

    def test_delete_twice(self, client):
        assert client.delete("/documents/1").status_code == 204
        assert client.delete("/documents/1").json() == {"detail": "Document 1 not found"}


class TestTask6UsersRouter:
    def test_me_is_not_shadowed_by_user_id(self, client):
        response = client.get("/users/me")
        assert response.status_code == 200
        assert response.json() == {"id": 1, "name": "alice"}

    def test_user_by_id(self, client):
        assert client.get("/users/2").json() == {"id": 2, "name": "bob"}

    def test_unknown_user_gives_404(self, client):
        response = client.get("/users/42")
        assert response.status_code == 404
        assert response.json() == {"detail": "User 42 not found"}

    def test_non_int_user_id_gives_422(self, client):
        assert client.get("/users/abc").status_code == 422

    def test_routes_are_tagged(self, client):
        paths = client.get("/openapi.json").json()["paths"]
        assert paths["/users/me"]["get"]["tags"] == ["users"]
        assert paths["/users/{user_id}"]["get"]["tags"] == ["users"]


class TestTask7VersionedAndHidden:
    def test_health(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_health_hidden_from_openapi(self, client):
        assert client.get("/health").status_code == 200
        assert "/health" not in client.get("/openapi.json").json()["paths"]

    def test_users_under_api_v1(self, client):
        assert client.get("/api/v1/users/me").json() == {"id": 1, "name": "alice"}
        assert client.get("/api/v1/users/2").json() == {"id": 2, "name": "bob"}

    def test_both_prefixes_are_documented(self, client):
        paths = client.get("/openapi.json").json()["paths"]
        assert "/users/{user_id}" in paths
        assert "/api/v1/users/{user_id}" in paths
