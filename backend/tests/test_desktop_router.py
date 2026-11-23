"""The desktop routes the VibeMind app polls: monitor list, status, per-monitor picture.

They run against the real screen (reading only) through a small app that mounts just
this router, so no other service of the backend is started.
"""

import base64
import io
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from app.routers.desktop import router
from app.services.desktop_service import LiveDesktopService


@pytest.fixture(scope="module")
def client():
    service = LiveDesktopService()
    service.initialized = True
    app = FastAPI()
    app.state.service_manager = SimpleNamespace(get_service=lambda name: service)
    app.include_router(router, prefix="/api/desktop")
    return TestClient(app)


def test_monitors_lists_real_monitors_with_geometry(client):
    response = client.get("/api/desktop/monitors")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == len(body["monitors"]) >= 1
    first = body["monitors"][0]
    assert first["index"] == 1 and first["primary"] is True
    assert first["geometry"]["width"] > 0 and first["geometry"]["height"] > 0


def test_status_answers_instead_of_500(client):
    response = client.get("/api/desktop/status")
    assert response.status_code == 200
    assert response.json()["capture_available"] is True


def test_screen_info_matches_the_monitor_list(client):
    monitors = client.get("/api/desktop/monitors").json()["monitors"]
    info = client.get("/api/desktop/screen-info").json()
    assert info["monitors"] == monitors
    assert info["resolution"]["width"] == monitors[0]["geometry"]["width"]


def test_screenshot_is_a_jpeg_of_the_asked_monitor(client):
    geometry = client.get("/api/desktop/monitors").json()["monitors"][0]["geometry"]
    shot = client.get("/api/desktop/screenshot?monitor=1").json()["screenshot"]
    assert shot["format"] == "jpeg" and shot["monitor"] == 1
    image = Image.open(io.BytesIO(base64.b64decode(shot["data"])))
    assert image.format == "JPEG"
    assert image.size == (shot["width"], shot["height"])
    assert image.size == (geometry["width"], geometry["height"])


def test_monitor_zero_means_the_primary_monitor(client):
    shot = client.get("/api/desktop/screenshot?monitor=0").json()["screenshot"]
    assert shot["monitor"] == 1


def test_unknown_monitor_is_404(client):
    assert client.get("/api/desktop/screenshot?monitor=99").status_code == 404


def test_task_route_returns_the_latest_journal_entry(client, tmp_path, monkeypatch):
    monkeypatch.setenv("VIBEMIND_DESKTOP_AUFGABEN_DIR", str(tmp_path))
    assert client.get("/api/desktop/task").json() == {"success": True, "task": None, "stopped": False}
    (tmp_path / "dt-20260101-000000-aaaaaa.json").write_text('{"id": "old"}', encoding="utf-8")
    (tmp_path / "dt-20260102-000000-bbbbbb.json").write_text('{"id": "new"}', encoding="utf-8")
    (tmp_path / "dt-evil.json").write_text('{"id": "ignored"}', encoding="utf-8")
    (tmp_path / "STOP").write_text("", encoding="utf-8")
    body = client.get("/api/desktop/task").json()
    assert body["task"] == {"id": "new"} and body["stopped"] is True
