"""The key and hotkey routes of the MCP bridge hand the right action to the handler.

The handler is replaced by a recorder; no key is pressed.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import mcp_bridge


@pytest.fixture
def calls(monkeypatch):
    seen = []

    async def recorder(action_type, params):
        seen.append((action_type, params))
        return {"success": True}

    monkeypatch.setitem(mcp_bridge._handler_registry, "_action", {"fn": recorder, "status": "ready"})
    return seen


def test_key_and_hotkey_reach_the_action_handler(calls):
    app = FastAPI()
    app.include_router(mcp_bridge.router, prefix="/api/mcp")
    client = TestClient(app)
    assert client.post("/api/mcp/key", json={"key": "enter"}).json() == {"success": True}
    assert client.post("/api/mcp/hotkey", json={"keys": ["ctrl", "s"]}).json() == {"success": True}
    assert calls == [("press", {"key": "enter"}), ("hotkey", {"keys": "ctrl+s"})]
