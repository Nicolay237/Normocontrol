# -*- coding: utf-8 -*-
"""Защита перед наплывом пользователей: лимиты по IP, большие файлы, письма о сбоях."""

import io
import logging
import os
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import app as server  # noqa: E402
import mailer  # noqa: E402
from checker import pdf_checks, run_normocontrol  # noqa: E402
from make_pdfs import make_pdf  # noqa: E402
from test_api import broken, docx_bytes, post  # noqa: E402


def check(c, data, name="работа.docx", ip="10.1.1.1", headers=None):
    return c.post("/api/check", data={"profile": "vkr", "file": (io.BytesIO(data), name)},
                  content_type="multipart/form-data", environ_base={"REMOTE_ADDR": ip}, headers=headers or {})


def test_forged_forwarded_for_does_not_bypass_login_limit():
    c = server.app.test_client()
    for n in range(10):
        c.post("/api/login", json={"login": "admin", "password": "wrong"},
               headers={"X-Forwarded-For": f"203.0.113.{n}"})
    r = c.post("/api/login", json={"login": "admin", "password": "admin-pass-123"},
               headers={"X-Forwarded-For": "198.51.100.7"})
    assert r.status_code == 429


def test_check_rate_limited_per_ip(monkeypatch):
    monkeypatch.setattr(server, "CHECK_LIMIT", 3)
    c = server.app.test_client()
    data = docx_bytes(broken())
    assert [check(c, data).status_code for _ in range(3)] == [200, 200, 200]
    r = check(c, data)
    assert r.status_code == 429 and "Подождите" in r.get_json()["error"]
    assert check(c, data, headers={"X-Forwarded-For": "192.0.2.1"}).status_code == 429   # заголовок не помогает
    assert check(c, data, ip="10.2.2.2").status_code == 200                               # другой IP — свой лимит


def test_docx_zip_bomb_rejected(monkeypatch):
    monkeypatch.setattr(server, "DOCX_MAX_UNPACKED", 1024 * 1024)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("word/document.xml", "<" + " " * (5 * 1024 * 1024))
    r = check(server.app.test_client(), buf.getvalue())
    assert r.status_code == 400 and "слишком большой" in r.get_json()["error"]


def test_long_pdf_checked_up_to_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(pdf_checks, "PDF_MAX_PAGES", 3)
    p = str(tmp_path / "long.pdf")
    make_pdf(p, paragraphs=120)
    rep = run_normocontrol(p, "vkr")
    assert any("проверены первые 3" in n for n in rep.notes)


def test_alerts_throttled(monkeypatch):
    sent = []
    monkeypatch.setattr(mailer, "send", lambda to, subj, text: sent.append((to, subj)))
    monkeypatch.setattr(mailer.threading, "Thread",
                        lambda target, args, daemon: type("T", (), {"start": lambda self: target(*args)})())
    h = mailer.AlertHandler("owner@example.com")
    lg = logging.getLogger("normocontrol.test-alerts")
    lg.addHandler(h)
    try:
        lg.error("check failed")
        lg.error("check failed")          # повтор в течение получаса — без письма
        lg.error("payment failed")
        lg.warning("просто предупреждение")
    finally:
        lg.removeHandler(h)
    assert [s for _, s in sent] == ["Сбой на сайте: check failed", "Сбой на сайте: payment failed"]
    assert all(to == "owner@example.com" for to, _ in sent)


def test_alerts_off_without_mail(monkeypatch):
    monkeypatch.setenv("CONTACT_EMAIL", "owner@example.com")
    monkeypatch.delenv("SMTP_HOST", raising=False)
    assert mailer.install_alerts(logging.getLogger("x")) is None
