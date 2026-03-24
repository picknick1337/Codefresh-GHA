# codefresh-to-github-actions

A local migration workbench for converting a **basic but explicit subset** of Codefresh pipeline YAML into GitHub Actions workflow YAML.

This project now has two surfaces:

- a **CLI** for one-shot conversion
- a **local web workbench** for live editing, step review, and migration notes

The goal is not fake precision. When the tool is unsure, it tells you.

## What the workbench does

- paste or upload Codefresh YAML
- live conversion to GitHub Actions YAML
- per-step review with generated step name / `uses` / `run` fields editable in real time
- structured step metadata: rationale, warnings, checklist items, detected tools, and special handling hints
- explicit conservative handling for:
  - `freestyle`
  - `git-clone`
  - `build`
  - `push`
  - freestyle steps using container images such as Google Cloud SDK / gcloud CLI images and JFrog CLI images
- conservative warnings when a Codefresh image likely bundled tooling such as `terraform`

## Scope

Supported in this version:

- top-level `variables` mapped to job-level `env` where possible
- sequential `steps` in source order
- `freestyle` steps mapped to `run` steps
- `git-clone` steps mapped conservatively to `actions/checkout@v4`
- `build` steps mapped conservatively to `docker build ...`
- `push` steps mapped conservatively to `docker push ...`
- structured per-step metadata for UI review
- overrides for generated step fields from the workbench UI
- special hints for Codefresh steps that appear to depend on bundled CLIs in images

## Explicit assumptions

- output is a **single workflow** with a **single job** on `ubuntu-latest`
- trigger defaults are intentionally simple: `workflow_dispatch` and `push` to `main`
- step ordering is preserved, but Codefresh parallelism, services, volumes, and advanced conditions are **not** fully modeled
- container/image semantics are preserved as comments and warnings where direct GitHub Actions equivalents are unclear
- docker registry authentication is **not** inferred automatically
- image-specific tooling is **not** assumed to exist on GitHub runners just because it existed in a Codefresh container image

## Important special handling

### Google Cloud SDK / gcloud images

If a freestyle step uses images such as `google/cloud-sdk`, `google-cloud-cli`, or similar:

- the step stays conservative as a shell step
- the generated output includes comments explaining that the original container image semantics are not preserved automatically
- the structured metadata recommends using:
  - `google-github-actions/auth`
  - `google-github-actions/setup-gcloud`

### JFrog CLI images

If a freestyle step uses JFrog CLI container images:

- the step stays explicit and conservative
- the metadata recommends installing/configuring JFrog CLI directly in GitHub Actions instead of assuming the original image exists

### Terraform inside CLI-oriented images

If the tool detects `terraform` commands inside gcloud/JFrog-style images:

- it emits explicit warnings and rationale
- it recommends adding `hashicorp/setup-terraform`
- it calls out that the original Codefresh image may have bundled multiple tools that GitHub-hosted runners will not inherit automatically

That is deliberate. Guessing here is how migrations go sideways.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

## Run the web workbench

```bash
cf2gha-web
```

Then open <http://127.0.0.1:5000>.

The UI is local-only and intentionally simple:

- left: source Codefresh YAML
- right: generated GitHub Actions YAML
- below: editable per-step translation review, warnings, rationale, and checklist

## CLI usage

```bash
cf2gha path/to/codefresh.yml
cf2gha path/to/codefresh.yml --output .github/workflows/converted.yml
cf2gha path/to/codefresh.yml --name "Migrated Pipeline"
cf2gha path/to/codefresh.yml --strict
```

- default output: stdout
- `--output`: write to a file
- `--strict`: return exit code `1` if warnings were produced

## Architecture

### Why Flask + plain JS

I chose a small Python web app with server-rendered static assets and a JSON translation endpoint.

That stack is the best fit here because it gives:

- fast iteration inside the existing Python project
- no Node build chain
- easy real-time translation calls from the browser
- explicit translation logic that stays close to the tests

### Main pieces

- `cf2gha.translator` — core translation and structured step metadata
- `cf2gha.service` — serialize translation results for UI/API use
- `cf2gha.web` — local Flask app and `/api/translate` endpoint
- `cf2gha.cli` — one-shot file-to-workflow conversion

## Development

Run tests:

```bash
pytest
```

## Limitations

This tool still does **not** aim to fully support:

- parallel graphs / fan-in / fan-out
- all built-in Codefresh step types
- matrix generation
- secret migration
- deployment environments
- service containers
- advanced conditionals and triggers
- exact runner/container parity

If the converter cannot map something confidently, it emits warnings and leaves a clear placeholder in the output rather than guessing.
