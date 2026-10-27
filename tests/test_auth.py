# -*- coding: utf-8 -*-
"""Учётки университета: вход, временный пароль, права администратора, доступ к исправлению."""

import io
import json
import os
import re

import app as server
import make_docs as md

ADMIN = {"login": "admin", "password": "admin-pass-123"}


def client():
    return server.app.test_client()


def login(c, creds):
    return c.post("/api/login", json=creds)


def admin_client():
    c = client()
    assert login(c, ADMIN).status_code == 200
    return c


def create_user(name="Иванов Иван Петрович"):
    r = admin_client().post("/api/admin/users", json={"name": name})
    assert r.status_code == 200
    return r.get_json()["created"][0]


def docx_bytes():
    buf = io.BytesIO()
    doc = md.good_document()
    doc.styles["Normal"].paragraph_format.line_spacing = 1.0
    doc.save(buf)
    return buf.getvalue()


def fix_request(c):
    return c.post("/api/fix", data={"profile": "vkr", "file": (io.BytesIO(docx_bytes()), "w.docx")},
                  content_type="multipart/form-data")


def test_anonymous_can_check_but_not_fix():
    c = client()
    r = c.post("/api/check", data={"profile": "vkr", "file": (io.BytesIO(docx_bytes()), "w.docx")},
               content_type="multipart/form-data")
    assert r.status_code == 200
    r = fix_request(c)
    assert r.status_code == 401 and r.get_json()["code"] == "login_required"
    assert c.get("/api/me").get_json() == {"user": None, "autofix_enabled": False}


def test_wrong_password():
    assert login(client(), {"login": "admin", "password": "nope"}).status_code == 401
    assert login(client(), {"login": "nobody", "password": "nope"}).status_code == 401


def test_new_user_must_change_temporary_password_before_fixing():
    u = create_user()
    assert u["login"] == "ivanov.ip" and len(u["password"]) == 10
    c = client()
    r = login(c, {"login": u["login"], "password": u["password"]})
    assert r.status_code == 200 and r.get_json()["user"]["must_change_password"] is True
    assert fix_request(c).status_code == 403

    r = c.post("/api/account/password", json={"current": u["password"], "new": "short"})
    assert r.status_code == 400
    r = c.post("/api/account/password", json={"current": u["password"], "new": "new-password-1"})
    assert r.status_code == 200 and r.get_json()["autofix_enabled"] is True
    assert fix_request(c).status_code == 200


def test_login_is_case_insensitive_and_logins_are_unique():
    a = create_user("Петров Пётр")
    b = create_user("Петров Павел")
    assert a["login"] == "petrov.p" and b["login"] == "petrov.p2"
    assert login(client(), {"login": "PETROV.P", "password": a["password"]}).status_code == 200


def test_regular_user_has_no_admin_access():
    u = create_user("Сидоров Сидор")
    c = client()
    login(c, {"login": u["login"], "password": u["password"]})
    assert c.get("/api/admin/users").status_code == 403
    assert client().get("/api/admin/users").status_code == 401


def test_block_and_reset_invalidate_sessions():
    u = create_user("Блокируемый Борис")
    c = client()
    login(c, {"login": u["login"], "password": u["password"]})
    assert c.get("/api/me").get_json()["user"]["login"] == u["login"]

    adm = admin_client()
    uid = next(x["id"] for x in adm.get("/api/admin/users").get_json()["users"] if x["login"] == u["login"])
    assert adm.patch(f"/api/admin/users/{uid}", json={"active": False}).status_code == 200
    assert c.get("/api/me").get_json()["user"] is None                      # сессия сброшена
    assert login(client(), {"login": u["login"], "password": u["password"]}).status_code == 403

    adm.patch(f"/api/admin/users/{uid}", json={"active": True})
    new = adm.post(f"/api/admin/users/{uid}/reset").get_json()["created"][0]["password"]
    assert login(client(), {"login": u["login"], "password": u["password"]}).status_code == 401
    assert login(client(), {"login": u["login"], "password": new}).status_code == 200


def test_bulk_create():
    r = admin_client().post("/api/admin/users/bulk",
                            json={"names": ["Кузнецова Анна", "", "Смирнов Олег Игоревич"]})
    created = r.get_json()["created"]
    assert [x["login"] for x in created] == ["kuznetsova.a", "smirnov.oi"]
    assert all(len(x["password"]) == 10 for x in created)


def test_admin_cannot_lock_themselves_out():
    adm = admin_client()
    me = next(x for x in adm.get("/api/admin/users").get_json()["users"] if x["login"] == "admin")
    assert adm.patch(f"/api/admin/users/{me['id']}", json={"active": False}).status_code == 400
    assert adm.patch(f"/api/admin/users/{me['id']}", json={"role": "user"}).status_code == 400
    assert adm.delete(f"/api/admin/users/{me['id']}").status_code == 400


def test_cross_site_post_rejected():
    r = client().post("/api/login", json=ADMIN, headers={"Origin": "https://evil.example"})
    assert r.status_code == 403


def test_brute_force_limited():
    c = client()
    try:
        for _ in range(10):
            login(c, {"login": "admin", "password": "wrong"})
        assert login(c, ADMIN).status_code == 429
    finally:
        server.auth._FAILS.clear()   # не мешать другим тестам


def _boot(html):
    return json.loads(re.search(r"window.__BOOT__=(.*?)</script>", html).group(1))


def test_boot_contains_user():
    if not os.path.isdir(server.DIST_DIR):
        return
    boot = _boot(admin_client().get("/vkr").data.decode())
    assert boot["config"]["user"]["login"] == "admin" and boot["config"]["autofix_enabled"] is True
    assert _boot(client().get("/vkr").data.decode())["config"]["user"] is None


def test_database_url_normalized_for_psycopg(monkeypatch):
    import auth
    for raw in ("postgres://u:p@host/db", "postgresql://u:p@host/db"):
        monkeypatch.setenv("DATABASE_URL", raw)
        assert auth._db_url(".") == "postgresql+psycopg://u:p@host/db"


def test_migrate_users_between_databases(tmp_path):
    from sqlalchemy import create_engine, insert, select
    from auth import users, metadata
    from scripts.migrate_users import migrate
    from datetime import datetime, timezone
    src = "sqlite:///" + str(tmp_path / "old.db").replace("\\", "/")
    dst = "sqlite:///" + str(tmp_path / "new.db").replace("\\", "/")
    now = datetime.now(timezone.utc)
    eng = create_engine(src)
    metadata.create_all(eng)
    with eng.begin() as c:
        for login, role in (("admin", "admin"), ("ivanov.ii", "user")):
            c.execute(insert(users).values(login=login, name=login, password_hash="h-" + login, role=role,
                                           active=True, must_change_password=False, session_version=3,
                                           created_at=now))
    new = create_engine(dst)
    metadata.create_all(new)
    with new.begin() as c:   # админ, созданный из ADMIN_LOGIN на новом хостинге
        c.execute(insert(users).values(login="admin", name="Администратор", password_hash="other", role="admin",
                                       active=True, must_change_password=False, session_version=1, created_at=now))
    assert migrate(src, dst, log=lambda *_: None) == (1, 1)
    assert migrate(src, dst, log=lambda *_: None) == (0, 2)          # повторный запуск без дублей
    with new.connect() as c:
        rows = {r["login"]: r for r in c.execute(select(users)).mappings()}
    assert set(rows) == {"admin", "ivanov.ii"}
    assert rows["admin"]["password_hash"] == "h-admin"                # пароль из старой базы
    assert rows["ivanov.ii"]["session_version"] == 3


# ── обычная регистрация ──

def register(c, email, password="secret-pass-1", ip="10.0.0.1", **extra):
    extra.setdefault("consent", True)
    return c.post("/api/register", json={"email": email, "password": password, **extra},
                  environ_base={"REMOTE_ADDR": ip})


def test_registered_user_pays_until_admin_grants_free_access():
    c = client()
    r = register(c, "Student@Mail.ru", name="Студент")
    assert r.status_code == 201
    body = r.get_json()
    assert body["user"]["login"] == "student@mail.ru" and body["user"]["free_autofix"] is False
    assert body["autofix_enabled"] is False
    r = fix_request(c)
    assert r.status_code == 402 and r.get_json()["code"] == "payment_required"

    admin = admin_client()
    row = next(u for u in admin.get("/api/admin/users").get_json()["users"] if u["login"] == "student@mail.ru")
    assert row["registered"] is True and row["free_autofix"] is False
    assert admin.patch(f"/api/admin/users/{row['id']}", json={"free_autofix": True}).status_code == 200
    assert c.get("/api/me").get_json()["autofix_enabled"] is True     # без повторного входа
    assert fix_request(c).status_code == 200

    admin.patch(f"/api/admin/users/{row['id']}", json={"free_autofix": False})
    assert fix_request(c).status_code == 402

    # вход по email и паролю после выхода
    c2 = client()
    assert login(c2, {"login": "student@mail.ru", "password": "secret-pass-1"}).status_code == 200


def test_register_validation():
    c = client()
    assert register(c, "not-an-email").status_code == 400
    assert register(c, "short@mail.ru", password="123").status_code == 400
    r = register(c, "noconsent@mail.ru", consent=False, ip="10.0.0.9")
    assert r.status_code == 400 and "согласие" in r.get_json()["error"]
    assert register(c, "twice@mail.ru", ip="10.0.0.2").status_code == 201
    r = register(client(), "TWICE@mail.ru", ip="10.0.0.2")
    assert r.status_code == 409


def test_regular_user_cannot_grant_free_access_to_self():
    c = client()
    register(c, "sneaky@mail.ru", ip="10.0.0.3")
    me = c.get("/api/me").get_json()["user"]
    assert c.patch(f"/api/admin/users/{me['id']}", json={"free_autofix": True}).status_code == 403


def test_admin_issued_accounts_get_free_access():
    creds = create_user("Сидоров Пётр")
    c = client()
    login(c, {"login": creds["login"], "password": creds["password"]})
    assert c.get("/api/me").get_json()["user"]["free_autofix"] is True


def test_registration_rate_limited_per_ip():
    codes = [register(client(), f"bot{i}@mail.ru", ip="10.9.9.9").status_code for i in range(6)]
    assert codes[:5] == [201] * 5 and codes[5] == 429


def test_old_database_gets_new_columns(tmp_path, monkeypatch):
    """База, созданная до регистрации: колонки добавляются, выданные учётки сохраняют бесплатный доступ."""
    import auth
    from sqlalchemy import create_engine, text
    eng = create_engine("sqlite:///" + str(tmp_path / "old.db").replace("\\", "/"))
    with eng.begin() as c:
        c.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, login VARCHAR(64) NOT NULL UNIQUE, "
                       "name VARCHAR(200) NOT NULL, password_hash VARCHAR(256) NOT NULL, role VARCHAR(16) NOT NULL, "
                       "active BOOLEAN NOT NULL, must_change_password BOOLEAN NOT NULL, "
                       "session_version INTEGER NOT NULL, created_at DATETIME NOT NULL, last_login_at DATETIME)"))
        c.execute(text("INSERT INTO users (login, name, password_hash, role, active, must_change_password, "
                       "session_version, created_at) VALUES ('teacher', 'T', 'h', 'user', 1, 0, 1, '2026-01-01')"))
    monkeypatch.setattr(auth, "engine", eng)
    auth._add_missing_columns()
    auth._add_missing_columns()   # повторный запуск ничего не ломает
    with eng.connect() as c:
        row = c.execute(text("SELECT free_autofix, registered FROM users")).first()
    assert bool(row[0]) is True and bool(row[1]) is False

    from scripts.migrate_users import migrate
    dst = "sqlite:///" + str(tmp_path / "new.db").replace("\\", "/")
    with eng.begin() as c:
        c.execute(text("ALTER TABLE users DROP COLUMN free_autofix"))
        c.execute(text("ALTER TABLE users DROP COLUMN registered"))
    migrate("sqlite:///" + str(tmp_path / "old.db").replace("\\", "/"), dst, log=lambda *_: None)
    with create_engine(dst).connect() as c:
        assert bool(c.execute(text("SELECT free_autofix FROM users WHERE login='teacher'")).scalar()) is True
