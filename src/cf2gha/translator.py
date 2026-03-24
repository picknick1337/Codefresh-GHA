from __future__ import annotations

from collections.abc import Iterable
from copy import deepcopy
from typing import Any

from .models import StepTranslation, StepWarning, TranslationResult, TranslationWarning

SUPPORTED_SPECIAL_TYPES = {"freestyle", "git-clone", "build", "push"}
GCLOUD_IMAGE_HINTS = (
    "google/cloud-sdk",
    "google-cloud-cli",
    "google/cloud-cli",
    "cloud-sdk",
    "cloudsdktool",
    "gcloud",
)
JFROG_IMAGE_HINTS = (
    "jfrog-cli",
    "jfrog/jfrog-cli",
    "releases-docker.jfrog.io",
    "jfrog",
)
TERRAFORM_COMMAND_HINTS = ("terraform ", "terraform\n", "terraform\t", "terraform-")


def translate_pipeline(
    data: dict[str, Any],
    workflow_name: str = "Converted from Codefresh",
    step_overrides: dict[str, dict[str, Any]] | None = None,
) -> TranslationResult:
    warnings: list[TranslationWarning] = []
    env = _extract_env(data, warnings)
    steps = _extract_steps(data)
    stages = _extract_stage_names(data)
    step_overrides = step_overrides or {}

    gha_steps: list[dict[str, Any]] = []
    translated_steps: list[StepTranslation] = []
    if any(_step_type(step) == "git-clone" for _, step in steps):
        gha_steps.append({"name": "Checkout repository", "uses": "actions/checkout@v4"})

    for step_name, step_body in steps:
        translated = _translate_step(step_name, step_body, stages, warnings)
        translated = _apply_override(translated, step_overrides.get(step_name))
        gha_steps.append(translated.gha_step)
        translated_steps.append(translated)

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
    return TranslationResult(
        workflow=workflow,
        warnings=warnings,
        steps=translated_steps,
        checklist=_build_pipeline_checklist(data, translated_steps),
        source_summary={
            "step_count": len(translated_steps),
            "stage_count": len(stages),
            "has_top_level_env": bool(env),
        },
    )


def _apply_override(step: StepTranslation, override: dict[str, Any] | None) -> StepTranslation:
    if not override:
        return step

    mutated = deepcopy(step)
    gha_step = deepcopy(step.gha_step)
    for field in ("name", "uses", "run"):
        value = override.get(field)
        if isinstance(value, str) and value.strip():
            gha_step[field] = value
    if override.get("env") is None:
        pass
    elif isinstance(override.get("env"), dict):
        env = {str(k): _stringify_value(v) for k, v in override["env"].items()}
        if env:
            gha_step["env"] = env
        else:
            gha_step.pop("env", None)
    mutated.gha_step = gha_step
    mutated.rationale.append("The generated GitHub Actions step was edited in the workbench.")
    return mutated


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
                warnings.append(
                    TranslationWarning(
                        code="unsupported_variable",
                        message=f"Unsupported variable entry: {item!r}",
                    )
                )
        return env

    if variables:
        warnings.append(
            TranslationWarning(
                code="unsupported_variables",
                message="Unsupported top-level variables format; skipping env translation.",
            )
        )
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


def _translate_step(step_name: str, step: dict[str, Any], stages: set[str], warnings: list[TranslationWarning]) -> StepTranslation:
    step_type = _step_type(step)

    step_warnings: list[StepWarning] = []
    rationale: list[str] = []
    checklist: list[str] = []
    if step.get("stage") and step["stage"] not in stages:
        warnings.append(
            TranslationWarning(
                code="unknown_stage",
                step=step_name,
                message=f"Step references undeclared stage {step['stage']!r}. Preserved as comment.",
            )
        )
        step_warnings.append(
            StepWarning(
                code="unknown_stage",
                message=f"This step references undeclared stage {step['stage']!r}.",
                suggestion="Check whether the stage name changed or the pipeline relied on implicit ordering.",
            )
        )

    if step_type == "freestyle":
        gha_step = _translate_freestyle(step_name, step, warnings, step_warnings, rationale, checklist)
    elif step_type == "git-clone":
        gha_step = _translate_git_clone(step_name, step, warnings, rationale, checklist)
    elif step_type == "build":
        gha_step = _translate_build(step_name, step, warnings, rationale, checklist)
    elif step_type == "push":
        gha_step = _translate_push(step_name, step, warnings, rationale, checklist)
    else:
        warnings.append(
            TranslationWarning(
                code="unsupported_step_type",
                step=step_name,
                message=f"Unsupported step type {step_type!r}; emitted placeholder step.",
            )
        )
        step_warnings.append(
            StepWarning(
                code="unsupported_step_type",
                message=f"Unsupported Codefresh step type: {step_type}",
                suggestion="Replace the placeholder with a hand-written action or script.",
            )
        )
        rationale.append("This Codefresh step type has no safe direct mapping in this tool.")
        checklist.append("Replace the TODO placeholder with a GitHub Actions equivalent.")
        gha_step = _placeholder_step(step_name, step, f"Unsupported Codefresh step type: {step_type}")

    special_handling, detected_tools, hints = _special_image_handling(step)
    if special_handling:
        rationale.extend(special_handling)
        checklist.extend(hints)
        for item in hints:
            step_warnings.append(
                StepWarning(
                    code="image_semantics_review",
                    message=item,
                    suggestion="Keep the step explicit rather than assuming the container image on the runner.",
                )
            )

    return StepTranslation(
        source_name=step_name,
        step_type=step_type,
        stage=str(step.get("stage")) if step.get("stage") else None,
        source_image=str(step.get("image")) if step.get("image") else None,
        gha_step=gha_step,
        rationale=_dedupe(rationale),
        checklist=_dedupe(checklist),
        warnings=step_warnings,
        detected_tools=detected_tools,
        translation_hints=hints,
        special_handling=special_handling,
    )


def _translate_freestyle(
    step_name: str,
    step: dict[str, Any],
    warnings: list[TranslationWarning],
    step_warnings: list[StepWarning],
    rationale: list[str],
    checklist: list[str],
) -> dict[str, Any]:
    commands = step.get("commands") or []
    if isinstance(commands, str):
        commands = [commands]
    if not isinstance(commands, list) or not commands:
        warnings.append(
            TranslationWarning(
                code="empty_freestyle",
                step=step_name,
                message="Freestyle step had no commands; emitted placeholder.",
            )
        )
        step_warnings.append(
            StepWarning(
                code="empty_freestyle",
                message="Freestyle step has no commands to translate.",
                suggestion="Fill in the step manually or remove it if it is obsolete.",
            )
        )
        rationale.append("Freestyle steps need shell commands; none were present.")
        checklist.append("Decide whether this step should be deleted or re-authored manually.")
        return _placeholder_step(step_name, step, "Freestyle step has no commands to translate.")

    commands_text = "\n".join(str(command) for command in commands)
    run_lines = _comment_prelude(step_name, step)
    for note in _command_notes(step):
        run_lines.append(f"# {note}")
    run_lines.extend(str(command) for command in commands)

    translated = {"name": step_name, "run": "\n".join(run_lines)}
    step_env = _extract_step_env(step)
    if step_env:
        translated["env"] = step_env
        rationale.append("Step-level environment variables were preserved under env.")
    rationale.append("Freestyle steps translate best to run steps because the source is already shell-oriented.")

    detected = _detect_tools(str(step.get("image") or ""), commands_text)
    if detected:
        rationale.append(f"Detected tools in the step context: {', '.join(detected)}.")
    if any(tool == "terraform" for tool in detected):
        checklist.append("Confirm terraform version parity; Codefresh image contents do not automatically exist on GitHub runners.")
    return translated


def _translate_git_clone(
    step_name: str,
    step: dict[str, Any],
    warnings: list[TranslationWarning],
    rationale: list[str],
    checklist: list[str],
) -> dict[str, Any]:
    repo = step.get("repo") or step.get("repo_name") or step.get("working_directory") or "<repository>"
    revision = step.get("revision") or step.get("branch")
    warnings.append(
        TranslationWarning(
            code="conservative_git_clone",
            step=step_name,
            message="git-clone mapped conservatively to actions/checkout; verify repository, ref, and auth settings.",
        )
    )
    rationale.append("git-clone is mapped to actions/checkout because GitHub Actions already assumes a checked-out repository in most jobs.")
    checklist.append("Verify checkout ref and credentials if this step clones a different repository.")

    translated: dict[str, Any] = {"name": step_name, "uses": "actions/checkout@v4"}
    with_args: dict[str, Any] = {}
    if revision:
        with_args["ref"] = str(revision)
    if repo not in {"<repository>", ".", None}:
        translated["name"] = f"{step_name} (Repository hint from Codefresh: {repo})"
    if with_args:
        translated["with"] = with_args
    return translated


def _translate_build(
    step_name: str,
    step: dict[str, Any],
    warnings: list[TranslationWarning],
    rationale: list[str],
    checklist: list[str],
) -> dict[str, Any]:
    image_name = step.get("image_name") or step.get("tag") or "<image>"
    dockerfile = step.get("dockerfile") or "Dockerfile"
    context = step.get("working_directory") or "."
    warnings.append(
        TranslationWarning(
            code="conservative_build",
            step=step_name,
            message="build step translated to docker build command; verify tags, build args, registry auth, and platform settings.",
        )
    )
    rationale.append("The build step was translated to an explicit docker build command instead of inferring extra action wrappers.")
    checklist.append("Add docker/login-action or another registry auth step before pushing images.")

    run_lines = _comment_prelude(step_name, step) + [
        f"docker build -f {dockerfile} -t {image_name} {context}",
    ]
    return {"name": step_name, "run": "\n".join(run_lines)}


def _translate_push(
    step_name: str,
    step: dict[str, Any],
    warnings: list[TranslationWarning],
    rationale: list[str],
    checklist: list[str],
) -> dict[str, Any]:
    candidate = step.get("candidate") or step.get("image_name") or step.get("tag") or "<image>"
    warnings.append(
        TranslationWarning(
            code="conservative_push",
            step=step_name,
            message="push step translated to docker push command; configure docker/login-action or other auth first.",
        )
    )
    rationale.append("Push steps stay as docker push commands so auth remains visible and reviewable.")
    checklist.append("Configure registry login before running docker push.")
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


def _command_notes(step: dict[str, Any]) -> list[str]:
    image = str(step.get("image") or "")
    commands = step.get("commands") or []
    if isinstance(commands, str):
        commands = [commands]
    commands_text = "\n".join(str(command) for command in commands)
    notes: list[str] = []

    if _looks_like_gcloud_image(image):
        notes.append("Codefresh container image looked like Google Cloud SDK / gcloud CLI.")
        notes.append("Prefer google-github-actions/auth plus google-github-actions/setup-gcloud instead of assuming the source image exists on the runner.")
    if _looks_like_jfrog_image(image):
        notes.append("Codefresh container image looked like a JFrog CLI image.")
        notes.append("Prefer installing/configuring JFrog CLI explicitly in GitHub Actions instead of relying on the original container image.")
    if _mentions_terraform(commands_text):
        notes.append("Terraform commands were detected; install/setup terraform explicitly if the original image bundled it.")
    return notes


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


def _detect_tools(image: str, commands_text: str) -> list[str]:
    found: list[str] = []
    lower_image = image.lower()
    lower_commands = commands_text.lower()
    if "terraform" in lower_commands:
        found.append("terraform")
    if _looks_like_gcloud_image(lower_image) or "gcloud" in lower_commands:
        found.append("gcloud")
    if _looks_like_jfrog_image(lower_image) or "jfrog" in lower_commands:
        found.append("jfrog-cli")
    return _dedupe(found)


def _special_image_handling(step: dict[str, Any]) -> tuple[list[str], list[str], list[str]]:
    image = str(step.get("image") or "")
    commands = step.get("commands") or []
    if isinstance(commands, str):
        commands = [commands]
    commands_text = "\n".join(str(command) for command in commands)

    rationale: list[str] = []
    detected_tools = _detect_tools(image, commands_text)
    hints: list[str] = []

    if _looks_like_gcloud_image(image):
        rationale.append(
            "The source step ran inside a Google Cloud SDK / gcloud image. GitHub-hosted runners do not automatically provide that exact container environment."
        )
        hints.append("Replace implicit gcloud image assumptions with google-github-actions/auth and google-github-actions/setup-gcloud.")
    if _looks_like_jfrog_image(image):
        rationale.append(
            "The source step ran inside a JFrog CLI image. Treat JFrog CLI installation and login as explicit setup in GitHub Actions."
        )
        hints.append("Install/configure JFrog CLI explicitly; do not assume the original image contents exist on the runner.")
    if _mentions_terraform(commands_text) and (_looks_like_gcloud_image(image) or _looks_like_jfrog_image(image)):
        rationale.append(
            "Terraform commands were detected inside a CLI-focused image. That often means the Codefresh image bundled extra tooling which GitHub Actions will not inherit automatically."
        )
        hints.append("Add hashicorp/setup-terraform and verify any cloud or artifact auth before terraform commands run.")
    return _dedupe(rationale), detected_tools, _dedupe(hints)


def _mentions_terraform(commands_text: str) -> bool:
    lower = commands_text.lower()
    return "terraform" in lower


def _looks_like_gcloud_image(image: str) -> bool:
    lower = image.lower()
    return any(hint in lower for hint in GCLOUD_IMAGE_HINTS)


def _looks_like_jfrog_image(image: str) -> bool:
    lower = image.lower()
    return any(hint in lower for hint in JFROG_IMAGE_HINTS)


def _build_pipeline_checklist(data: dict[str, Any], steps: list[StepTranslation]) -> list[str]:
    items = [
        "Validate workflow triggers and branch filters before replacing the original pipeline.",
        "Move secrets into GitHub Actions secrets or environments; this tool does not migrate secret storage.",
        "Run the generated workflow in a test repository before cutting over production builds.",
    ]
    if data.get("variables"):
        items.append("Review top-level variables and decide whether any should become GitHub secrets instead of plain env values.")
    if any(step.step_type in {"build", "push"} for step in steps):
        items.append("Review container registry auth and image tagging strategy.")
    if any(step.translation_hints for step in steps):
        items.append("Review special image/tooling hints for steps that relied on bundled CLIs in Codefresh images.")
    return _dedupe(items)


def _dedupe(values: Iterable[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            output.append(value)
            seen.add(value)
    return output
