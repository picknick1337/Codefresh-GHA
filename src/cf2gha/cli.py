from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .emitter import dump_yaml
from .parser import ParseError, load_codefresh_file
from .translator import translate_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cf2gha",
        description="Convert a basic Codefresh pipeline YAML into a GitHub Actions workflow YAML.",
    )
    parser.add_argument("input", help="Path to a Codefresh YAML file")
    parser.add_argument("-o", "--output", help="Write workflow YAML to this file instead of stdout")
    parser.add_argument("--name", default="Converted from Codefresh", help="Workflow name override")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero if translation emitted warnings",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        pipeline = load_codefresh_file(args.input)
        result = translate_pipeline(pipeline, workflow_name=args.name)
    except (OSError, ParseError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    workflow_text = dump_yaml(result.workflow)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(workflow_text, encoding="utf-8")
    else:
        print(workflow_text, end="")

    if result.warnings:
        print("Warnings:", file=sys.stderr)
        for warning in result.warnings:
            prefix = f"[{warning.code}]"
            if warning.step:
                print(f"- {prefix} step={warning.step}: {warning.message}", file=sys.stderr)
            else:
                print(f"- {prefix} {warning.message}", file=sys.stderr)

    return 1 if args.strict and result.warnings else 0


if __name__ == "__main__":
    raise SystemExit(main())
