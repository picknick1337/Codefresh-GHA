from __future__ import annotations

from pathlib import Path

import yaml

from cf2gha.cli import main


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
