# -*- coding: utf-8 -*-
"""
Учётные записи: регистрация для всех по email и учётки университета, которые выдаёт администратор.

Кто что может:
  * без входа и после обычной регистрации — проверка оформления бесплатно, автоисправление — за оплату;
  * подписка (SUBSCRIPTION_PRICE ₽ в месяц) — SUBSCRIPTION_LIMIT автоисправлений за календарный месяц;
    пока оплата не подключена, подписку выдаёт администратор в /admin;
  * пользователь с бесплатным доступом (его выдаёт администратор: учётки кафедры получают доступ
    сразу, зарегистрировавшимся его включают в /admin) — автоисправление бесплатно;
  * администратор — то же + страница управления учётками (/admin);
  * дополнительные проверки вуза (checker/packs) — только тем, кому их назначил администратор
    (таблица user_packs); настройки пакетов — в таблице check_packs.

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
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import Blueprint, jsonify, request, session, g, abort
from sqlalchemy import (
    MetaData, Table, Column, Integer, String, Boolean, DateTime, Text, create_engine, select, insert,
    update, delete, func, inspect, text,
)
from werkzeug.security import generate_password_hash, check_password_hash

from checker.packs import PACKS, settings_for
import mailer
import payments

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
    # бесплатное автоисправление: включает только администратор
    Column("free_autofix", Boolean, nullable=False, default=False),
    # зарегистрировался сам (а не получил учётку от администратора)
    Column("registered", Boolean, nullable=False, default=False),
    # когда пользователь дал согласие на обработку персональных данных (при регистрации)
    Column("consent_at", DateTime(timezone=True), nullable=True),
    # подписка действует до этого момента (None — нет подписки)
    Column("subscription_until", DateTime(timezone=True), nullable=True),
    # почта подтверждена кодом из письма (учётки от администратора и старые — считаются подтверждёнными)
    Column("email_verified", Boolean, nullable=False, default=True),
    # оплаченные и ещё не использованные разовые автоисправления
    Column("autofix_credits", Integer, nullable=False, default=0),
)

# заказы: разовое исправление (autofix) или подписка (subscription), оплата через ЮKassa
orders = Table(
    "orders", metadata,
    Column("id", String(32), primary_key=True),
    Column("user_id", Integer, nullable=False, index=True),
    Column("kind", String(16), nullable=False),
    Column("amount", Integer, nullable=False),               # ₽
    Column("status", String(16), nullable=False, default="pending"),   # pending | succeeded | canceled
    Column("payment_id", String(64), nullable=True, index=True),
    # что исправить после оплаты: работа, загруженная перед покупкой (хранится на сервере час)
    Column("upload_id", String(64), nullable=True),
    Column("profile", String(16), nullable=True),
    Column("standards", String(200), nullable=True),
    Column("file_name", String(255), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("paid_at", DateTime(timezone=True), nullable=True),
    Column("fulfilled", Boolean, nullable=False, default=False),       # начислено ли оплаченное
    Column("receipt_issued", Boolean, nullable=False, default=False),  # чек в «Мой налог» выдан
)
AUTOFIX_PRICE = int(os.environ.get("AUTOFIX_PRICE", "99"))

# коды из писем: подтверждение почты (verify) и сброс пароля (reset); храним только хеш
email_codes = Table(
    "email_codes", metadata,
    Column("user_id", Integer, primary_key=True),
    Column("purpose", String(16), primary_key=True),
    Column("code_hash", String(256), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("attempts", Integer, nullable=False, default=0),
)
CODE_TTL = timedelta(minutes=30)
CODE_ATTEMPTS = 5

# автоисправления по подписке — для лимита в месяц
autofix_log = Table(
    "autofix_log", metadata,
    Column("id", Integer, primary_key=True),
    Column("user_id", Integer, nullable=False, index=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

SUBSCRIPTION_PRICE = int(os.environ.get("SUBSCRIPTION_PRICE", "299"))
SUBSCRIPTION_LIMIT = int(os.environ.get("SUBSCRIPTION_LIMIT", "30"))

# дополнительные проверки: кому какой пакет назначен и настройки пакетов (JSON поверх значений из кода)
user_packs = Table(
    "user_packs", metadata,
    Column("user_id", Integer, primary_key=True),
    Column("pack_key", String(32), primary_key=True),
)
check_packs = Table(
    "check_packs", metadata,
    Column("key", String(32), primary_key=True),
    Column("settings", Text, nullable=False, default="{}"),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)

# колонки, добавленные после первого запуска, и значение для уже существующих строк:
# учётки, выданные администратором до появления регистрации, сохраняют бесплатный доступ
_ADDED_COLUMNS = {
    "free_autofix": "BOOLEAN NOT NULL DEFAULT TRUE",
    "registered": "BOOLEAN NOT NULL DEFAULT FALSE",
    "subscription_until": "{timestamp} NULL",
    "consent_at": "{timestamp} NULL",
    "email_verified": "BOOLEAN NOT NULL DEFAULT TRUE",
    "autofix_credits": "INTEGER NOT NULL DEFAULT 0",
}

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
    _add_missing_columns()
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


def _add_missing_columns():
    """create_all не меняет существующие таблицы — новые колонки добавляем сами."""
    have = {c["name"] for c in inspect(engine).get_columns("users")}
    with engine.begin() as c:
        timestamp = "TIMESTAMP WITH TIME ZONE" if engine.dialect.name == "postgresql" else "DATETIME"
        for name, ddl in _ADDED_COLUMNS.items():
            if name not in have:
                c.execute(text(f"ALTER TABLE users ADD COLUMN {name} {ddl.format(timestamp=timestamp)}"))
                log.info("в таблицу users добавлена колонка %s", name)


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
            free_autofix=True,
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
            "must_change_password": u["must_change_password"], "free_autofix": has_free_access(u),
            "subscription": subscription_state(u), "email_verified": bool(u["email_verified"]),
            "autofix_credits": u["autofix_credits"],
            "packs": [{"key": k, "short": PACKS[k].short, "title": PACKS[k].title,
                       "profiles": list(PACKS[k].profiles)} for k in assigned_packs(u["id"])]}


def assigned_packs(uid):
    with engine.connect() as c:
        keys = c.execute(select(user_packs.c.pack_key).where(user_packs.c.user_id == uid)).scalars().all()
    return [k for k in sorted(keys) if k in PACKS]


def packs_for_check(u):
    """Дополнительные проверки текущего пользователя: [(ключ, настройки JSON)] — для run_normocontrol."""
    if not u or u["must_change_password"]:
        return ()
    keys = assigned_packs(u["id"])
    if not keys:
        return ()
    with engine.connect() as c:
        saved = dict(c.execute(select(check_packs.c.key, check_packs.c.settings)
                               .where(check_packs.c.key.in_(keys))).all())
    return tuple((k, saved.get(k) or "{}") for k in keys)


def has_free_access(u):
    return bool(u and (u["role"] == "admin" or u["free_autofix"]))


def _aware(dt):
    # SQLite возвращает время без часового пояса — храним всегда UTC
    return dt.replace(tzinfo=timezone.utc) if dt is not None and dt.tzinfo is None else dt


def _month_start():
    now = _now()
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def subscription_state(u):
    """Подписка: активна ли, до какого числа, сколько исправлений использовано в этом месяце."""
    until = _aware(u.get("subscription_until"))
    active = bool(until and until > _now())
    used = 0
    if active:
        with engine.connect() as c:
            used = c.execute(select(func.count()).select_from(autofix_log).where(
                autofix_log.c.user_id == u["id"], autofix_log.c.created_at >= _month_start())).scalar()
    return {"active": active, "until": until.isoformat() if until else None,
            "used": used, "limit": SUBSCRIPTION_LIMIT, "left": max(0, SUBSCRIPTION_LIMIT - used) if active else 0}


def autofix_access(u):
    """
    Чем оплачено автоисправление: ("free", None) — бесплатный доступ, ("subscription", None) —
    подписка с остатком лимита, (None, код) — недоступно: login_required, password_change_required,
    email_unverified, limit_reached, payment_required.
    """
    if not u:
        return None, "login_required"
    if u["must_change_password"]:
        return None, "password_change_required"
    if not u["email_verified"]:
        return None, "email_unverified"
    if has_free_access(u):
        return "free", None
    sub = subscription_state(u)
    if sub["active"] and sub["left"] > 0:
        return "subscription", None
    if u["autofix_credits"] > 0:
        return "credit", None
    return None, "limit_reached" if sub["active"] else "payment_required"


def consume_credit(u):
    """Списать одно оплаченное исправление (после того как исправленный файл выдан)."""
    with engine.begin() as c:
        c.execute(update(users).where(users.c.id == u["id"], users.c.autofix_credits > 0)
                  .values(autofix_credits=users.c.autofix_credits - 1))


def record_autofix(u):
    with engine.begin() as c:
        c.execute(insert(autofix_log).values(user_id=u["id"], created_at=_now()))


def can_autofix():
    """Автоисправление доступно: бесплатный доступ от администратора или подписка с остатком лимита."""
    return autofix_access(current_user())[0] is not None


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
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
REGISTRATION_ENABLED = os.environ.get("REGISTRATION_ENABLED", "1") != "0"
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


REGISTER_WINDOW, REGISTER_LIMIT = 60 * 60, 5   # регистраций с одного IP в час


def _too_many(key, window=FAIL_WINDOW, limit=FAIL_LIMIT):
    now = time.time()
    with _FAILS_LOCK:
        hits = [t for t in _FAILS.get(key, []) if now - t < window]
        _FAILS[key] = hits
        return len(hits) >= limit


def _fail(key):
    with _FAILS_LOCK:
        _FAILS.setdefault(key, []).append(time.time())


# ── API: вход и аккаунт ───────────────────────────────────────────────────

@bp.get("/api/me")
def me():
    return jsonify(user=public_user(current_user()), autofix_enabled=can_autofix())


def _client_ip():
    return request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip()


def _start_session(row):
    session.clear()
    session.permanent = True
    session["uid"], session["ver"] = row["id"], row["session_version"]
    g.user = dict(row)


@bp.post("/api/register")
def register():
    """Обычная регистрация по email: вход сразу, автоисправление — за оплату, пока админ не откроет доступ."""
    if not REGISTRATION_ENABLED:
        return jsonify(error="Регистрация временно закрыта."), 403
    data = request.get_json(silent=True) or {}
    email = normalize_login(data.get("email"))
    name = (data.get("name") or "").strip()[:200]
    password = data.get("password") or ""
    if not EMAIL_RE.match(email) or len(email) > 64:
        return jsonify(error="Укажите настоящий email — он будет логином для входа."), 400
    err = _validate_new_password(password)
    if err:
        return jsonify(error=err), 400
    if data.get("consent") is not True:   # 152-ФЗ: согласие — отдельное явное действие
        return jsonify(error="Нужно согласие с офертой и на обработку персональных данных."), 400
    key = f"register:{_client_ip()}"
    if _too_many(key, REGISTER_WINDOW, REGISTER_LIMIT):
        return jsonify(error="Слишком много регистраций с вашего адреса. Попробуйте через час."), 429

    with engine.begin() as c:
        if c.execute(select(users.c.id).where(users.c.login == email)).first():
            return jsonify(error="Этот email уже зарегистрирован — войдите в аккаунт."), 409
        c.execute(insert(users).values(
            login=email, name=name or email.split("@")[0], password_hash=generate_password_hash(password),
            role="user", active=True, must_change_password=False, session_version=1, created_at=_now(),
            last_login_at=_now(), free_autofix=False, registered=True, consent_at=_now(),
            # пока почта не настроена, подтверждать нечем — аккаунт работает сразу
            email_verified=not mailer.enabled(),
        ))
        row = c.execute(select(users).where(users.c.login == email)).mappings().first()
    _fail(key)   # счётчик регистраций с этого IP
    _start_session(row)
    mail_sent = None
    if not row["email_verified"]:
        mail_sent = _send_code(row, "verify")
    return jsonify(user=public_user(row), autofix_enabled=can_autofix(), mail_sent=mail_sent), 201


@bp.post("/api/login")
def login():
    data = request.get_json(silent=True) or {}
    login_ = normalize_login(data.get("login"))
    password = data.get("password") or ""
    ip = _client_ip()
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
    _start_session(row)
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

def _admin_row(r, packs=None):
    return {
        "packs": packs if packs is not None else assigned_packs(r["id"]),
        "id": r["id"], "login": r["login"], "name": r["name"], "role": r["role"], "active": r["active"],
        "must_change_password": r["must_change_password"],
        "free_autofix": has_free_access(r), "registered": r["registered"],
        "subscription_until": _aware(r["subscription_until"]).isoformat() if r["subscription_until"] else None,
        "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        "last_login_at": r["last_login_at"].isoformat() if r["last_login_at"] else None,
    }


@bp.get("/api/admin/users")
@admin_required
def admin_list():
    with engine.connect() as c:
        rows = c.execute(select(users).order_by(func.lower(users.c.name), users.c.login)).mappings().all()
        assigned = {}
        for uid, key in c.execute(select(user_packs.c.user_id, user_packs.c.pack_key)).all():
            if key in PACKS:
                assigned.setdefault(uid, []).append(key)
    import legal
    return jsonify(users=[_admin_row(r, sorted(assigned.get(r["id"], []))) for r in rows],
                   db_ephemeral=DB_IS_EPHEMERAL, legal_missing=legal.missing(),
                   payments_enabled=payments.enabled(), payments_test=payments.test_mode())


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
        must_change_password=True, session_version=1, created_at=_now(), free_autofix=True,
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
    if "free_autofix" in data:
        values["free_autofix"] = bool(data["free_autofix"])
    if "subscription_days" in data:   # пока оплата не подключена — подписку выдаёт администратор
        days = data["subscription_days"]
        if not isinstance(days, int) or isinstance(days, bool) or not 1 <= days <= 366:
            return jsonify(error="Срок подписки — от 1 до 366 дней."), 400
    if data.get("subscription_cancel"):
        values["subscription_until"] = None
    packs = data.get("packs")
    if packs is not None:
        if not isinstance(packs, list) or any(k not in PACKS for k in packs):
            return jsonify(error="Неизвестная дополнительная проверка."), 400
    if not values and packs is None and "subscription_days" not in data:
        return jsonify(error="Нечего менять."), 400
    with engine.begin() as c:
        row = c.execute(select(users).where(users.c.id == uid)).mappings().first()
        if not row:
            return jsonify(error="Пользователь не найден."), 404
        if values.get("active") is False or values.get("role") == "user":
            values["session_version"] = row["session_version"] + 1  # разлогинить сразу
        if "subscription_days" in data:
            # продление: с конца текущей подписки, если она ещё действует
            start = max(_now(), _aware(row["subscription_until"]) or _now())
            values["subscription_until"] = start + timedelta(days=data["subscription_days"])
        if values:
            c.execute(update(users).where(users.c.id == uid).values(**values))
        if packs is not None:
            c.execute(delete(user_packs).where(user_packs.c.user_id == uid))
            for k in sorted(set(packs)):
                c.execute(insert(user_packs).values(user_id=uid, pack_key=k))
        row = c.execute(select(users).where(users.c.id == uid)).mappings().first()
    return jsonify(user=_admin_row(row))


@bp.delete("/api/admin/users/<int:uid>")
@admin_required
def admin_delete(uid):
    if uid == current_user()["id"]:
        return jsonify(error="Нельзя удалить самого себя."), 400
    with engine.begin() as c:
        c.execute(delete(user_packs).where(user_packs.c.user_id == uid))
        res = c.execute(delete(users).where(users.c.id == uid))
    if not res.rowcount:
        return jsonify(error="Пользователь не найден."), 404
    return jsonify(ok=True)

# ── API: дополнительные проверки ──────────────────────────────────────────

def _pack_row(c, key):
    pack = PACKS[key]
    raw = c.execute(select(check_packs.c.settings).where(check_packs.c.key == key)).scalar()
    used = c.execute(select(func.count()).select_from(user_packs).where(user_packs.c.pack_key == key)).scalar()
    return {"key": key, "title": pack.title, "short": pack.short, "description": pack.description,
            "profiles": list(pack.profiles), "settings": settings_for(key, raw), "defaults": pack.defaults,
            "customized": bool(raw and raw != "{}"), "users": used}


@bp.get("/api/admin/packs")
@admin_required
def admin_packs():
    with engine.connect() as c:
        return jsonify(packs=[_pack_row(c, k) for k in PACKS])


def _validate_settings(key, data):
    """Только известные ключи и тех же типов, что значения по умолчанию."""
    defaults = PACKS[key].defaults
    if not isinstance(data, dict):
        raise ValueError("Настройки — объект JSON: {\"ключ\": значение}.")
    for k, v in data.items():
        if k not in defaults:
            raise ValueError(f"Неизвестная настройка «{k}». Доступны: {', '.join(defaults)}.")
        d = defaults[k]
        if isinstance(d, bool) != isinstance(v, bool) or not isinstance(v, type(d)):
            raise ValueError(f"«{k}»: ожидается {type(d).__name__}, как в значении по умолчанию.")
        if isinstance(d, list) and not all(isinstance(x, str) and x.strip() for x in v):
            raise ValueError(f"«{k}»: список непустых строк.")
    # храним только отличия от значений по умолчанию — тогда обновления кода подхватываются
    return {k: v for k, v in data.items() if v != defaults[k]}


@bp.put("/api/admin/packs/<key>")
@admin_required
def admin_pack_settings(key):
    if key not in PACKS:
        return jsonify(error="Неизвестная дополнительная проверка."), 404
    data = (request.get_json(silent=True) or {}).get("settings")
    try:
        diff = _validate_settings(key, data if data is not None else {})
    except ValueError as e:
        return jsonify(error=str(e)), 400
    import json as _json
    with engine.begin() as c:
        c.execute(delete(check_packs).where(check_packs.c.key == key))
        if diff:
            c.execute(insert(check_packs).values(key=key, settings=_json.dumps(diff, ensure_ascii=False),
                                                 updated_at=_now()))
        return jsonify(pack=_pack_row(c, key))

# ── почта: подтверждение и сброс пароля ───────────────────────────────────

def _issue_code(uid, purpose):
    code = f"{secrets.randbelow(10 ** 6):06d}"
    with engine.begin() as c:
        c.execute(delete(email_codes).where(email_codes.c.user_id == uid, email_codes.c.purpose == purpose))
        c.execute(insert(email_codes).values(user_id=uid, purpose=purpose, code_hash=generate_password_hash(code),
                                             expires_at=_now() + CODE_TTL, attempts=0))
    return code


def _check_code(uid, purpose, code):
    """Код верный и не истёк — запись удаляется; неверный — счётчик попыток (после 5 код сгорает)."""
    code = re.sub(r"\D", "", code or "")
    with engine.begin() as c:
        row = c.execute(select(email_codes).where(email_codes.c.user_id == uid,
                                                  email_codes.c.purpose == purpose)).mappings().first()
        if not row or _aware(row["expires_at"]) < _now() or row["attempts"] >= CODE_ATTEMPTS:
            return "expired"
        if not check_password_hash(row["code_hash"], code):
            c.execute(update(email_codes).where(email_codes.c.user_id == uid, email_codes.c.purpose == purpose)
                      .values(attempts=row["attempts"] + 1))
            return "wrong"
        c.execute(delete(email_codes).where(email_codes.c.user_id == uid, email_codes.c.purpose == purpose))
    return "ok"


def _send_code(row, purpose):
    """Новый код на почту пользователя. True — письмо ушло, False — почтовый сервис не ответил."""
    site = (os.environ.get("SITE_URL") or "https://normocontrol.site").rstrip("/")
    subject, text = mailer.code_letter(purpose, _issue_code(row["id"], purpose), site)
    try:
        mailer.send(row["login"], subject, text)
        return True
    except Exception:
        log.exception("не удалось отправить письмо (%s)", purpose)
        return False


MAIL_WINDOW, MAIL_LIMIT = 60 * 60, 5   # писем одному адресу в час


@bp.post("/api/email/resend")
@login_required
def email_resend():
    u = current_user()
    if u["email_verified"]:
        return jsonify(user=public_user(u), autofix_enabled=can_autofix())
    key = f"mail:{u['id']}"
    if _too_many(key, MAIL_WINDOW, MAIL_LIMIT):
        return jsonify(error="Слишком много писем подряд. Попробуйте через час."), 429
    _fail(key)
    if not _send_code(u, "verify"):
        return jsonify(error="Не удалось отправить письмо. Попробуйте ещё раз через несколько минут."), 502
    return jsonify(ok=True)


@bp.post("/api/email/verify")
@login_required
def email_verify():
    u = current_user()
    if not u["email_verified"]:
        res = _check_code(u["id"], "verify", (request.get_json(silent=True) or {}).get("code"))
        if res == "wrong":
            return jsonify(error="Неверный код. Проверьте письмо и попробуйте ещё раз."), 400
        if res == "expired":
            return jsonify(error="Код устарел или введён неверно слишком много раз — запросите новый.",
                           code="code_expired"), 400
        with engine.begin() as c:
            c.execute(update(users).where(users.c.id == u["id"]).values(email_verified=True))
        u["email_verified"] = True
    return jsonify(user=public_user(u), autofix_enabled=can_autofix())


@bp.post("/api/password/forgot")
def password_forgot():
    """Код для сброса пароля. Ответ одинаковый, есть такой email или нет — чтобы не выдавать базу."""
    if not mailer.enabled():
        return jsonify(error="Восстановление пароля по почте пока недоступно. Напишите администратору."), 503
    email = normalize_login((request.get_json(silent=True) or {}).get("email"))
    keys = (f"forgot-ip:{_client_ip()}", f"forgot:{email}")
    if not EMAIL_RE.match(email):
        return jsonify(error="Укажите email, с которым вы регистрировались."), 400
    if _too_many(keys[0], MAIL_WINDOW, 10) or _too_many(keys[1], MAIL_WINDOW, 3):
        return jsonify(error="Слишком много запросов. Попробуйте через час."), 429
    for k in keys:
        _fail(k)
    with engine.connect() as c:
        row = c.execute(select(users).where(users.c.login == email)).mappings().first()
    if row and row["active"]:
        _send_code(row, "reset")
    return jsonify(ok=True)


@bp.post("/api/password/reset")
def password_reset():
    data = request.get_json(silent=True) or {}
    email = normalize_login(data.get("email"))
    err = _validate_new_password(data.get("password") or "")
    if err:
        return jsonify(error=err), 400
    with engine.connect() as c:
        row = c.execute(select(users).where(users.c.login == email)).mappings().first()
    res = _check_code(row["id"], "reset", data.get("code")) if row and row["active"] else "expired"
    if res == "wrong":
        return jsonify(error="Неверный код. Проверьте письмо и попробуйте ещё раз."), 400
    if res == "expired":
        return jsonify(error="Код устарел или неверен — запросите новый.", code="code_expired"), 400
    ver = row["session_version"] + 1   # остальные устройства выходят из аккаунта
    with engine.begin() as c:
        c.execute(update(users).where(users.c.id == row["id"]).values(
            password_hash=generate_password_hash(data["password"]), must_change_password=False,
            session_version=ver, email_verified=True, last_login_at=_now()))
        row = c.execute(select(users).where(users.c.id == row["id"])).mappings().first()
    _start_session(row)
    return jsonify(user=public_user(row), autofix_enabled=can_autofix())

# ── оплата ────────────────────────────────────────────────────────────────

def _site():
    return (os.environ.get("SITE_URL") or request.host_url).rstrip("/")


def _order_public(o):
    return {"id": o["id"], "kind": o["kind"], "amount": o["amount"], "status": o["status"],
            "upload_id": o["upload_id"], "profile": o["profile"],
            "standards": [s for s in (o["standards"] or "").split(",") if s], "file_name": o["file_name"],
            "created_at": o["created_at"].isoformat() if o["created_at"] else None}


def _fulfill(order_id):
    """Начислить оплаченное ровно один раз (повторные уведомления и обновления страницы — без эффекта)."""
    with engine.begin() as c:
        claimed = c.execute(update(orders).where(orders.c.id == order_id, orders.c.fulfilled.is_(False))
                            .values(fulfilled=True)).rowcount
        if not claimed:
            return
        o = c.execute(select(orders).where(orders.c.id == order_id)).mappings().first()
        if o["kind"] == "autofix":
            c.execute(update(users).where(users.c.id == o["user_id"])
                      .values(autofix_credits=users.c.autofix_credits + 1))
        else:
            row = c.execute(select(users.c.subscription_until).where(users.c.id == o["user_id"])).first()
            start = max(_now(), _aware(row[0]) or _now())
            c.execute(update(users).where(users.c.id == o["user_id"])
                      .values(subscription_until=start + timedelta(days=30)))
    log.info("заказ %s оплачен и выполнен", order_id)


def sync_order(order_id):
    """Узнать статус платежа у ЮKassa и, если оплачен, выполнить заказ. Возвращает заказ из базы."""
    with engine.connect() as c:
        o = c.execute(select(orders).where(orders.c.id == order_id)).mappings().first()
    if not o or not o["payment_id"] or (o["status"] != "pending" and o["fulfilled"] == (o["status"] == "succeeded")):
        return o
    p = payments.get_payment(o["payment_id"])
    paid = (p.get("status") == "succeeded" and p.get("paid")
            and (p.get("metadata") or {}).get("order_id") == order_id
            and float((p.get("amount") or {}).get("value", 0)) == float(o["amount"]))
    status = "succeeded" if paid else "canceled" if p.get("status") == "canceled" else "pending"
    if status != o["status"]:
        with engine.begin() as c:
            c.execute(update(orders).where(orders.c.id == order_id).values(
                status=status, paid_at=_now() if status == "succeeded" else None))
    if status == "succeeded":
        _fulfill(order_id)
    with engine.connect() as c:
        return c.execute(select(orders).where(orders.c.id == order_id)).mappings().first()


@bp.post("/api/orders")
@login_required
def order_create():
    """Заказ: {"kind": "autofix" | "subscription", "upload_id", "profile", "standards", "file_name"}."""
    if not payments.enabled():
        return jsonify(error="Оплата подключается и скоро заработает.", code="payments_disabled"), 503
    u = current_user()
    if not u["email_verified"]:
        return jsonify(error="Подтвердите почту — на неё придут ответы по оплате и возвратам.",
                       code="email_unverified"), 403
    data = request.get_json(silent=True) or {}
    kind = data.get("kind")
    if kind not in ("autofix", "subscription"):
        return jsonify(error="Неизвестный товар."), 400
    amount = AUTOFIX_PRICE if kind == "autofix" else SUBSCRIPTION_PRICE
    order_id = payments.new_order_id()
    stds = data.get("standards") or []
    with engine.begin() as c:
        c.execute(insert(orders).values(
            id=order_id, user_id=u["id"], kind=kind, amount=amount, status="pending", created_at=_now(),
            upload_id=(data.get("upload_id") or None) if kind == "autofix" else None,
            profile=(data.get("profile") or None) if kind == "autofix" else None,
            standards=",".join(stds)[:200] if kind == "autofix" and isinstance(stds, list) else None,
            file_name=(data.get("file_name") or "")[:255] or None))
    description = (f"Автоисправление оформления работы, заказ {order_id[:8]}" if kind == "autofix"
                   else f"Подписка на 30 дней ({SUBSCRIPTION_LIMIT} автоисправлений в месяц), заказ {order_id[:8]}")
    try:
        payment_id, url = payments.create_payment(order_id, amount, description, f"{_site()}/pay/{order_id}")
    except payments.PaymentError:
        with engine.begin() as c:
            c.execute(update(orders).where(orders.c.id == order_id).values(status="canceled"))
        return jsonify(error="Не удалось создать платёж. Попробуйте ещё раз через минуту."), 502
    with engine.begin() as c:
        c.execute(update(orders).where(orders.c.id == order_id).values(payment_id=payment_id))
    return jsonify(order_id=order_id, confirmation_url=url), 201


@bp.get("/api/orders/<order_id>")
@login_required
def order_status(order_id):
    u = current_user()
    with engine.connect() as c:
        o = c.execute(select(orders).where(orders.c.id == order_id)).mappings().first()
    if not o or (o["user_id"] != u["id"] and u["role"] != "admin"):
        return jsonify(error="Заказ не найден."), 404
    try:
        o = sync_order(order_id)
    except payments.PaymentError:
        pass   # ЮKassa недоступна — покажем последний известный статус, страница спросит ещё раз
    _load_user()   # начисление могло изменить исправления и подписку
    return jsonify(order=_order_public(o), user=public_user(current_user()), autofix_enabled=can_autofix())


@bp.post("/api/payments/webhook")
def payments_webhook():
    """
    Уведомление ЮKassa (payment.succeeded / payment.canceled). Тело — только подсказка, какой
    платёж проверить: статус и сумму всё равно берём из API ЮKassa.
    """
    obj = (request.get_json(silent=True) or {}).get("object") or {}
    payment_id = str(obj.get("id") or "")[:64]
    if not payment_id:
        return jsonify(ok=True)
    with engine.connect() as c:
        o = c.execute(select(orders.c.id).where(orders.c.payment_id == payment_id)).first()
    if o:
        try:
            sync_order(o[0])
        except payments.PaymentError:
            return jsonify(error="retry"), 502   # ЮKassa повторит уведомление позже
    return jsonify(ok=True)


@bp.get("/api/admin/orders")
@admin_required
def admin_orders():
    with engine.connect() as c:
        rows = c.execute(select(orders, users.c.login).join(users, users.c.id == orders.c.user_id, isouter=True)
                         .where(orders.c.status != "pending")
                         .order_by(orders.c.created_at.desc()).limit(300)).mappings().all()
    return jsonify(orders=[{
        "id": r["id"], "login": r["login"], "kind": r["kind"], "amount": r["amount"], "status": r["status"],
        "paid_at": _aware(r["paid_at"]).isoformat() if r["paid_at"] else None,
        "receipt_issued": r["receipt_issued"]} for r in rows if r["status"] == "succeeded"])


@bp.patch("/api/admin/orders/<order_id>")
@admin_required
def admin_order_update(order_id):
    value = bool((request.get_json(silent=True) or {}).get("receipt_issued"))
    with engine.begin() as c:
        res = c.execute(update(orders).where(orders.c.id == order_id).values(receipt_issued=value))
    if not res.rowcount:
        return jsonify(error="Заказ не найден."), 404
    return jsonify(ok=True)
