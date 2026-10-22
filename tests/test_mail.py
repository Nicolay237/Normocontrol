# -*- coding: utf-8 -*-
"""Подтверждение почты кодом из письма и сброс пароля (отправка писем подменена)."""

import re

import pytest

import mailer

from test_auth import admin_client, client, fix_request, login, register


@pytest.fixture
def outbox(monkeypatch):
    for k, v in (("SMTP_HOST", "smtp.test"), ("SMTP_USER", "noreply@normocontrol.site"), ("SMTP_PASSWORD", "x")):
        monkeypatch.setenv(k, v)
    sent = []
    monkeypatch.setattr(mailer, "send", lambda to, subject, text: sent.append((to, subject, text)))
    return sent


def code_from(letter):
    return re.search(r"\b(\d{6})\b", letter[2]).group(1)


def test_without_smtp_registration_needs_no_confirmation():
    c = client()
    r = register(c, "nomail@mail.ru", ip="10.3.0.1").get_json()
    assert r["user"]["email_verified"] is True and r["mail_sent"] is None


def test_registration_requires_code(outbox):
    c = client()
    r = register(c, "verify@mail.ru", ip="10.3.0.2").get_json()
    assert r["user"]["email_verified"] is False and r["mail_sent"] is True
    assert outbox[-1][0] == "verify@mail.ru" and "Код подтверждения" in outbox[-1][1]

    # пока почта не подтверждена — автоисправление недоступно даже с подпиской
    uid = r["user"]["id"]
    admin_client().patch(f"/api/admin/users/{uid}", json={"subscription_days": 30})
    assert fix_request(c).get_json()["code"] == "email_unverified"

    good = code_from(outbox[-1])
    bad = "000000" if good != "000000" else "111111"
    r = c.post("/api/email/verify", json={"code": bad})
    assert r.status_code == 400
    r = c.post("/api/email/verify", json={"code": good}).get_json()
    assert r["user"]["email_verified"] is True and r["autofix_enabled"] is True


def test_code_burns_after_five_wrong_attempts(outbox):
    c = client()
    register(c, "brute@mail.ru", ip="10.3.0.3")
    good = code_from(outbox[-1])
    bad = "000000" if good != "000000" else "111111"
    for _ in range(5):
        c.post("/api/email/verify", json={"code": bad})
    r = c.post("/api/email/verify", json={"code": good})
    assert r.status_code == 400 and r.get_json()["code"] == "code_expired"
    # новый код по кнопке «Отправить ещё раз»
    assert c.post("/api/email/resend", json={}).status_code == 200
    assert c.post("/api/email/verify", json={"code": code_from(outbox[-1])}).status_code == 200


def test_mail_failure_does_not_break_registration(monkeypatch, outbox):
    def boom(*a):
        raise OSError("smtp down")
    monkeypatch.setattr(mailer, "send", boom)
    r = register(client(), "down@mail.ru", ip="10.3.0.4")
    assert r.status_code == 201 and r.get_json()["mail_sent"] is False


def test_password_reset(outbox):
    register(client(), "forgot@mail.ru", password="old-password-1", ip="10.3.0.5")
    other = client()
    login(other, {"login": "forgot@mail.ru", "password": "old-password-1"})

    c = client()
    assert c.post("/api/password/forgot", json={"email": "forgot@mail.ru"}).status_code == 200
    assert "Сброс пароля" in outbox[-1][1]
    # неизвестный адрес — тот же ответ и никакого письма
    n = len(outbox)
    assert c.post("/api/password/forgot", json={"email": "nobody@mail.ru"}).status_code == 200
    assert len(outbox) == n

    code = code_from(outbox[n - 1])
    r = c.post("/api/password/reset", json={"email": "forgot@mail.ru", "code": code, "password": "short"})
    assert r.status_code == 400
    r = c.post("/api/password/reset", json={"email": "forgot@mail.ru", "code": code, "password": "new-password-1"})
    assert r.status_code == 200 and r.get_json()["user"]["email_verified"] is True
    assert c.get("/api/me").get_json()["user"]["login"] == "forgot@mail.ru"   # сразу вошёл
    assert other.get("/api/me").get_json()["user"] is None                    # другие устройства вышли
    assert login(client(), {"login": "forgot@mail.ru", "password": "new-password-1"}).status_code == 200
    # код одноразовый
    r = c.post("/api/password/reset", json={"email": "forgot@mail.ru", "code": code, "password": "another-pass-1"})
    assert r.status_code == 400


def test_forgot_without_smtp_explains():
    r = client().post("/api/password/forgot", json={"email": "a@mail.ru"})
    assert r.status_code == 503


def test_letter_text():
    subject, text = mailer.code_letter("verify", "123456", "https://normocontrol.site")
    assert "123456" in subject and "123456" in text and "30 минут" in text
