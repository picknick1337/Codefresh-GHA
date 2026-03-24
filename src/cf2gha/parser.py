from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class ParseError(ValueError):
    pass


def load_codefresh_file(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ParseError("Top-level Codefresh YAML must be a mapping/object")
    return data
