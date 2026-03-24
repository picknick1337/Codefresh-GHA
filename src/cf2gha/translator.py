from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .models import TranslationResult, TranslationWarning

SUPPORTED_SPECIAL_TYPES = {"freestyle", "git-clone", "build", "push"}


def translate_pipeline(data: dict[str, Any], workflow_name: str = "Converted from Codefresh") -> TranslationResult:
    warnings: list[TranslationWarning] = []
    env = _extract_env(data, warnings)
    steps = _extract_steps(data)
    stages = _extract_stage_names(data)

    gha_steps: list[dict[str, Any]] = []
    if any(_step_type(step) == "git-clone" for _, step in steps):
        gha_steps.append({"name": "Checkout repository", "uses": "actions/checkout@v4"})

    for step_name, step_body in steps:
        gha_steps.extend(_translate_step(step_name, step_body, stages, warnings))

    workflow = {
        "name": workflow_name,
        "on": {"workflow_dispatch": None, "push": {"branches": ["main"]}},
        "jobs": {
            "codefresh_migration": {
                "runs-on": "ubuntu-latest",
                "env": env or None,
                "steps": gha_steps,
            }
        },
    }

    _strip_nones(workflow)
    return TranslationResult(workflow=workflow, warnings=warnings)


def _extract_env(data: dict[str, Any], warnings: list[TranslationWarning]) -> dict[str, str]:
    variables = data.get("variables") or {}
    if isinstance(variables, dict):
        return {str(key): _stringify_value(value) for key, value in variables.items()}

    if isinstance(variables, list):
        env: dict[str, str] = {}
        for item in variables:
            if isinstance(item, dict) and "key" in item and "value" in item:
                env[str(item["key"])] = _stringify_value(item["value"])
            else:
                warnings.append(TranslationWarning(code="unsupported_variable", message=f"Unsupported variable entry: {item!r}"))
        return env

    if variables:
        warnings.append(TranslationWarning(code="unsupported_variables", message="Unsupported top-level variables format; skipping env translation."))
    return {}


def _extract_steps(data: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    steps = data.get("steps") or {}
    if not isinstance(steps, dict):
        return []
    ordered: list[tuple[str, dict[str, Any]]] = []
    for name, body in steps.items():
        if isinstance(body, dict):
            ordered.append((str(name), body))
    return ordered


def _extract_stage_names(data: dict[str, Any]) -> set[str]:
    stages = data.get("stages") or []
    if isinstance(stages, list):
        return {str(stage) for stage in stages}
    return set()


def _translate_step(step_name: str, step: dict[str, Any], stages: set[str], warnings: list[TranslationWarning]) -> list[dict[str, Any]]:
    step_type = _step_type(step)
    translated: list[dict[str, Any]] = []

    if step.get("stage") and step["stage"] not in stages:
        warnings.append(TranslationWarning(code="unknown_stage", step=step_name, message=f"Step references undeclared stage {step['stage']!r}. Preserved as comment."))

    if step_type == "freestyle":
        translated.append(_translate_freestyle(step_name, step, warnings))
    elif step_type == "git-clone":
        translated.append(_translate_git_clone(step_name, step, warnings))
    elif step_type == "build":
        translated.append(_translate_build(step_name, step, warnings))
    elif step_type == "push":
        translated.append(_translate_push(step_name, step, warnings))
    else:
        warnings.append(TranslationWarning(code="unsupported_step_type", step=step_name, message=f"Unsupported step type {step_type!r}; emitted placeholder step."))
        translated.append(_placeholder_step(step_name, step, f"Unsupported Codefresh step type: {step_type}"))

    return translated


def _translate_freestyle(step_name: str, step: dict[str, Any], warnings: list[TranslationWarning]) -> dict[str, Any]:
    commands = step.get("commands") or []
    if isinstance(commands, str):
        commands = [commands]
    if not isinstance(commands, list) or not commands:
        warnings.append(TranslationWarning(code="empty_freestyle", step=step_name, message="Freestyle step had no commands; emitted placeholder."))
        return _placeholder_step(step_name, step, "Freestyle step has no commands to translate.")

    run_lines = _comment_prelude(step_name, step) + [str(command) for command in commands]
    translated = {"name": step_name, "run": "\n".join(run_lines)}
    step_env = _extract_step_env(step)
    if step_env:
        translated["env"] = step_env
    return translated


def _translate_git_clone(step_name: str, step: dict[str, Any], warnings: list[TranslationWarning]) -> dict[str, Any]:
    repo = step.get("repo") or step.get("repo_name") or step.get("working_directory") or "<repository>"
    revision = step.get("revision") or step.get("branch")
    warnings.append(TranslationWarning(code="conservative_git_clone", step=step_name, message="git-clone mapped conservatively to actions/checkout; verify repository, ref, and auth settings."))

    translated: dict[str, Any] = {"name": step_name, "uses": "actions/checkout@v4"}
    with_args: dict[str, Any] = {}
    if revision:
        with_args["ref"] = str(revision)
    if repo not in {"<repository>", ".", None}:
        run_note = f"Repository hint from Codefresh: {repo}"
        translated["name"] = f"{step_name} ({run_note})"
    if with_args:
        translated["with"] = with_args
    return translated


def _translate_build(step_name: str, step: dict[str, Any], warnings: list[TranslationWarning]) -> dict[str, Any]:
    image_name = step.get("image_name") or step.get("tag") or "<image>"
    dockerfile = step.get("dockerfile") or "Dockerfile"
    context = step.get("working_directory") or "."
    warnings.append(TranslationWarning(code="conservative_build", step=step_name, message="build step translated to docker build command; verify tags, build args, registry auth, and platform settings."))

    run_lines = _comment_prelude(step_name, step) + [
        f"docker build -f {dockerfile} -t {image_name} {context}",
    ]
    return {"name": step_name, "run": "\n".join(run_lines)}


def _translate_push(step_name: str, step: dict[str, Any], warnings: list[TranslationWarning]) -> dict[str, Any]:
    candidate = step.get("candidate") or step.get("image_name") or step.get("tag") or "<image>"
    warnings.append(TranslationWarning(code="conservative_push", step=step_name, message="push step translated to docker push command; configure docker/login-action or other auth first."))
    run_lines = _comment_prelude(step_name, step) + [f"docker push {candidate}"]
    return {"name": step_name, "run": "\n".join(run_lines)}


def _placeholder_step(step_name: str, step: dict[str, Any], reason: str) -> dict[str, Any]:
    lines = _comment_prelude(step_name, step)
    lines.append(f'echo "TODO: {reason}"')
    return {"name": step_name, "run": "\n".join(lines)}


def _comment_prelude(step_name: str, step: dict[str, Any]) -> list[str]:
    lines = [f"# Converted from Codefresh step: {step_name}"]
    if step.get("stage"):
        lines.append(f"# Original stage: {step['stage']}")
    if step.get("type") and step.get("type") not in SUPPORTED_SPECIAL_TYPES:
        lines.append(f"# Original type: {step['type']}")
    if step.get("image"):
        lines.append(f"# Original image: {step['image']}")
    return lines


def _extract_step_env(step: dict[str, Any]) -> dict[str, str]:
    for key in ("environment", "env"):
        value = step.get(key)
        if isinstance(value, dict):
            return {str(k): _stringify_value(v) for k, v in value.items()}
        if isinstance(value, list):
            env: dict[str, str] = {}
            for item in value:
                if isinstance(item, str) and "=" in item:
                    k, v = item.split("=", 1)
                    env[k] = v
            if env:
                return env
    return {}


def _step_type(step: dict[str, Any]) -> str:
    return str(step.get("type") or "freestyle")


def _stringify_value(value: Any) -> str:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return "" if value is None else str(value)
    return str(value)


def _strip_nones(value: Any) -> Any:
    if isinstance(value, dict):
        for key in list(value.keys()):
            if value[key] is None:
                del value[key]
            else:
                _strip_nones(value[key])
    elif isinstance(value, list):
        for item in value:
            _strip_nones(item)
    return value
