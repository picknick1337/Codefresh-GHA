from __future__ import annotations

from pathlib import Path

from flask import Flask, jsonify, render_template, request

from .parser import ParseError
from .service import translate_codefresh_yaml

TEMPLATE_DIR = Path(__file__).with_name("templates")
STATIC_DIR = Path(__file__).with_name("static")


def create_app() -> Flask:
    app = Flask(__name__, template_folder=str(TEMPLATE_DIR), static_folder=str(STATIC_DIR))

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.post("/api/translate")
    def translate():
        payload = request.get_json(silent=True) or {}
        source_yaml = str(payload.get("source_yaml") or "")
        workflow_name = str(payload.get("workflow_name") or "Converted from Codefresh")
        step_overrides = payload.get("step_overrides")
        try:
            result = translate_codefresh_yaml(source_yaml, workflow_name=workflow_name, step_overrides=step_overrides)
        except ParseError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify(result)

    return app


def main() -> None:
    app.run(debug=True)


app = create_app()
