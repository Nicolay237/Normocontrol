#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import os
import tempfile

from flask import Flask, request, render_template, jsonify, Response

import normocontrol as nc

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024  # 20 МБ на файл

ALLOWED_EXT = {".docx", ".pdf"}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/report.css")
def report_css():
    return Response(nc.REPORT_CSS, mimetype="text/css")


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
        fragment = nc.build_report_fragment(report, f.filename)

    return Response(fragment, mimetype="text/html")


@app.errorhandler(413)
def too_large(e):
    return jsonify(error="Файл слишком большой (максимум 20 МБ)."), 413


@app.errorhandler(404)
def not_found(e):
    return jsonify(error="Страница не найдена."), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify(error="Внутренняя ошибка сервера."), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
