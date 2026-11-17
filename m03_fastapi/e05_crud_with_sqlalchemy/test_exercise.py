from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from m03_fastapi.e05_crud_with_sqlalchemy.exercise import (
    Dataset,
    DatasetCreate,
    DatasetOut,
    DatasetUpdate,
    create_app,
    get_session,
)

WIKI = {"name": "wiki-dump", "description": "English Wikipedia", "kind": "text", "row_count": 1000}
SALES = {"name": "sales-2024", "kind": "tabular", "row_count": 52}
FACES = {"name": "faces", "kind": "image"}


@pytest.fixture
def client():
    with TestClient(create_app()) as c:  # fresh in-memory database per test
        yield c


@pytest.fixture
def seeded(client):
    for payload in (WIKI, SALES, FACES, {"name": "wiki-fr", "kind": "text"}):
        client.post("/datasets", json=payload)  # no assert here: a fixture must not fail
    return client


class TestTask1Schemas:
    def test_create_defaults(self):
        ds = DatasetCreate(name="x", kind="text")
        assert ds.description is None
        assert ds.row_count == 0

    @pytest.mark.parametrize(
        "payload",
        [
            {"name": "", "kind": "text"},
            {"name": "x" * 101, "kind": "text"},
            {"name": "x", "kind": "audio"},
            {"name": "x", "kind": "text", "row_count": -1},
            {"name": "x", "kind": "text", "description": "d" * 501},
        ],
    )
    def test_create_rejects(self, payload):
        with pytest.raises(ValidationError):
            DatasetCreate(**payload)

    def test_update_tracks_unset_fields(self):
        assert DatasetUpdate(description=None).model_dump(exclude_unset=True) == {"description": None}
        assert DatasetUpdate().model_dump(exclude_unset=True) == {}

    @pytest.mark.parametrize("field", ["name", "kind", "row_count"])
    def test_update_rejects_explicit_null_for_not_null_columns(self, field):
        with pytest.raises(ValidationError):
            DatasetUpdate.model_validate({field: None})

    def test_out_from_orm_object(self):
        orm = Dataset(id=7, name="n", description=None, kind="image", row_count=3)
        assert DatasetOut.model_validate(orm).model_dump() == {
            "id": 7,
            "name": "n",
            "description": None,
            "kind": "image",
            "row_count": 3,
        }


class _FakeSessionmaker:
    def __init__(self):
        self.events: list[str] = []
        self.session = object()

    def __call__(self):
        return self

    def __enter__(self):
        self.events.append("enter")
        return self.session

    def __exit__(self, exc_type, exc, tb):
        self.events.append(f"exit:{exc_type.__name__ if exc_type else None}")
        return False


def _fake_request(sessionmaker):
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(sessionmaker=sessionmaker)))


class TestTask2SessionDependency:
    def test_yields_session_and_closes(self):
        maker = _FakeSessionmaker()
        gen = get_session(_fake_request(maker))
        assert next(gen) is maker.session
        assert maker.events == ["enter"]
        with pytest.raises(StopIteration):
            next(gen)
        assert maker.events == ["enter", "exit:None"]

    def test_closes_on_error(self):
        maker = _FakeSessionmaker()
        gen = get_session(_fake_request(maker))
        next(gen)
        with pytest.raises(ValueError):
            gen.throw(ValueError("endpoint failed"))
        assert maker.events == ["enter", "exit:ValueError"]


class TestTask3Create:
    def test_returns_201_with_id(self, client):
        response = client.post("/datasets", json=WIKI)
        assert response.status_code == 201
        assert response.json() == {"id": 1, **WIKI}

    def test_defaults_are_applied(self, client):
        assert client.post("/datasets", json=FACES).json() == {
            "id": 1,
            "name": "faces",
            "description": None,
            "kind": "image",
            "row_count": 0,
        }

    def test_duplicate_name_gives_409(self, client):
        client.post("/datasets", json=WIKI)
        response = client.post("/datasets", json={**WIKI, "kind": "tabular"})
        assert response.status_code == 409
        assert response.json() == {"detail": "Dataset 'wiki-dump' already exists"}

    def test_session_usable_after_conflict(self, client):
        client.post("/datasets", json=WIKI)
        client.post("/datasets", json=WIKI)
        assert client.post("/datasets", json=SALES).json()["id"] == 2

    def test_invalid_body_gives_422(self, client):
        assert client.post("/datasets", json={"name": "x", "kind": "audio"}).status_code == 422


class TestTask4ReadOne:
    def test_read(self, seeded):
        assert seeded.get("/datasets/2").json() == {"id": 2, "description": None, **SALES}

    def test_missing_gives_404(self, seeded):
        response = seeded.get("/datasets/99")
        assert response.status_code == 404
        assert response.json() == {"detail": "Dataset 99 not found"}

    def test_bad_id_gives_422(self, seeded):
        assert seeded.get("/datasets/abc").status_code == 422


class TestTask5List:
    def test_all(self, seeded):
        body = seeded.get("/datasets").json()
        assert body["total"] == 4
        assert [d["name"] for d in body["items"]] == ["wiki-dump", "sales-2024", "faces", "wiki-fr"]

    def test_filter_by_kind(self, seeded):
        body = seeded.get("/datasets", params={"kind": "text"}).json()
        assert body["total"] == 2
        assert [d["id"] for d in body["items"]] == [1, 4]

    def test_search_is_case_insensitive(self, seeded):
        body = seeded.get("/datasets", params={"q": "WIKI"}).json()
        assert [d["name"] for d in body["items"]] == ["wiki-dump", "wiki-fr"]

    def test_wildcards_are_literal(self, seeded):
        assert seeded.get("/datasets", params={"q": "%"}).json() == {"total": 0, "items": []}

    def test_total_ignores_pagination(self, seeded):
        body = seeded.get("/datasets", params={"limit": 2, "offset": 1}).json()
        assert body["total"] == 4
        assert [d["id"] for d in body["items"]] == [2, 3]

    @pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"offset": -1}, {"kind": "audio"}])
    def test_bad_params_give_422(self, seeded, params):
        assert seeded.get("/datasets", params=params).status_code == 422


class TestTask6PartialUpdate:
    def test_only_sent_fields_change(self, seeded):
        response = seeded.patch("/datasets/1", json={"row_count": 2000})
        assert response.status_code == 200
        assert response.json() == {"id": 1, **WIKI, "row_count": 2000}

    def test_explicit_null_clears_description(self, seeded):
        body = seeded.patch("/datasets/1", json={"description": None}).json()
        assert body["description"] is None
        assert body["name"] == "wiki-dump"
        assert seeded.get("/datasets/1").json()["description"] is None

    def test_null_name_gives_422(self, seeded):
        assert seeded.patch("/datasets/1", json={"name": None}).status_code == 422

    def test_rename_conflict_gives_409(self, seeded):
        response = seeded.patch("/datasets/1", json={"name": "faces"})
        assert response.status_code == 409
        assert response.json() == {"detail": "Dataset 'faces' already exists"}
        assert seeded.get("/datasets/1").json()["name"] == "wiki-dump"

    def test_missing_gives_404(self, seeded):
        response = seeded.patch("/datasets/99", json={"row_count": 1})
        assert response.status_code == 404
        assert response.json() == {"detail": "Dataset 99 not found"}


class TestTask7Delete:
    def test_delete_returns_204(self, seeded):
        response = seeded.delete("/datasets/2")
        assert response.status_code == 204
        assert response.content == b""

    def test_deleted_is_gone(self, seeded):
        seeded.delete("/datasets/2")
        assert seeded.get("/datasets/2").status_code == 404
        assert seeded.get("/datasets").json()["total"] == 3

    def test_missing_gives_404(self, seeded):
        response = seeded.delete("/datasets/99")
        assert response.status_code == 404
        assert response.json() == {"detail": "Dataset 99 not found"}

    def test_name_can_be_reused_after_delete(self, seeded):
        seeded.delete("/datasets/1")
        assert seeded.post("/datasets", json=WIKI).status_code == 201
