# codefresh-to-github-actions

A small Python CLI that converts a **basic subset** of Codefresh pipeline YAML into GitHub Actions workflow YAML.

This is a pragmatic first cut, not a full Codefresh migration engine.

## Scope

Supported in this version:

- top-level `variables` mapped to job-level `env` where possible
- sequential `steps` in source order
- `freestyle` steps mapped to `run` steps
- `git-clone` steps mapped conservatively to `actions/checkout@v4`
- `build` steps mapped conservatively to `docker build ...`
- `push` steps mapped conservatively to `docker push ...`
- unsupported constructs preserved as placeholder steps plus CLI warnings

## Explicit assumptions

- Output is a **single workflow** with a **single job** on `ubuntu-latest`
- Trigger defaults are intentionally simple: `workflow_dispatch` and `push` to `main`
- Step ordering is preserved, but Codefresh parallelism, services, volumes, and advanced conditions are **not** fully modeled
- Container/image semantics are preserved as comments where direct GitHub Actions equivalents are unclear
- Docker registry authentication is **not** inferred automatically

## Limitations

This tool does **not** aim to fully support:

- parallel graphs / fan-in / fan-out
- all built-in Codefresh step types
- matrix generation
- secret migration
- deployment environments
- service containers
- advanced conditionals and triggers
- exact runner/container parity

If the converter cannot map something confidently, it emits warnings and leaves a clear placeholder in the output rather than guessing.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

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

## Example

### Input

```yaml
version: "1.0"
variables:
  IMAGE_NAME: ghcr.io/acme/demo:latest
stages:
  - clone
  - build
steps:
  clone_repo:
    type: git-clone
    repo: acme/demo
    revision: main
  unit_tests:
    type: freestyle
    stage: build
    image: python:3.12
    commands:
      - pip install -r requirements.txt
      - pytest -q
  build_image:
    type: build
    image_name: ghcr.io/acme/demo:latest
    working_directory: .
  push_image:
    type: push
    candidate: ghcr.io/acme/demo:latest
```

### Output

```yaml
name: Converted from Codefresh
'on':
  workflow_dispatch: null
  push:
    branches:
      - main
jobs:
  codefresh_migration:
    runs-on: ubuntu-latest
    env:
      IMAGE_NAME: ghcr.io/acme/demo:latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
      - name: clone_repo (Repository hint from Codefresh: acme/demo)
        uses: actions/checkout@v4
        with:
          ref: main
      - name: unit_tests
        run: |
          # Converted from Codefresh step: unit_tests
          # Original stage: build
          # Original image: python:3.12
          pip install -r requirements.txt
          pytest -q
      - name: build_image
        run: |
          # Converted from Codefresh step: build_image
          docker build -f Dockerfile -t ghcr.io/acme/demo:latest .
      - name: push_image
        run: |
          # Converted from Codefresh step: push_image
          docker push ghcr.io/acme/demo:latest
```

Warnings for conservative or unsupported translations are printed to stderr.

## Development

Run tests:

```bash
pytest
```

## Why this project is intentionally simple

Migration tools get dangerous when they hide uncertainty. This version stays explicit:

- conservative translations
- comments in generated steps
- warnings in CLI output
- readable code paths over broad magic
