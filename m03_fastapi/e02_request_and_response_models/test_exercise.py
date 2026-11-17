import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from m03_fastapi.e02_request_and_response_models.exercise import (
    ChatMessage,
    ChatRequest,
    UserIn,
    UserOut,
    create_app,
    hash_password,
    store,
)

ALICE = {"username": "alice", "email": "alice@example.com", "password": "correct-horse", "full_name": "Alice A."}
BOB = {"username": "bob", "email": "bob@example.com", "password": "battery-staple"}


@pytest.fixture(autouse=True)
def _clean_store():
    store.clear()
    yield
    store.clear()


@pytest.fixture
def client():
    return TestClient(create_app())


@pytest.fixture
def seeded(client):
    """Create alice (id 1) and bob (id 2) directly in the store."""
    store.add(username="alice", email="alice@example.com", password="correct-horse", full_name="Alice A.")
    store.add(username="bob", email="bob@example.com", password="battery-staple", full_name=None)
    return client


class TestTask1Schemas:
    def test_valid_user_in(self):
        user = UserIn(**ALICE)
        assert user.username == "alice"
        assert user.password.get_secret_value() == "correct-horse"
        assert "correct-horse" not in repr(user)

    @pytest.mark.parametrize(
        ("field", "value"),
        [("username", "al"), ("username", "Alice!"), ("username", "a" * 33), ("email", "not-an-email"), ("password", "short")],
    )
    def test_invalid_user_in(self, field, value):
        with pytest.raises(ValidationError) as info:
            UserIn(**{**ALICE, field: value})
        assert info.value.errors()[0]["loc"] == (field,)

    def test_full_name_is_optional(self):
        assert UserIn(**BOB).full_name is None

    def test_user_out_has_no_password_field(self):
        assert set(UserOut.model_fields) == {"id", "username", "email", "full_name"}


class TestTask2CreateUser:
    def test_returns_201_without_password(self, client):
        response = client.post("/users", json=ALICE)
        assert response.status_code == 201
        assert response.json() == {"id": 1, "username": "alice", "email": "alice@example.com", "full_name": "Alice A."}

    def test_location_header(self, client):
        client.post("/users", json=ALICE)
        assert client.post("/users", json=BOB).headers["location"] == "/users/2"

    def test_password_is_stored_hashed(self, client):
        client.post("/users", json=ALICE)
        assert store.get(1).hashed_password == hash_password("correct-horse")

    def test_duplicate_username_gives_409(self, client):
        client.post("/users", json=ALICE)
        response = client.post("/users", json={**ALICE, "email": "other@example.com"})
        assert response.status_code == 409
        assert response.json() == {"detail": "Username 'alice' is already taken"}

    def test_invalid_body_gives_422_with_location(self, client):
        response = client.post("/users", json={**ALICE, "password": "short"})
        assert response.status_code == 422
        assert response.json()["detail"][0]["loc"] == ["body", "password"]
        assert store.all() == []


class TestTask3ReadUser:
    def test_read_existing(self, seeded):
        assert seeded.get("/users/1").json() == {
            "id": 1,
            "username": "alice",
            "email": "alice@example.com",
            "full_name": "Alice A.",
        }

    def test_none_fields_are_excluded(self, seeded):
        body = seeded.get("/users/2").json()
        assert body["username"] == "bob"
        assert "full_name" not in body

    def test_unknown_gives_404(self, seeded):
        response = seeded.get("/users/99")
        assert response.status_code == 404
        assert response.json() == {"detail": "User 99 not found"}

    def test_path_constraint(self, seeded):
        response = seeded.get("/users/0")
        assert response.status_code == 422
        assert response.json()["detail"][0]["type"] == "greater_than_equal"


class TestTask4ListUsers:
    def test_lists_all_ordered_by_id(self, seeded):
        body = seeded.get("/users").json()
        assert [u["username"] for u in body] == ["alice", "bob"]
        assert body[1]["full_name"] is None
        assert all("hashed_password" not in u for u in body)

    def test_filter_and_limit(self, seeded):
        store.add(username="bobby", email="bobby@example.com", password="x" * 8, full_name=None)
        assert [u["username"] for u in seeded.get("/users", params={"q": "bob"}).json()] == ["bob", "bobby"]
        assert [u["username"] for u in seeded.get("/users", params={"limit": 1}).json()] == ["alice"]

    @pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"q": "x" * 51}])
    def test_query_constraints(self, seeded, params):
        response = seeded.get("/users", params=params)
        assert response.status_code == 422
        assert response.json()["detail"][0]["loc"][0] == "query"

    def test_empty_list(self, client):
        response = client.get("/users")
        assert response.status_code == 200
        assert response.json() == []


class TestTask5ChangePassword:
    def test_success_returns_204(self, seeded):
        response = seeded.post("/users/1/password", json={"old_password": "correct-horse", "new_password": "new-secret-1"})
        assert response.status_code == 204
        assert store.get(1).hashed_password == hash_password("new-secret-1")

    def test_wrong_old_password_gives_403(self, seeded):
        response = seeded.post("/users/1/password", json={"old_password": "nope", "new_password": "new-secret-1"})
        assert response.status_code == 403
        assert response.json() == {"detail": "Old password is incorrect"}
        assert store.get(1).hashed_password == hash_password("correct-horse")

    def test_unknown_user_gives_404(self, seeded):
        response = seeded.post("/users/9/password", json={"old_password": "a", "new_password": "new-secret-1"})
        assert response.status_code == 404
        assert response.json() == {"detail": "User 9 not found"}

    def test_both_fields_are_body_keys(self, seeded):
        response = seeded.post("/users/1/password", json={"old_password": "correct-horse", "new_password": "short"})
        assert response.status_code == 422
        assert response.json()["detail"][0]["loc"] == ["body", "new_password"]


class TestTask6ChatModels:
    def test_valid_request_with_defaults(self):
        req = ChatRequest(messages=[{"role": "user", "content": "hi"}])
        assert req.model == "fake-gpt"
        assert req.temperature == 0.7
        assert req.max_tokens is None
        assert isinstance(req.messages[0], ChatMessage)

    @pytest.mark.parametrize(
        "payload",
        [
            {"messages": []},
            {"messages": [{"role": "robot", "content": "hi"}]},
            {"messages": [{"role": "user", "content": ""}]},
            {"messages": [{"role": "user", "content": "hi"}], "temperature": 2.5},
            {"messages": [{"role": "user", "content": "hi"}], "max_tokens": 0},
        ],
    )
    def test_invalid_requests(self, payload):
        with pytest.raises(ValidationError):
            ChatRequest(**payload)

    def test_temperature_bounds_are_inclusive(self):
        assert ChatRequest(messages=[{"role": "user", "content": "x"}], temperature=2.0).temperature == 2.0


class TestTask7ChatCompletions:
    def test_reply_and_usage(self, client):
        payload = {
            "model": "tiny",
            "messages": [
                {"role": "system", "content": "be brief"},
                {"role": "user", "content": "hello there"},
            ],
        }
        response = client.post("/chat/completions", json=payload)
        assert response.status_code == 200
        assert response.json() == {
            "model": "tiny",
            "message": {"role": "assistant", "content": "You said: hello there"},
            "usage": {"prompt_tokens": 4, "completion_tokens": 4, "total_tokens": 8},
        }

    def test_uses_last_user_message(self, client):
        payload = {
            "messages": [
                {"role": "user", "content": "first"},
                {"role": "assistant", "content": "ok"},
                {"role": "user", "content": "second"},
            ]
        }
        assert client.post("/chat/completions", json=payload).json()["message"]["content"] == "You said: second"

    def test_max_tokens_truncates(self, client):
        payload = {"messages": [{"role": "user", "content": "one two three four"}], "max_tokens": 3}
        body = client.post("/chat/completions", json=payload).json()
        assert body["message"]["content"] == "You said: one"
        assert body["usage"]["completion_tokens"] == 3

    def test_no_user_message_gives_400(self, client):
        response = client.post("/chat/completions", json={"messages": [{"role": "system", "content": "x"}]})
        assert response.status_code == 400
        assert response.json() == {"detail": "At least one user message is required"}

    def test_invalid_body_gives_422(self, client):
        response = client.post("/chat/completions", json={"messages": []})
        assert response.status_code == 422
        assert response.json()["detail"][0]["loc"] == ["body", "messages"]
