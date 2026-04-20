from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

from agents.orchestrator import build_orchestrator
from config import Settings
from models.deal import Deal


def _load_openai_key_from_dotenv() -> None:
    env_path = Path(".env")
    if os.getenv("OPENAI_API_KEY") or not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        supported_keys = {
            "OPENAI_API_KEY",
            "OPENAI_BASE_URL",
            "BUDGETWINGS_LLM_PROVIDER",
            "BUDGETWINGS_LLM_MODEL",
        }
        if key in supported_keys:
            os.environ.setdefault(key, value.strip().strip('"').strip("'"))


_load_openai_key_from_dotenv()


@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY is required for the real pipeline e2e test",
)
def test_pipeline_e2e_generates_deals_and_guides(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings()
    orchestrator = build_orchestrator(settings)
    monkeypatch.chdir(tmp_path)

    deals = asyncio.run(orchestrator.run(city="深圳", persona_type="worker", top_n=3))

    assert isinstance(deals, list)
    assert deals
    assert all(isinstance(deal, Deal) for deal in deals)

    guide_files = list(Path("data/guides").glob("*.md"))
    assert guide_files
    assert all(path.read_text(encoding="utf-8").strip() for path in guide_files)
