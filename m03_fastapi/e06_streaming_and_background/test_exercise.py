import json

import httpx
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from m03_fastapi.e06_streaming_and_background import exercise
from m03_fastapi.e06_streaming_and_background.exercise import create_app, format_sse


@pytest.fixture(autouse=True)
def _reset_state():
    exercise.INDEX_LOG.clear()
    exercise.FETCH_STATS.update(in_flight=0, max_in_flight=0, calls=0)
    yield
    exercise.INDEX_LOG.clear()


@pytest.fixture
def client():
    return TestClient(create_app())


def parse_sse(raw: str) -> list[dict[str, str]]:
    """Minimal SSE parser: one dict per event, data lines joined with newlines."""
    events = []
    for block in raw.split("\n\n"):
        if not block.strip():
            continue
        event: dict[str, str] = {}
        data_lines = []
        for line in block.split("\n"):
            field, _, value = line.partition(": ")
            if field == "data":
                data_lines.append(value)
            elif field:
                event[field] = value
        event["data"] = "\n".join(data_lines)
        events.append(event)
    return events


class TestTask1PlainStreaming:
    def test_streams_lines(self, client):
        with client.stream("GET", "/count", params={"n": 3}) as response:
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/plain")
            assert list(response.iter_lines()) == ["1", "2", "3"]

    def test_full_body(self, client):
        assert client.get("/count", params={"n": 5}).text == "1\n2\n3\n4\n5\n"

    @pytest.mark.parametrize("n", [0, 101])
    def test_bounds(self, client, n):
        assert client.get("/count", params={"n": n}).status_code == 422

    async def test_with_async_client(self):
        transport = httpx.ASGITransport(app=create_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            async with ac.stream("GET", "/count", params={"n": 2}) as response:
                chunks = [chunk async for chunk in response.aiter_text()]
        assert "".join(chunks) == "1\n2\n"


class TestTask2FormatSse:
    def test_data_only(self):
        assert format_sse("hi") == "data: hi\n\n"

    def test_all_fields_in_order(self):
        assert format_sse("x", event="done", id="7") == "id: 7\nevent: done\ndata: x\n\n"

    def test_multiline_data(self):
        assert format_sse("a\nb") == "data: a\ndata: b\n\n"

    def test_empty_data(self):
        assert format_sse("") == "data: \n\n"


class TestTask3ManualSse:
    def test_headers(self, client):
        with client.stream("POST", "/chat/stream", json={"prompt": "hi"}) as response:
            assert response.headers["content-type"].startswith("text/event-stream")
            assert response.headers["cache-control"] == "no-cache"
            assert response.headers["x-accel-buffering"] == "no"

    def test_tokens_rebuild_the_reply(self, client):
        with client.stream("POST", "/chat/stream", json={"prompt": "hello big world"}) as response:
            events = parse_sse(response.read().decode())
        tokens = [json.loads(e["data"])["token"] for e in events[:-1]]
        assert tokens == ["Echo:", " hello", " big", " world"]
        assert "".join(tokens) == "Echo: hello big world"

    def test_done_event_last(self, client):
        events = parse_sse(client.post("/chat/stream", json={"prompt": "x"}).text)
        assert events[-1] == {"event": "done", "data": "[DONE]"}
        assert all("event" not in e for e in events[:-1])

    def test_empty_prompt_gives_422(self, client):
        assert client.post("/chat/stream", json={"prompt": ""}).status_code == 422


class TestTask4BuiltinSse:
    def test_events(self, client):
        with client.stream("GET", "/chat/events", params={"prompt": "hi there"}) as response:
            assert response.headers["content-type"].startswith("text/event-stream")
            events = parse_sse(response.read().decode())
        assert [e["event"] for e in events] == ["token", "token", "token", "done"]
        assert [e.get("id") for e in events[:3]] == ["0", "1", "2"]
        assert json.loads(events[1]["data"]) == {"token": " hi"}

    def test_done_is_raw(self, client):
        events = parse_sse(client.get("/chat/events", params={"prompt": "x"}).text)
        assert events[-1]["data"] == "[DONE]"  # not '"[DONE]"'

    def test_prompt_required(self, client):
        assert client.get("/chat/events").status_code == 422


class TestTask5BackgroundTasks:
    def test_jobs_functions_directly(self):
        exercise.index_document("d0", "a b  c")
        assert exercise.INDEX_LOG == ["indexed:d0:3"]

    def test_accepted_and_tasks_ran_in_order(self, client):
        response = client.post("/documents", json={"id": "d1", "text": "hello brave new world"})
        assert response.status_code == 202
        assert response.json() == {"id": "d1", "status": "queued"}
        assert exercise.INDEX_LOG == ["indexed:d1:4", "notified:d1"]

    def test_each_request_schedules_its_own_tasks(self, client):
        client.post("/documents", json={"id": "a", "text": "x"})
        client.post("/documents", json={"id": "b", "text": "y z"})
        assert exercise.INDEX_LOG == ["indexed:a:1", "notified:a", "indexed:b:2", "notified:b"]

    def test_invalid_body_schedules_nothing(self, client):
        assert client.post("/documents", json={"id": "x"}).status_code == 422
        assert exercise.INDEX_LOG == []


class TestTask6ConcurrentCalls:
    def test_results_in_request_order(self, client):
        body = client.get("/enrich", params=[("id", 3), ("id", 1)]).json()
        assert body == {"items": [exercise.METADATA[3], exercise.METADATA[1]], "missing": []}

    def test_missing_ids(self, client):
        body = client.get("/enrich", params=[("id", 2), ("id", 99)]).json()
        assert body["items"] == [exercise.METADATA[2]]
        assert body["missing"] == [99]

    def test_calls_run_concurrently(self, client):
        client.get("/enrich", params=[("id", 1), ("id", 2), ("id", 3)])
        assert exercise.FETCH_STATS["calls"] == 3
        assert exercise.FETCH_STATS["max_in_flight"] == 3

    def test_at_least_one_id(self, client):
        assert client.get("/enrich").status_code == 422


class TestTask7StreamedUpload:
    def _upload(self, client, content: bytes, content_type="text/plain", **headers):
        return client.post("/files/stats", content=content, headers={"Content-Type": content_type, **headers})

    def test_stats(self, client):
        response = self._upload(client, b"line one\nline two\nthree", **{"X-Filename": "notes.txt"})
        assert response.status_code == 200
        assert response.json() == {"filename": "notes.txt", "size_bytes": 23, "lines": 3}

    def test_trailing_newline_and_default_name(self, client):
        assert self._upload(client, b"a\nb\n").json() == {"filename": "upload.txt", "size_bytes": 4, "lines": 2}

    def test_chunked_body(self, client):
        def chunks():
            yield b"ab\n"
            yield b"cd"

        assert self._upload(client, chunks()).json()["lines"] == 2

    def test_rejects_non_text(self, client):
        response = self._upload(client, b"\x89PNG", content_type="image/png")
        assert response.status_code == 415
        assert response.json() == {"detail": "Only text/* uploads are supported"}

    def test_rejects_empty_and_too_large(self, client):
        assert self._upload(client, b"").json() == {"detail": "Empty upload"}
        response = self._upload(client, b"x" * (exercise.MAX_UPLOAD_BYTES + 1))
        assert response.status_code == 413
        assert response.json() == {"detail": f"Upload exceeds {exercise.MAX_UPLOAD_BYTES} bytes"}


class TestTask8WebSocket:
    URL = "/ws/chat?token=secret"

    def test_echo_counts_messages(self, client):
        with client.websocket_connect(self.URL) as ws:
            ws.send_json({"type": "message", "text": "hi"})
            assert ws.receive_json() == {"type": "echo", "text": "hi", "n": 1}
            ws.send_json({"type": "ping"})
            assert ws.receive_json() == {"type": "pong"}
            ws.send_json({"type": "message", "text": "again"})
            assert ws.receive_json() == {"type": "echo", "text": "again", "n": 2}

    def test_unknown_type_keeps_connection(self, client):
        with client.websocket_connect(self.URL) as ws:
            ws.send_json({"type": "dance"})
            assert ws.receive_json() == {"type": "error", "detail": "unknown message type"}
            ws.send_json({"type": "ping"})
            assert ws.receive_json() == {"type": "pong"}

    def test_bye_closes_normally(self, client):
        with client.websocket_connect(self.URL) as ws:
            ws.send_json({"type": "bye"})
            with pytest.raises(WebSocketDisconnect) as info:
                ws.receive_json()
        assert info.value.code == 1000

    @pytest.mark.parametrize("url", ["/ws/chat", "/ws/chat?token=wrong"])
    def test_bad_token_rejected(self, client, url):
        with pytest.raises(WebSocketDisconnect) as info, client.websocket_connect(url):
            pass
        assert info.value.code == 1008
