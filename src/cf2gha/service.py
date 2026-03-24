from __future__ import annotations

from typing import Any

from .emitter import dump_yaml
from .models import StepTranslation, StepWarning, TranslationResult, TranslationWarning
from .parser import load_codefresh_text
from .translator import translate_pipeline


def translate_codefresh_yaml(
    source_yaml: str,
    workflow_name: str = "Converted from Codefresh",
    step_overrides: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    pipeline = load_codefresh_text(source_yaml)
    result = translate_pipeline(pipeline, workflow_name=workflow_name, step_overrides=step_overrides)
    return serialize_result(result)



def serialize_result(result: TranslationResult) -> dict[str, Any]:
    return {
        "workflow": result.workflow,
        "workflow_yaml": dump_yaml(result.workflow),
        "warnings": [_serialize_warning(warning) for warning in result.warnings],
        "steps": [_serialize_step(step) for step in result.steps],
        "checklist": list(result.checklist),
        "source_summary": dict(result.source_summary),
    }



def _serialize_warning(warning: TranslationWarning) -> dict[str, Any]:
    return {
        "code": warning.code,
        "message": warning.message,
        "step": warning.step,
        "severity": warning.severity,
        "suggestion": warning.suggestion,
    }



def _serialize_step(step: StepTranslation) -> dict[str, Any]:
    return {
        "source_name": step.source_name,
        "step_type": step.step_type,
        "stage": step.stage,
        "source_image": step.source_image,
        "gha_step": step.gha_step,
        "rationale": list(step.rationale),
        "checklist": list(step.checklist),
        "warnings": [_serialize_step_warning(warning) for warning in step.warnings],
        "detected_tools": list(step.detected_tools),
        "translation_hints": list(step.translation_hints),
        "special_handling": list(step.special_handling),
    }



def _serialize_step_warning(warning: StepWarning) -> dict[str, Any]:
    return {
        "code": warning.code,
        "message": warning.message,
        "severity": warning.severity,
        "suggestion": warning.suggestion,
    }
