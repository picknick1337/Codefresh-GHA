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
    step = result.steps[0]

    assert job["env"] == {"APP_ENV": "test", "DEBUG": "True"}
    assert job["steps"][0]["name"] == "unit_tests"
    assert "pytest -q" in job["steps"][0]["run"]
    assert job["steps"][0]["env"] == {"PYTHONUNBUFFERED": "1"}
    assert step.rationale
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



def test_special_image_handling_for_gcloud_and_jfrog_with_terraform():
    pipeline = {
        "steps": {
            "tf_plan": {
                "type": "freestyle",
                "image": "google/cloud-sdk:slim",
                "commands": ["gcloud auth list", "terraform init", "terraform plan"],
            },
            "publish": {
                "type": "freestyle",
                "image": "releases-docker.jfrog.io/jfrog/jfrog-cli-v2-jf",
                "commands": ["jf rt ping", "terraform apply -auto-approve"],
            },
        }
    }

    result = translate_pipeline(pipeline)

    tf_plan = result.steps[0]
    publish = result.steps[1]

    assert "setup-gcloud" in " ".join(tf_plan.translation_hints)
    assert "setup-terraform" in " ".join(tf_plan.translation_hints)
    assert any(tool == "terraform" for tool in tf_plan.detected_tools)
    assert any("Terraform commands were detected" in line for line in tf_plan.special_handling)
    assert "Install/configure JFrog CLI explicitly" in " ".join(publish.translation_hints)
    assert "setup-terraform" in " ".join(publish.translation_hints)
    assert any(tool == "jfrog-cli" for tool in publish.detected_tools)



def test_step_overrides_replace_generated_fields():
    pipeline = {
        "steps": {
            "demo": {"type": "freestyle", "commands": ["echo hi"]},
        }
    }

    result = translate_pipeline(
        pipeline,
        step_overrides={
            "demo": {"name": "Renamed demo", "run": "echo custom", "env": {"HELLO": "world"}},
        },
    )

    step = result.steps[0]
    assert step.gha_step["name"] == "Renamed demo"
    assert step.gha_step["run"] == "echo custom"
    assert step.gha_step["env"] == {"HELLO": "world"}
    assert any("edited in the workbench" in line for line in step.rationale)
