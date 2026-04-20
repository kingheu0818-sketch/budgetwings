from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from models.guide import GuideTemplate


def load_guide_template(path: Path) -> GuideTemplate:
    raw_data: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw_data, dict):
        msg = f"guide template must be a YAML mapping: {path}"
        raise ValueError(msg)
    return GuideTemplate.model_validate(raw_data)
