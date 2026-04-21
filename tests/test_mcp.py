from __future__ import annotations

import pytest

from config import Settings
from mcp_server import server as server_module


@pytest.fixture(autouse=True)
def disable_knowledge_base(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server_module.MCPServices, "_build_knowledge_base", lambda self: None)


def test_create_server_registers_expected_tools() -> None:
    settings = Settings()

    server = server_module.create_server(settings=settings)

    tool_names = set(server._tool_manager._tools.keys())
    assert tool_names == {
        "search_deals",
        "get_guide",
        "price_trend",
        "visa_check",
        "weather_check",
    }


def test_create_server_raises_when_mcp_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server_module, "mcp_server_module", None)

    with pytest.raises(RuntimeError, match="mcp library is not installed"):
        server_module.create_server(settings=Settings())
