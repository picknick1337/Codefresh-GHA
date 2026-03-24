from __future__ import annotations

import yaml

from cf2gha.cli import main
from cf2gha.web import create_app


def test_cli_writes_output_file(tmp_path, capsys):
    input_file = tmp_path / "codefresh.yml"
    output_file = tmp_path / "workflow.yml"
    input_file.write_text(
        yaml.safe_dump(
            {
                "variables": {"FOO": "bar"},
                "steps": {
                    "demo": {"type": "freestyle", "commands": ["echo hi"]},
                },
            }
        ),
        encoding="utf-8",
    )

    exit_code = main([str(input_file), "--output", str(output_file), "--name", "Demo Workflow"])

    assert exit_code == 0
    text = output_file.read_text(encoding="utf-8")
    assert "name: Demo Workflow" in text
    assert "echo hi" in text
    captured = capsys.readouterr()
    assert captured.err == ""



def test_cli_strict_mode_returns_non_zero_on_warnings(tmp_path):
    input_file = tmp_path / "codefresh.yml"
    input_file.write_text(
        yaml.safe_dump(
            {
                "steps": {
                    "odd": {"type": "mystery"},
                }
            }
        ),
        encoding="utf-8",
    )

    exit_code = main([str(input_file), "--strict"])

    assert exit_code == 1



def test_web_translate_endpoint_returns_structured_step_metadata():
    app = create_app()
    client = app.test_client()

    response = client.post(
        "/api/translate",
        json={
            "source_yaml": yaml.safe_dump(
                {
                    "steps": {
                        "demo": {
                            "type": "freestyle",
                            "image": "google/cloud-sdk:slim",
                            "commands": ["gcloud auth list", "terraform plan"],
                        }
                    }
                }
            )
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["steps"][0]["source_name"] == "demo"
    assert "workflow_yaml" in payload
    assert "translation_hints" in payload["steps"][0]
    assert any("setup-gcloud" in hint for hint in payload["steps"][0]["translation_hints"])



def test_web_translate_endpoint_rejects_bad_yaml():
    app = create_app()
    client = app.test_client()

    response = client.post("/api/translate", json={"source_yaml": "steps: ["})

    assert response.status_code == 400
    payload = response.get_json()
    assert "error" in payload
