"""The shell routes run commands without any login, so they are off by default.

No command is executed here: with the switch on, the handler is replaced by a recorder.
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import create_app
from app.routers import mcp_bridge


def _paths(app):
    return set(app.openapi()["paths"])


def test_shell_router_is_not_mounted_by_default(monkeypatch):
    monkeypatch.delenv("AUTOMATION_UI_ENABLE_SHELL", raising=False)
    paths = _paths(create_app())
    assert not any(path.startswith("/api/shell") for path in paths)
    assert "/api/desktop/screenshot" in paths


def test_shell_router_is_mounted_only_with_the_switch(monkeypatch):
    monkeypatch.setenv("AUTOMATION_UI_ENABLE_SHELL", "1")
    assert "/api/shell/powershell" in _paths(create_app())
    monkeypatch.setenv("AUTOMATION_UI_ENABLE_SHELL", "true")
    assert not any(path.startswith("/api/shell") for path in _paths(create_app()))


def test_bridge_shell_route_refuses_without_the_switch(monkeypatch):
    seen = []

    async def recorder(**kwargs):
        seen.append(kwargs)
        return {"success": True}

    monkeypatch.setitem(mcp_bridge._handler_registry, "shell", {"fn": recorder, "status": "ready"})
    app = FastAPI()
    app.include_router(mcp_bridge.router, prefix="/api/mcp")
    client = TestClient(app)

    monkeypatch.delenv("AUTOMATION_UI_ENABLE_SHELL", raising=False)
    assert client.post("/api/mcp/shell", json={"command": "x"}).status_code == 403
    assert seen == []

    monkeypatch.setenv("AUTOMATION_UI_ENABLE_SHELL", "1")
    assert client.post("/api/mcp/shell", json={"command": "x"}).status_code == 200
    assert [call["command"] for call in seen] == ["x"]
