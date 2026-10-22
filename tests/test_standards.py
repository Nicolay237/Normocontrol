# -*- coding: utf-8 -*-
"""Раздел «Выбор ГОСТов» и подписка на автоисправление."""

import io

import pytest
from docx.shared import Cm

import auth
import make_docs as md
from checker import run_normocontrol
from checker.bibliography import check_entry
from checker.standards import build_profile, fixable, normalize

from test_auth import admin_client, client, register


def check(doc, tmp_path, stds):
    path = tmp_path / "w.docx"
    doc.save(path)
    return run_normocontrol(str(path), "custom", standards=stds)


def cats(report):
    return {i.category for i in report.issues}


# ── набор стандартов ──

def test_exclusive_standards_cannot_be_combined():
    with pytest.raises(ValueError, match="взаимоисключающие"):
        normalize(["gost-7.32", "gost-7.0.11"])
    with pytest.raises(ValueError, match="взаимоисключающие"):
        normalize(["gost-7.0.100", "gost-7.1"])
    with pytest.raises(ValueError, match="хотя бы один"):
        normalize([])
    with pytest.raises(ValueError, match="Неизвестный"):
        normalize(["gost-9999"])
    # порядок и повторы не важны — один и тот же набор
    assert normalize(["gost-7.0.5", "gost-7.32", "gost-7.32"]) == ("gost-7.32", "gost-7.0.5")


def test_profiles_follow_standards():
    p = build_profile(["gost-7.0.11"])
    assert p["margins_cm"]["left"] == (2.5, 2.5) and p["page_number_pos"] == "top"
    assert p["heading_align"] == "center" and p["bib_standard"] is None and not p["citations"]
    p = build_profile(["gost-2.105", "gost-7.1"])
    assert "Arial" in p["font_names"] and not p["check_margins"] and p["bib_standard"] == "7.1"
    assert fixable(("gost-7.32", "gost-7.0.100", "gost-7.0.5")) and not fixable(("gost-2.105",))


def test_good_document_passes_gost_7_32(tmp_path):
    assert check(md.good_document(), tmp_path, ("gost-7.32", "gost-7.0.100", "gost-7.0.5")).issues == []


def test_dissertation_rules(tmp_path):
    report = check(md.good_document(), tmp_path, ("gost-7.0.11",))
    msgs = "\n".join(i.message for i in report.issues)
    assert "левое поле 3 см, ожидается 2,5 см" in msgs
    assert "середине верхнего поля" in msgs                 # номер страницы внизу, а нужен вверху
    assert "заголовок располагается посередине" in msgs
    assert "п. 6." not in msgs and "7.32" not in msgs        # ссылки на пункты ГОСТ 7.32 убраны


def test_eskd_allows_arial_and_any_margins(tmp_path):
    doc = md.new_document(left=2.0, right=1.0, body_font="Arial", align=0, indent=1.5)
    md.structural(doc, "ВВЕДЕНИЕ", page_break=False)
    md.body(doc)
    report = check(doc, tmp_path, ("gost-2.105",))
    assert not cats(report) & {"Поля страницы", "Шрифт", "Выравнивание", "Красная строка"}
    report = check(doc, tmp_path, ("gost-7.32",))
    assert {"Поля страницы", "Шрифт", "Выравнивание", "Красная строка"} <= cats(report)


def test_only_bibliography(tmp_path):
    doc = md.good_document()
    doc.sections[0].left_margin = Cm(1)                     # оформление сломано, но его не проверяем
    md.body(doc, "2. Петров П. П. Анализ. – М. : Наука, 2019. – 100 с.")
    report = check(doc, tmp_path, ("gost-7.0.100",))
    assert cats(report) == {"Список источников"}


def test_old_bibliography_standard_allows_old_forms():
    entry = "Иванов, И. И. Базы данных [Электронный ресурс] / И. И. Иванов. – М. : Наука, 2010. – 200 с."
    assert any("Электронный ресурс" in m for m in check_entry(entry, "7.0.100"))
    assert any("место издания пишется полностью" in m for m in check_entry(entry, "7.0.100"))
    assert check_entry(entry, "7.1") == []
    web = "Сайт ГИБДД. – Режим доступа: http://gibdd.ru"
    assert not any("URL" in m for m in check_entry(web, "7.1"))
    assert any("URL" in m for m in check_entry(web, "7.0.100"))


# ── API ──

def upload(doc, **fields):
    buf = io.BytesIO()
    doc.save(buf)
    return {"file": (io.BytesIO(buf.getvalue()), "w.docx"), **fields}


def test_api_standards_and_custom_check():
    c = client()
    catalog = c.get("/api/standards").get_json()
    assert {g["key"] for g in catalog["groups"]} == {"layout", "bibliography", "citations"}
    assert catalog["default"] == ["gost-7.32", "gost-7.0.100", "gost-7.0.5"]

    r = c.post("/api/check", data=upload(md.good_document(), profile="custom", standards="gost-7.32,gost-2.105"),
               content_type="multipart/form-data")
    assert r.status_code == 400 and "взаимоисключающие" in r.get_json()["error"]

    r = c.post("/api/check", data=upload(md.good_document(), profile="custom", standards="gost-7.0.11"),
               content_type="multipart/form-data").get_json()
    assert r["standards"] == ["gost-7.0.11"] and r["autofix_supported"] is False and r["fixable"] == 0
    assert r["profile"]["key"] == "custom"

    admin = admin_client()
    r = admin.post("/api/fix", data=upload(md.good_document(), profile="custom", standards="gost-7.0.11"),
                   content_type="multipart/form-data")
    assert r.status_code == 400 and r.get_json()["code"] == "fix_unsupported"
    r = admin.post("/api/fix", data=upload(md.good_document(), profile="custom", standards="gost-7.32,gost-7.0.100"),
                   content_type="multipart/form-data")
    assert r.status_code == 200


# ── подписка ──

def broken_doc():
    doc = md.good_document()
    doc.styles["Normal"].paragraph_format.line_spacing = 1.0
    return doc


def fix(c):
    return c.post("/api/fix", data=upload(broken_doc(), profile="vkr"), content_type="multipart/form-data")


def test_subscription_limits_autofix(monkeypatch):
    c = client()
    register(c, "subscriber@mail.ru", ip="10.2.2.2")
    assert fix(c).get_json()["code"] == "payment_required"

    admin = admin_client()
    uid = c.get("/api/me").get_json()["user"]["id"]
    assert admin.patch(f"/api/admin/users/{uid}", json={"subscription_days": 0}).status_code == 400
    assert admin.patch(f"/api/admin/users/{uid}", json={"subscription_days": 30}).status_code == 200
    me = c.get("/api/me").get_json()
    assert me["autofix_enabled"] is True
    assert me["user"]["subscription"]["active"] and me["user"]["subscription"]["used"] == 0

    monkeypatch.setattr(auth, "SUBSCRIPTION_LIMIT", 2)
    r = fix(c)
    assert r.status_code == 200 and r.get_json()["subscription"]["left"] == 1
    assert fix(c).status_code == 200
    r = fix(c)
    assert r.status_code == 402 and r.get_json()["code"] == "limit_reached"
    assert c.get("/api/me").get_json()["autofix_enabled"] is False

    # продление прибавляет срок к текущей подписке
    until = c.get("/api/me").get_json()["user"]["subscription"]["until"]
    admin.patch(f"/api/admin/users/{uid}", json={"subscription_days": 30})
    assert c.get("/api/me").get_json()["user"]["subscription"]["until"] > until

    admin.patch(f"/api/admin/users/{uid}", json={"subscription_cancel": True})
    assert fix(c).get_json()["code"] == "payment_required"


def test_free_access_does_not_spend_subscription(monkeypatch):
    admin = admin_client()
    monkeypatch.setattr(auth, "SUBSCRIPTION_LIMIT", 1)
    for _ in range(3):
        assert fix(admin).status_code == 200


def test_config_has_subscription_price():
    cfg = client().get("/api/config").get_json()
    assert cfg["subscription_price"] == 299 and cfg["subscription_limit"] == 30
