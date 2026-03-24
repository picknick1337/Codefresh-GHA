from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class ParseError(ValueError):
    pass


def load_codefresh_file(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return load_codefresh_text(handle.read())


def load_codefresh_text(text: str) -> dict[str, Any]:
    try:
        data = yaml.safe_load(text) or {}
    except yaml.YAMLError as exc:
        raise ParseError(str(exc)) from exc
    if not isinstance(data, dict):
        raise ParseError("Top-level Codefresh YAML must be a mapping/object")
    return data
