import re

import pytest
from fastapi.testclient import TestClient

from m03_fastapi.e04_errors_middleware_lifespan import exercise
from m03_fastapi.e04_errors_middleware_lifespan.exercise import FakeLLMClient, create_app

FRONTEND = "https://app.example.com"


@pytest.fixture(autouse=True)
def _reset_lifecycle():
    exercise.LIFECYCLE_EVENTS.clear()
    yield
    exercise.LIFECYCLE_EVENTS.clear()


@pytest.fixture
def client():
    with TestClient(create_app()) as c:
        yield c


class TestTask1HTTPExceptionHeaders:
    def test_valid_token(self, client):
        response = client.get("/protected", headers={"Authorization": "Bearer secret-token"})
        assert response.status_code == 200
        assert response.json() == {"ok": True}

    @pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer nope"}, {"Authorization": "secret-token"}])
    def test_rejected_with_www_authenticate(self, client, headers):
        response = client.get("/protected", headers=headers)
        assert response.status_code == 401
        assert response.json() == {"detail": "Not authenticated"}
        assert response.headers["www-authenticate"] == "Bearer"


class TestTask2DomainErrorHandler:
    def test_not_found_envelope(self, client):
        response = client.get("/documents/99")
        assert response.status_code == 404
        assert response.json() == {"error": {"code": "not_found", "message": "Document 99 not found"}}

    def test_subclass_headers_are_forwarded(self, client):
        response = client.post("/generate/acme")
        assert response.status_code == 429
        assert response.json()["error"]["code"] == "quota_exceeded"
        assert response.headers["retry-after"] == "60"

    def test_message_comes_from_exception(self, client):
        response = client.post("/generate/acme")
        assert response.json()["error"]["message"] == "Tenant 'acme' is out of tokens"
        assert client.post("/generate/globex").json() == {"tenant": "globex", "status": "generated"}

    async def test_handler_directly(self):
        response = await exercise.domain_error_handler(None, exercise.DomainError("nope"))
        assert response.status_code == 400
        assert response.body == b'{"error":{"code":"domain_error","message":"nope"}}'


class TestTask3ValidationHandler:
    def test_query_errors(self, client):
        response = client.get("/search", params={"q": "x", "limit": 0})
        assert response.status_code == 422
        error = response.json()["error"]
        assert error["code"] == "validation_error"
        assert error["message"] == "Request validation failed"
        assert [d["field"] for d in error["details"]] == ["query.q", "query.limit"]
        assert "at least 2" in error["details"][0]["message"]

    def test_missing_required(self, client):
        details = client.get("/search").json()["error"]["details"]
        assert details == [{"field": "query.q", "message": "Field required"}]

    def test_body_errors(self, client):
        response = client.post("/complete", json={"template": "summarize", "text": ""})
        assert response.status_code == 422
        assert response.json()["error"]["details"][0]["field"] == "body.text"


class TestTask4UnhandledErrors:
    def test_500_envelope_without_leaking(self):
        with TestClient(create_app(), raise_server_exceptions=False) as client:
            response = client.get("/crash")
        assert response.status_code == 500
        assert response.json() == {"error": {"code": "internal_error", "message": "Internal server error"}}
        assert "hunter2" not in response.text

    async def test_handler_directly(self):
        response = await exercise.unhandled_error_handler(None, KeyError("secret"))
        assert response.status_code == 500
        assert b"secret" not in response.body


class TestTask5RequestContextMiddleware:
    def test_generates_request_id(self, client):
        response = client.get("/request-id")
        request_id = response.headers["x-request-id"]
        assert re.fullmatch(r"[0-9a-f]{32}", request_id)
        assert response.json() == {"request_id": request_id}

    def test_propagates_valid_incoming_id(self, client):
        response = client.get("/request-id", headers={"X-Request-ID": "trace-abc_123"})
        assert response.headers["x-request-id"] == "trace-abc_123"
        assert response.json() == {"request_id": "trace-abc_123"}

    @pytest.mark.parametrize("bad", ["has space", "x" * 65, "semi;colon"])
    def test_replaces_invalid_incoming_id(self, client, bad):
        response = client.get("/request-id", headers={"X-Request-ID": bad})
        assert response.headers["x-request-id"] != bad
        assert re.fullmatch(r"[0-9a-f]{32}", response.headers["x-request-id"])

    def test_process_time_header(self, client):
        value = client.get("/documents/1").headers["x-process-time"]
        assert re.fullmatch(r"\d+\.\d{2}", value)

    def test_error_responses_get_headers_too(self, client):
        response = client.get("/documents/99", headers={"X-Request-ID": "req-1"})
        assert response.status_code == 404
        assert response.headers["x-request-id"] == "req-1"


class TestTask6Lifespan:
    def test_startup_populates_state(self, client):
        assert exercise.LIFECYCLE_EVENTS == ["startup"]
        assert isinstance(client.app.state.llm, FakeLLMClient)
        assert set(client.app.state.prompts) == {"summarize", "translate"}

    def test_endpoint_uses_state(self, client):
        response = client.post("/complete", json={"template": "translate", "text": "hello"})
        assert response.json() == {"completion": "[fake-1] Translate to French: hello"}

    def test_unknown_template_uses_domain_error(self, client):
        response = client.post("/complete", json={"template": "poem", "text": "x"})
        assert response.status_code == 404
        assert response.json()["error"]["message"] == "Prompt template 'poem' not found"

    def test_shutdown_closes_client(self):
        app = create_app()
        with TestClient(app):
            llm = app.state.llm
            assert not llm.closed
        assert llm.closed
        assert exercise.LIFECYCLE_EVENTS == ["startup", "shutdown"]


class TestTask7Cors:
    def _preflight(self, client, origin=FRONTEND, method="POST"):
        return client.options(
            "/complete",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": method,
                "Access-Control-Request-Headers": "Content-Type",
            },
        )

    def test_preflight_allowed(self, client):
        response = self._preflight(client)
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == FRONTEND
        assert response.headers["access-control-allow-credentials"] == "true"
        assert response.headers["access-control-max-age"] == "600"

    def test_preflight_unknown_origin_rejected(self, client):
        response = self._preflight(client, origin="https://evil.example")
        assert response.status_code == 400
        assert "access-control-allow-origin" not in response.headers

    def test_preflight_disallowed_method(self, client):
        assert self._preflight(client, method="DELETE").status_code == 400

    def test_simple_request_exposes_headers(self, client):
        response = client.get("/documents/1", headers={"Origin": FRONTEND})
        assert response.headers["access-control-allow-origin"] == FRONTEND
        exposed = {h.strip().lower() for h in response.headers["access-control-expose-headers"].split(",")}
        assert {"x-request-id", "x-process-time"} <= exposed

    def test_custom_origins(self):
        with TestClient(create_app(cors_origins=["http://localhost:5173"])) as client:
            assert self._preflight(client, origin="http://localhost:5173").status_code == 200
            assert self._preflight(client).status_code == 400
