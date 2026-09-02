#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import os
import tempfile
from datetime import datetime, timezone

from flask import Flask, request, jsonify, send_from_directory

import normocontrol as nc

FRONTEND_DIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend", "dist")

app = Flask(__name__, static_folder=FRONTEND_DIST, static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024  # 20 МБ на файл

ALLOWED_EXT = {".docx", ".pdf"}


def serialize_report(report, filename):
    """Turns a normocontrol.Report into the JSON shape the React frontend expects."""
    categories = []
    index_by_name = {}
    for issue in report.issues:
        if issue.category not in index_by_name:
            index_by_name[issue.category] = len(categories)
            categories.append({"name": issue.category, "issues": []})
        categories[index_by_name[issue.category]]["issues"].append(
            {"location": issue.location, "message": issue.message}
        )

    return {
        "filename": filename,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "isClean": report.is_clean(),
        "totalIssues": len(report.issues),
        "notes": list(report.notes),
        "categories": categories,
    }


@app.route("/health")
def health():
    return {"status": "ok"}


@app.route("/api/check", methods=["POST"])
def api_check():
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify(error="Файл не выбран."), 400

    ext = os.path.splitext(f.filename)[1].lower()
    if ext not in ALLOWED_EXT:
        return jsonify(error="Поддерживаются только файлы .docx и .pdf."), 400

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, f.filename)
        f.save(path)
        try:
            report = nc.run_normocontrol(path)
        except Exception as e:
            return jsonify(error=f"Не удалось обработать файл: {e}"), 422

    return jsonify(serialize_report(report, f.filename))


@app.errorhandler(413)
def too_large(e):
    return jsonify(error="Файл слишком большой (максимум 20 МБ)."), 413


@app.errorhandler(404)
def not_found(e):
    if request.path.startswith("/api/"):
        return jsonify(error="Страница не найдена."), 404
    # SPA fallback: any non-API 404 (deep link, refresh) still serves the app shell.
    return send_from_directory(FRONTEND_DIST, "index.html")


@app.errorhandler(500)
def server_error(e):
    return jsonify(error="Внутренняя ошибка сервера."), 500


@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIST, "index.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
