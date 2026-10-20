# -*- coding: utf-8 -*-
"""
Учётные записи университета: вход по логину и паролю, которые выдаёт администратор.

Кто что может:
  * без входа — проверка оформления (бесплатно для всех); автоисправление — позже за оплату;
  * вошедший пользователь университета — проверка и автоисправление бесплатно;
  * администратор — то же + страница управления учётками (/admin).

База: DATABASE_URL (PostgreSQL на Render/Neon), без неё — SQLite-файл в папке instance/
(годится для разработки; на Render без постоянного диска такой файл стирается при деплое).
Первый администратор создаётся из переменных ADMIN_LOGIN / ADMIN_PASSWORD при запуске.
"""

import os
import re
import time
import secrets
import logging
import threading
from datetime import datetime, timezone
from functools import wraps

from flask import Blueprint, jsonify, request, session, g, abort
from sqlalchemy import (
    MetaData, Table, Column, Integer, String, Boolean, DateTime, create_engine, select, insert,
    update, delete, func,
)
from werkzeug.security import generate_password_hash, check_password_hash

log = logging.getLogger("normocontrol.auth")
bp = Blueprint("auth", __name__)

# ── база ──────────────────────────────────────────────────────────────────

metadata = MetaData()
users = Table(
    "users", metadata,
    Column("id", Integer, primary_key=True),
    Column("login", String(64), nullable=False, unique=True),
    Column("name", String(200), nullable=False, default=""),
    Column("password_hash", String(256), nullable=False),
    Column("role", String(16), nullable=False, default="user"),        # user | admin
    Column("active", Boolean, nullable=False, default=True),
    Column("must_change_password", Boolean, nullable=False, default=True),
    # увеличивается при сбросе/смене пароля и блокировке — старые сессии перестают действовать
    Column("session_version", Integer, nullable=False, default=1),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("last_login_at", DateTime(timezone=True), nullable=True),
)

engine = None
DB_IS_EPHEMERAL = False


def _db_url(base_dir):
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        os.makedirs(os.path.join(base_dir, "instance"), exist_ok=True)
        return "sqlite:///" + os.path.join(base_dir, "instance", "normocontrol.db").replace("\\", "/")
    # Render/Heroku отдают postgres:// — SQLAlchemy нужен явный драйвер
    return re.sub(r"^postgres(ql)?://", "postgresql+psycopg://", url)


def _now():
    return datetime.now(timezone.utc)


def init_app(app, base_dir):
    global engine, DB_IS_EPHEMERAL
    url = _db_url(base_dir)
    engine = create_engine(url, pool_pre_ping=True, future=True)
    metadata.create_all(engine)
    # продакшен — любой хостинг, где задан основной адрес сайта (Timeweb, Render…)
    production = bool(os.environ.get("SITE_URL") or os.environ.get("RENDER") or os.environ.get("FORCE_HTTPS"))
    DB_IS_EPHEMERAL = url.startswith("sqlite") and production
    if DB_IS_EPHEMERAL:
        log.warning("DATABASE_URL не задан: учётки хранятся в SQLite внутри контейнера и пропадут при следующем деплое")

    secret = os.environ.get("SECRET_KEY")
    if not secret:
        secret = secrets.token_hex(32)
        log.warning("SECRET_KEY не задан: сгенерирован временный, после перезапуска все выйдут из аккаунтов")
    app.secret_key = secret
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        # cookie только по HTTPS, когда сайт работает на своём домене с SSL
        SESSION_COOKIE_SECURE=bool(os.environ.get("SITE_URL", "").startswith("https://")
                                   or os.environ.get("RENDER") or os.environ.get("FORCE_HTTPS")),
        PERMANENT_SESSION_LIFETIME=60 * 60 * 24 * 30,
    )
    _bootstrap_admin()
    app.register_blueprint(bp)
    app.before_request(_load_user)
    app.before_request(_check_origin)


def _bootstrap_admin():
    """Создаёт администратора из ADMIN_LOGIN/ADMIN_PASSWORD, если его ещё нет (пароль не перезаписывает)."""
    login = normalize_login(os.environ.get("ADMIN_LOGIN", ""))
    password = os.environ.get("ADMIN_PASSWORD", "")
    if not login or not password:
        return
    with engine.begin() as c:
        if c.execute(select(users.c.id).where(users.c.login == login)).first():
            return
        c.execute(insert(users).values(
            login=login, name="Администратор", password_hash=generate_password_hash(password),
            role="admin", active=True, must_change_password=False, session_version=1, created_at=_now(),
        ))
    log.info("создан администратор %s", login)


# ── текущий пользователь ──────────────────────────────────────────────────

def _load_user():
    g.user = None
    uid, ver = session.get("uid"), session.get("ver")
    if not uid:
        return
    with engine.connect() as c:
        row = c.execute(select(users).where(users.c.id == uid)).mappings().first()
    if not row or not row["active"] or row["session_version"] != ver:
        session.clear()
        return
    g.user = dict(row)


def current_user():
    return getattr(g, "user", None)


def public_user(u):
    if not u:
        return None
    return {"id": u["id"], "login": u["login"], "name": u["name"], "role": u["role"],
            "must_change_password": u["must_change_password"]}


def can_autofix():
    """Автоисправление: бесплатно для вошедших пользователей университета (оплата — следующий этап)."""
    u = current_user()
    return bool(u and not u["must_change_password"])


def _check_origin():
    """Запросы, меняющие данные, принимаем только со своего сайта (защита от CSRF)."""
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    origin = request.headers.get("Origin")
    if origin and origin.rstrip("/") != request.host_url.rstrip("/"):
        # за прокси Render схема может отличаться (http/https) — сравниваем только хост
        if re.sub(r"^https?://", "", origin.rstrip("/")) != request.host:
            abort(403)


def login_required(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        if not current_user():
            return jsonify(error="Нужно войти в аккаунт."), 401
        return fn(*a, **kw)
    return wrapper


def admin_required(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        u = current_user()
        if not u:
            return jsonify(error="Нужно войти в аккаунт."), 401
        if u["role"] != "admin":
            return jsonify(error="Недостаточно прав."), 403
        return fn(*a, **kw)
    return wrapper


# ── вспомогательное ───────────────────────────────────────────────────────

LOGIN_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{1,63}$")
PASSWORD_ALPHABET = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # без 0/O, 1/l/I
TRANSLIT = dict(zip(
    "абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
    ["a", "b", "v", "g", "d", "e", "e", "zh", "z", "i", "y", "k", "l", "m", "n", "o", "p", "r", "s", "t",
     "u", "f", "kh", "ts", "ch", "sh", "shch", "", "y", "", "e", "yu", "ya"],
))


def normalize_login(s):
    return (s or "").strip().lower()


def generate_password(n=10):
    return "".join(secrets.choice(PASSWORD_ALPHABET) for _ in range(n))


def login_from_name(name):
    """«Иванов Иван Петрович» → ivanov.ip"""
    parts = [p for p in re.split(r"\s+", (name or "").strip().lower()) if p]
    tr = lambda w: "".join(TRANSLIT.get(ch, ch if ch.isascii() and ch.isalnum() else "") for ch in w)
    if not parts:
        return "user"
    base = tr(parts[0]) or "user"
    initials = "".join(tr(p)[:1] for p in parts[1:3])
    return f"{base}.{initials}" if initials else base


def _unique_login(c, wanted):
    login, n = wanted, 1
    while c.execute(select(users.c.id).where(users.c.login == login)).first():
        n += 1
        login = f"{wanted}{n}"
    return login


def _validate_new_password(pw):
    if len(pw or "") < 8:
        return "Пароль должен быть не короче 8 символов."
    return None


# ── защита от подбора пароля ──────────────────────────────────────────────

_FAILS = {}
_FAILS_LOCK = threading.Lock()
FAIL_WINDOW, FAIL_LIMIT = 15 * 60, 10


def _too_many(key):
    now = time.time()
    with _FAILS_LOCK:
        hits = [t for t in _FAILS.get(key, []) if now - t < FAIL_WINDOW]
        _FAILS[key] = hits
        return len(hits) >= FAIL_LIMIT


def _fail(key):
    with _FAILS_LOCK:
        _FAILS.setdefault(key, []).append(time.time())


# ── API: вход и аккаунт ───────────────────────────────────────────────────

@bp.get("/api/me")
def me():
    return jsonify(user=public_user(current_user()), autofix_enabled=can_autofix())


@bp.post("/api/login")
def login():
    data = request.get_json(silent=True) or {}
    login_ = normalize_login(data.get("login"))
    password = data.get("password") or ""
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip()
    keys = (f"ip:{ip}", f"login:{login_}")
    if any(_too_many(k) for k in keys):
        return jsonify(error="Слишком много неудачных попыток. Попробуйте через 15 минут."), 429

    with engine.connect() as c:
        row = c.execute(select(users).where(users.c.login == login_)).mappings().first()
    if not row or not check_password_hash(row["password_hash"], password):
        for k in keys:
            _fail(k)
        return jsonify(error="Неверный логин или пароль."), 401
    if not row["active"]:
        return jsonify(error="Учётная запись заблокирована. Обратитесь к администратору."), 403

    with engine.begin() as c:
        c.execute(update(users).where(users.c.id == row["id"]).values(last_login_at=_now()))
    session.clear()
    session.permanent = True
    session["uid"], session["ver"] = row["id"], row["session_version"]
    g.user = dict(row)
    return jsonify(user=public_user(row), autofix_enabled=can_autofix())


@bp.post("/api/logout")
def logout():
    session.clear()
    return jsonify(ok=True)


@bp.post("/api/account/password")
@login_required
def change_password():
    data = request.get_json(silent=True) or {}
    u = current_user()
    if not check_password_hash(u["password_hash"], data.get("current") or ""):
        return jsonify(error="Текущий пароль указан неверно."), 400
    new = data.get("new") or ""
    err = _validate_new_password(new)
    if err:
        return jsonify(error=err), 400
    if new == data.get("current"):
        return jsonify(error="Новый пароль должен отличаться от текущего."), 400
    ver = u["session_version"] + 1
    with engine.begin() as c:
        c.execute(update(users).where(users.c.id == u["id"]).values(
            password_hash=generate_password_hash(new), must_change_password=False, session_version=ver))
    session["ver"] = ver   # текущая сессия остаётся, остальные устройства разлогиниваются
    u.update(must_change_password=False, session_version=ver)
    return jsonify(user=public_user(u), autofix_enabled=can_autofix())


# ── API: администрирование ────────────────────────────────────────────────

def _admin_row(r):
    return {
        "id": r["id"], "login": r["login"], "name": r["name"], "role": r["role"], "active": r["active"],
        "must_change_password": r["must_change_password"],
        "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        "last_login_at": r["last_login_at"].isoformat() if r["last_login_at"] else None,
    }


@bp.get("/api/admin/users")
@admin_required
def admin_list():
    with engine.connect() as c:
        rows = c.execute(select(users).order_by(func.lower(users.c.name), users.c.login)).mappings().all()
    return jsonify(users=[_admin_row(r) for r in rows], db_ephemeral=DB_IS_EPHEMERAL)


def _create(c, name, login_=None, role="user"):
    name = (name or "").strip()[:200]
    if login_:
        login_ = normalize_login(login_)
        if not LOGIN_RE.match(login_):
            raise ValueError("Логин: латинские буквы, цифры, точка, дефис или подчёркивание, от 2 символов.")
        if c.execute(select(users.c.id).where(users.c.login == login_)).first():
            raise ValueError(f"Логин «{login_}» уже занят.")
    else:
        login_ = _unique_login(c, login_from_name(name))
    password = generate_password()
    c.execute(insert(users).values(
        login=login_, name=name or login_, password_hash=generate_password_hash(password),
        role=role if role in ("user", "admin") else "user", active=True,
        must_change_password=True, session_version=1, created_at=_now(),
    ))
    return {"name": name or login_, "login": login_, "password": password}


@bp.post("/api/admin/users")
@admin_required
def admin_create():
    data = request.get_json(silent=True) or {}
    if not (data.get("name") or "").strip() and not data.get("login"):
        return jsonify(error="Укажите ФИО или логин."), 400
    try:
        with engine.begin() as c:
            created = _create(c, data.get("name"), data.get("login"), data.get("role", "user"))
    except ValueError as e:
        return jsonify(error=str(e)), 400
    return jsonify(created=[created])


@bp.post("/api/admin/users/bulk")
@admin_required
def admin_bulk():
    data = request.get_json(silent=True) or {}
    names = [n.strip() for n in (data.get("names") or []) if n and n.strip()]
    if not names:
        return jsonify(error="Список пуст: одно ФИО на строку."), 400
    if len(names) > 500:
        return jsonify(error="Не больше 500 человек за раз."), 400
    with engine.begin() as c:
        created = [_create(c, n) for n in names]
    return jsonify(created=created)


@bp.post("/api/admin/users/<int:uid>/reset")
@admin_required
def admin_reset(uid):
    password = generate_password()
    with engine.begin() as c:
        row = c.execute(select(users).where(users.c.id == uid)).mappings().first()
        if not row:
            return jsonify(error="Пользователь не найден."), 404
        c.execute(update(users).where(users.c.id == uid).values(
            password_hash=generate_password_hash(password), must_change_password=True,
            session_version=row["session_version"] + 1))
    return jsonify(created=[{"name": row["name"], "login": row["login"], "password": password}])


@bp.patch("/api/admin/users/<int:uid>")
@admin_required
def admin_update(uid):
    data = request.get_json(silent=True) or {}
    me_ = current_user()
    values = {}
    if "name" in data:
        values["name"] = (data["name"] or "").strip()[:200]
    if "active" in data:
        if uid == me_["id"] and not data["active"]:
            return jsonify(error="Нельзя заблокировать самого себя."), 400
        values["active"] = bool(data["active"])
    if "role" in data:
        if data["role"] not in ("user", "admin"):
            return jsonify(error="Неизвестная роль."), 400
        if uid == me_["id"] and data["role"] != "admin":
            return jsonify(error="Нельзя снять права администратора с самого себя."), 400
        values["role"] = data["role"]
    if not values:
        return jsonify(error="Нечего менять."), 400
    with engine.begin() as c:
        row = c.execute(select(users).where(users.c.id == uid)).mappings().first()
        if not row:
            return jsonify(error="Пользователь не найден."), 404
        if values.get("active") is False or values.get("role") == "user":
            values["session_version"] = row["session_version"] + 1  # разлогинить сразу
        c.execute(update(users).where(users.c.id == uid).values(**values))
        row = c.execute(select(users).where(users.c.id == uid)).mappings().first()
    return jsonify(user=_admin_row(row))


@bp.delete("/api/admin/users/<int:uid>")
@admin_required
def admin_delete(uid):
    if uid == current_user()["id"]:
        return jsonify(error="Нельзя удалить самого себя."), 400
    with engine.begin() as c:
        res = c.execute(delete(users).where(users.c.id == uid))
    if not res.rowcount:
        return jsonify(error="Пользователь не найден."), 404
    return jsonify(ok=True)
