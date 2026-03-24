from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TranslationWarning:
    code: str
    message: str
    step: str | None = None


@dataclass
class TranslationResult:
    workflow: dict[str, Any]
    warnings: list[TranslationWarning] = field(default_factory=list)
