# -*- coding: utf-8 -*-
"""Оферта, политика ПД, согласие, правила возврата, контакты: реквизиты из окружения, страницы сайта."""

import app as server
import legal

PAGES = ("/offer", "/refund", "/privacy", "/consent", "/contacts")


def client():
    return server.app.test_client()


def test_placeholders_until_requisites_set(monkeypatch):
    for k in ("LEGAL_NAME", "LEGAL_INN", "CONTACT_EMAIL", "CONTACT_PHONE"):
        monkeypatch.delenv(k, raising=False)
    assert legal.missing() == ["ФИО исполнителя", "ИНН", "email для обращений"]
    html = client().get("/contacts").data.decode()
    assert "[укажите ФИО: LEGAL_NAME]" in html


def test_documents_use_requisites_and_prices(monkeypatch):
    monkeypatch.setenv("LEGAL_NAME", "Петров Пётр Петрович")
    monkeypatch.setenv("LEGAL_INN", "123456789012")
    monkeypatch.setenv("CONTACT_EMAIL", "help@example.ru")
    assert legal.missing() == []
    c = client()
    for path in PAGES:
        r = c.get(path)
        html = r.data.decode()
        assert r.status_code == 200 and "<h1>" in html and "[укажите" not in html, path
    offer = c.get("/api/legal/offer").get_json()
    text = str(offer)
    assert "Петров Пётр Петрович" in text and "123456789012" in text
    assert "299 ₽" in text and "30 автоисправлений" in text and "99 ₽" in text
    # ссылки между документами работают в пререндере
    assert '<a href="/refund">' in c.get("/offer").data.decode()
    assert c.get("/api/legal/unknown").status_code == 404


def test_refund_example_matches_prices():
    text = str(legal.refund())
    assert "к возврату 101 ₽" in text   # 299 − 2 × 99


def test_legal_pages_not_in_sitemap_but_linked():
    sm = client().get("/sitemap.xml").data.decode()
    assert "/offer" not in sm
    assert "/contacts" not in client().get("/robots.txt").data.decode()   # не закрыты от поиска
