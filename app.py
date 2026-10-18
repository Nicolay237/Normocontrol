#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Flask-сервер: JSON API проверки + раздача собранного React-фронтенда."""

import os
import json
import gzip
import time
import uuid
import shutil
import tempfile
import threading
from urllib.parse import quote

from flask import Flask, request, jsonify, Response, send_from_directory, send_file

from checker import (
    PROFILES, describe_profile, run_normocontrol_cached, build_html_report,
)
from checker.fixers import fix_docx
import auth
from auth import can_autofix, current_user, public_user

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(BASE_DIR, "frontend", "dist")

app = Flask(__name__, static_folder=None)
app.json.ensure_ascii = False
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024  # 20 МБ на файл

ALLOWED_EXT = {".docx", ".pdf"}

# Учётки университета: вход по логину/паролю от администратора (см. auth.py).
# Проверка доступна всем; автоисправление — вошедшим пользователям университета
# (для остальных позже появится оплата).
auth.init_app(app, BASE_DIR)


# ── короткоживущее хранилище файлов на диске ──────────────────────────────
# Загруженные .docx (чтобы автоисправление не заставляло телефон отправлять файл
# второй раз), HTML-отчёты и исправленные файлы. На диске, а не в памяти: на
# тарифах с 512 МБ RAM сотня исправленных работ по 2–5 МБ в памяти не поместится.

class FileStore:
    TTL = 3600          # секунд
    MAX_ITEMS = 300

    def __init__(self, root):
        self.root = root
        shutil.rmtree(root, ignore_errors=True)   # файлы прошлого запуска уже никому не нужны
        os.makedirs(root, exist_ok=True)
        self.meta = {}                           # id → (kind, name, created, path)
        self.lock = threading.Lock()

    def _cleanup(self):
        now = time.time()
        old = {k for k, m in self.meta.items() if now - m[2] > self.TTL}
        rest = sorted((k for k in self.meta if k not in old), key=lambda k: self.meta[k][2])
        while len(rest) >= self.MAX_ITEMS:
            old.add(rest.pop(0))
        for k in old:
            m = self.meta.pop(k, None)
            try:
                os.remove(m[3])
            except (OSError, TypeError):
                pass

    def put(self, kind, name, data=None, src_path=None):
        sid = uuid.uuid4().hex
        # расширение сохраняем: проверка определяет формат по нему
        path = os.path.join(self.root, sid + os.path.splitext(name)[1].lower())
        if src_path:
            shutil.copyfile(src_path, path)
        else:
            with open(path, "wb") as fh:
                fh.write(data.encode("utf-8") if isinstance(data, str) else data)
        with self.lock:
            self._cleanup()
            self.meta[sid] = (kind, name, time.time(), path)
        return sid

    def get(self, sid, kind):
        """(путь, исходное имя) или None, если нет / устарел / другого типа."""
        if not sid or not sid.isalnum():
            return None
        with self.lock:
            m = self.meta.get(sid)
        if not m or m[0] != kind or time.time() - m[2] > self.TTL or not os.path.exists(m[3]):
            return None
        return m[3], m[1]


store = FileStore(os.path.join(tempfile.gettempdir(), "normocontrol_store"))


@app.route("/health")
def health():
    return {"status": "ok"}


@app.route("/api/config")
def api_config():
    return jsonify(_client_config())


def _client_config():
    return {"autofix_enabled": can_autofix(), "user": public_user(current_user())}


@app.route("/api/profiles")
def api_profiles():
    return jsonify([describe_profile(p) for p in PROFILES.values()])


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
        # .docx храним час: автоисправление возьмёт его отсюда, без повторной загрузки с телефона
        upload_id = store.put("upload", f.filename, src_path=path) if ext == ".docx" else None

    data = report.to_dict(f.filename)
    data["report_id"] = store.put("report", f.filename, data=build_html_report(report, f.filename))
    data["upload_id"] = upload_id
    return jsonify(data)


@app.route("/api/fix", methods=["POST"])
def api_fix():
    if not current_user():
        return jsonify(error="Автоисправление доступно после входа в аккаунт университета.", code="login_required"), 401
    if not can_autofix():
        return jsonify(error="Сначала смените временный пароль.", code="password_change_required"), 403
    profile = request.form.get("profile", "vkr")
    if profile not in PROFILES:
        return jsonify(error="Неизвестный тип работы."), 400

    # Обычно файл уже лежит на сервере после проверки (upload_id). Если его нет
    # (прошёл час или сервер перезапускался) — клиент присылает файл заново.
    stored = store.get(request.form.get("upload_id", ""), "upload")
    f = request.files.get("file")
    if not stored and not (f and f.filename):
        return jsonify(error="Файл не найден на сервере, загрузите его ещё раз.", code="upload_expired"), 410
    filename = stored[1] if stored else f.filename
    if os.path.splitext(filename)[1].lower() != ".docx":
        return jsonify(error="Автоисправление работает только с файлами .docx."), 400

    with tempfile.TemporaryDirectory() as tmp:
        dst = os.path.join(tmp, "fixed.docx")
        if stored:
            src = stored[0]
        else:
            src = os.path.join(tmp, "upload.docx")
            f.save(src)
        try:
            before = run_normocontrol_cached(src, profile)  # после проверки уже в кеше
            result = fix_docx(src, dst, PROFILES[profile], before=before)
        except Exception:
            app.logger.exception("fix failed")
            return jsonify(error="Не удалось исправить файл. Убедитесь, что он не повреждён и не защищён паролем."), 422
        base = os.path.splitext(filename)[0]
        download_id = store.put("fixed", f"{base}_исправлено.docx", src_path=dst)

    payload = result.to_dict()
    payload["file"] = filename
    payload["download_id"] = download_id
    return jsonify(payload)


def _attachment(resp, ascii_name, name):
    resp.headers["Content-Disposition"] = f"attachment; filename={ascii_name}; filename*=UTF-8''{quote(name)}"
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.route("/api/fixed/<rid>")
def api_fixed_download(rid):
    entry = store.get(rid, "fixed")
    if not entry:
        return jsonify(error="Файл не найден или устарел. Запустите исправление заново."), 404
    path, name = entry
    resp = send_file(path, mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    return _attachment(resp, "fixed.docx", name)


@app.route("/api/report/<rid>")
def api_report_download(rid):
    entry = store.get(rid, "report")
    if not entry:
        return jsonify(error="Отчёт не найден или устарел. Проверьте файл заново."), 404
    path, name = entry
    resp = send_file(path, mimetype="text/html")
    return _attachment(resp, "normocontrol_report.html", f"{os.path.splitext(name)[0]}_report.html")


@app.errorhandler(413)
def too_large(e):
    return jsonify(error="Файл слишком большой (максимум 20 МБ)."), 413


@app.errorhandler(500)
def server_error(e):
    return jsonify(error="Внутренняя ошибка сервера."), 500


# ── сжатие и кеширование (заметно ускоряет первую загрузку на телефоне) ──

_COMPRESSIBLE = ("text/", "application/javascript", "application/json", "image/svg+xml")
_GZ_CACHE = {}   # путь статики → (исходный размер, сжатые байты)


@app.after_request
def compress_and_cache(resp):
    path = request.path
    if path.startswith("/assets/"):
        # у файлов Vite хеш в имени — можно кешировать навсегда
        resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    elif resp.mimetype == "text/html" and not path.startswith("/api/"):
        # index.html всегда свежий (иначе не увидят новый деплой) и личный — в нём данные о пользователе
        resp.headers["Cache-Control"] = "private, no-cache"
        resp.headers["Vary"] = "Cookie"

    if ("gzip" not in request.headers.get("Accept-Encoding", "")
            or resp.status_code != 200 or "Content-Encoding" in resp.headers
            or not (resp.mimetype or "").startswith(_COMPRESSIBLE)
            or resp.headers.get("Content-Disposition", "").startswith("attachment")):
        return resp
    resp.direct_passthrough = False
    data = resp.get_data()
    if len(data) < 1024:
        return resp
    static = path.startswith("/assets/")
    cached = _GZ_CACHE.get(path) if static else None
    if cached and cached[0] == len(data):
        gz = cached[1]
    else:
        gz = gzip.compress(data, compresslevel=6)
        if static:
            _GZ_CACHE[path] = (len(data), gz)
    resp.set_data(gz)
    resp.headers["Content-Encoding"] = "gzip"
    resp.headers["Vary"] = ", ".join(filter(None, [resp.headers.get("Vary"), "Accept-Encoding"]))
    resp.headers["Content-Length"] = str(len(gz))
    return resp


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
    if path and os.path.isfile(full) and path != "index.html":
        return send_from_directory(DIST_DIR, path)
    return Response(_index_html(), mimetype="text/html")  # клиентский роутинг (/vkr, /coursework)


_INDEX = {}   # mtime index.html → (до вставки, после вставки)


def _index_html():
    """
    index.html со встроенными профилями, конфигом и текущим пользователем (window.__BOOT__):
    страница рисуется сразу, без дополнительных запросов к API — на мобильном интернете это
    заметно ускоряет первый показ. Шаблон кешируется, данные о пользователе — на каждый запрос.
    """
    path = os.path.join(DIST_DIR, "index.html")
    mtime = os.path.getmtime(path)
    if _INDEX.get("mtime") != mtime:
        with open(path, encoding="utf-8") as fh:
            head, _, tail = fh.read().partition("</head>")
        _INDEX.update(mtime=mtime, head=head, tail=tail,
                      profiles=[describe_profile(p) for p in PROFILES.values()])
    boot = {"profiles": _INDEX["profiles"], "config": _client_config()}
    # "</" экранируем, чтобы строка в JSON не закрыла тег <script>
    payload = json.dumps(boot, ensure_ascii=False).replace("</", "<\\/")
    return f"{_INDEX['head']}<script>window.__BOOT__={payload}</script>\n</head>{_INDEX['tail']}"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
