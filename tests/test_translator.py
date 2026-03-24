from cf2gha.translator import translate_pipeline


def test_translate_freestyle_and_top_level_variables():
    pipeline = {
        "variables": {"APP_ENV": "test", "DEBUG": True},
        "stages": ["clone", "test"],
        "steps": {
            "unit_tests": {
                "type": "freestyle",
                "stage": "test",
                "image": "python:3.12",
                "commands": ["pip install -r requirements.txt", "pytest -q"],
                "environment": {"PYTHONUNBUFFERED": 1},
            }
        },
    }

    result = translate_pipeline(pipeline)
    job = result.workflow["jobs"]["codefresh_migration"]

    assert job["env"] == {"APP_ENV": "test", "DEBUG": "True"}
    assert job["steps"][0]["name"] == "unit_tests"
    assert "pytest -q" in job["steps"][0]["run"]
    assert job["steps"][0]["env"] == {"PYTHONUNBUFFERED": "1"}
    assert result.warnings == []


def test_translate_checkout_build_push_and_emit_warnings():
    pipeline = {
        "steps": {
            "clone": {"type": "git-clone", "repo": "org/repo", "revision": "main"},
            "build_image": {"type": "build", "image_name": "ghcr.io/acme/app:latest", "working_directory": "."},
            "push_image": {"type": "push", "candidate": "ghcr.io/acme/app:latest"},
        }
    }

    result = translate_pipeline(pipeline)
    steps = result.workflow["jobs"]["codefresh_migration"]["steps"]

    assert steps[0]["uses"] == "actions/checkout@v4"
    assert steps[1]["uses"] == "actions/checkout@v4"
    assert "docker build" in steps[2]["run"]
    assert "docker push ghcr.io/acme/app:latest" in steps[3]["run"]
    assert {warning.code for warning in result.warnings} == {
        "conservative_git_clone",
        "conservative_build",
        "conservative_push",
    }


def test_translate_unsupported_step_as_placeholder():
    pipeline = {
        "steps": {
            "something_weird": {
                "type": "parallel",
                "stage": "later",
                "commands": ["echo hello"],
            }
        }
    }

    result = translate_pipeline(pipeline)
    step = result.workflow["jobs"]["codefresh_migration"]["steps"][0]

    assert 'TODO: Unsupported Codefresh step type: parallel' in step["run"]
    assert any(w.code == "unsupported_step_type" for w in result.warnings)
    assert any(w.code == "unknown_stage" for w in result.warnings)
