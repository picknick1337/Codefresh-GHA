from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TranslationWarning:
    code: str
    message: str
    step: str | None = None
    severity: str = "warning"
    suggestion: str | None = None


@dataclass
class StepWarning:
    code: str
    message: str
    severity: str = "warning"
    suggestion: str | None = None


@dataclass
class StepTranslation:
    source_name: str
    step_type: str
    stage: str | None
    source_image: str | None
    gha_step: dict[str, Any]
    rationale: list[str] = field(default_factory=list)
    checklist: list[str] = field(default_factory=list)
    warnings: list[StepWarning] = field(default_factory=list)
    detected_tools: list[str] = field(default_factory=list)
    translation_hints: list[str] = field(default_factory=list)
    special_handling: list[str] = field(default_factory=list)


@dataclass
class TranslationResult:
    workflow: dict[str, Any]
    warnings: list[TranslationWarning] = field(default_factory=list)
    steps: list[StepTranslation] = field(default_factory=list)
    checklist: list[str] = field(default_factory=list)
    source_summary: dict[str, Any] = field(default_factory=dict)
