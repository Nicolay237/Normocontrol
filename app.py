#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Flask-сервер: JSON API проверки + раздача собранного React-фронтенда."""

import os
import time
import uuid
import tempfile
import threading
from datetime import datetime, timezone
from urllib.parse import quote

from flask import Flask, request, jsonify, Response, send_from_directory

from checker import title_page
from checker import (
    PROFILES, describe_profile, run_normocontrol_cached, build_html_report,
)
from checker.fixers import fix_docx

# Образец титульного листа задаёт развёртывание (NORMOCONTROL_TITLE_TEMPLATE);
# без него проверка титула пропускается с пометкой в отчёте.
_title_template = os.environ.get("NORMOCONTROL_TITLE_TEMPLATE", "").strip()
if _title_template:
    title_page.TITLE_PAGE_TEMPLATE_PATH = _title_template

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(BASE_DIR, "frontend", "dist")

app = Flask(__name__, static_folder=None)
app.json.ensure_ascii = False
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024  # 20 МБ на файл

ALLOWED_EXT = {".docx", ".pdf"}

# Редакция сервиса: university — всё бесплатно (для кафедры); public — платное автоисправление
# (оплата ещё не подключена, поэтому в public автоисправление выключено).
EDITION = os.environ.get("EDITION", "university").lower()


def can_autofix():
    return EDITION == "university"


# HTML-отчёты и исправленные файлы для скачивания: короткоживущее хранилище в памяти
_REPORTS = {}
_REPORTS_LOCK = threading.Lock()
_REPORT_TTL = 3600
_REPORT_MAX = 200


def _store_report(html, name):
    now = time.time()
    rid = uuid.uuid4().hex
    with _REPORTS_LOCK:
        for k in [k for k, v in _REPORTS.items() if now - v[2] > _REPORT_TTL]:
            _REPORTS.pop(k, None)
        while len(_REPORTS) >= _REPORT_MAX:
            _REPORTS.pop(min(_REPORTS, key=lambda k: _REPORTS[k][2]), None)
        _REPORTS[rid] = (html, name, now)
    return rid


@app.route("/health")
def health():
    return {"status": "ok"}


@app.route("/api/config")
def api_config():
    return jsonify(edition=EDITION, autofix_enabled=can_autofix())


@app.route("/api/profiles")
def api_profiles():
    return jsonify([describe_profile(p) for p in PROFILES.values()])


def serialize_report(report, filename):
    """Отчёт Николая + поля конверта платформы (camelCase).

    Клиент Study Platform (app/normocontrol/client.py) ждёт isClean, totalIssues,
    notes и categories; ключи исходного отчёта сохранены для веб-интерфейса.
    """
    data = report.to_dict(filename)
    data["filename"] = filename
    data["generatedAt"] = datetime.now(timezone.utc).isoformat()
    data["isClean"] = report.is_clean()
    data["totalIssues"] = len(report.issues)
    return data


@app.route("/api/check", methods=["POST"])
def api_check():
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify(error="Файл не выбран."), 400

    profile = request.form.get("profile", "vkr")
    if profile not in PROFILES:
        return jsonify(error="Неизвестный тип работы."), 400

    ext = os.path.splitext(f.filename)[1].lower()
    if ext not in ALLOWED_EXT:
        return jsonify(error="Поддерживаются только файлы .docx и .pdf."), 400

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "upload" + ext)  # имя пользователя на диск не попадает
        f.save(path)
        try:
            report = run_normocontrol_cached(path, profile)
        except Exception as e:
            app.logger.exception("check failed")
            msg = "Не удалось обработать файл. Убедитесь, что он не повреждён и не защищён паролем."
            if app.debug:
                msg += f" ({e})"
            return jsonify(error=msg), 422

    data = serialize_report(report, f.filename)
    data["report_id"] = _store_report(build_html_report(report, f.filename), f.filename)
    return jsonify(data)


@app.route("/api/fix", methods=["POST"])
def api_fix():
    if not can_autofix():
        return jsonify(error="Автоисправление в этой версии недоступно."), 403
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify(error="Файл не выбран."), 400
    profile = request.form.get("profile", "vkr")
    if profile not in PROFILES:
        return jsonify(error="Неизвестный тип работы."), 400
    if os.path.splitext(f.filename)[1].lower() != ".docx":
        return jsonify(error="Автоисправление работает только с файлами .docx."), 400

    with tempfile.TemporaryDirectory() as tmp:
        src, dst = os.path.join(tmp, "upload.docx"), os.path.join(tmp, "fixed.docx")
        f.save(src)
        try:
            result = fix_docx(src, dst, PROFILES[profile])
        except Exception:
            app.logger.exception("fix failed")
            return jsonify(error="Не удалось исправить файл. Убедитесь, что он не повреждён и не защищён паролем."), 422
        with open(dst, "rb") as fh:
            data = fh.read()

    base = os.path.splitext(f.filename)[0]
    payload = result.to_dict()
    payload["file"] = f.filename
    payload["download_id"] = _store_report(data, f"{base}_исправлено.docx")
    return jsonify(payload)


@app.route("/api/fixed/<rid>")
def api_fixed_download(rid):
    with _REPORTS_LOCK:
        entry = _REPORTS.get(rid)
    if not entry or not isinstance(entry[0], bytes):
        return jsonify(error="Файл не найден или устарел. Запустите исправление заново."), 404
    data, name, _ = entry
    resp = Response(data, mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    resp.headers["Content-Disposition"] = (
        f"attachment; filename=fixed.docx; filename*=UTF-8''{quote(name)}"
    )
    return resp


@app.route("/api/report/<rid>")
def api_report_download(rid):
    with _REPORTS_LOCK:
        entry = _REPORTS.get(rid)
    if not entry:
        return jsonify(error="Отчёт не найден или устарел. Проверьте файл заново."), 404
    html, name, _ = entry
    if not isinstance(html, str):
        return jsonify(error="Отчёт не найден."), 404
    base = os.path.splitext(name)[0]
    resp = Response(html, mimetype="text/html")
    resp.headers["Content-Disposition"] = (
        f"attachment; filename=normocontrol_report.html; filename*=UTF-8''{quote(base)}_report.html"
    )
    return resp


@app.errorhandler(413)
def too_large(e):
    return jsonify(error="Файл слишком большой (максимум 20 МБ)."), 413


@app.errorhandler(500)
def server_error(e):
    return jsonify(error="Внутренняя ошибка сервера."), 500


# ── React SPA ─────────────────────────────────────────────────────────────

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def spa(path):
    if path.startswith("api/"):
        return jsonify(error="Не найдено."), 404
    if not os.path.isdir(DIST_DIR):
        return Response(
            "Фронтенд не собран. Выполните: cd frontend && npm install && npm run build "
            "(или запустите npm run dev для разработки).", status=503, mimetype="text/plain; charset=utf-8")
    full = os.path.join(DIST_DIR, path)
    if path and os.path.isfile(full):
        return send_from_directory(DIST_DIR, path)
    return send_from_directory(DIST_DIR, "index.html")  # клиентский роутинг (/vkr, /coursework)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
