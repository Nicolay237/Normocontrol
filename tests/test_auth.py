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
