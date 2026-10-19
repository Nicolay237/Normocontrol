# -*- coding: utf-8 -*-
"""API: проверка → исправление по upload_id без повторной загрузки, согласованность счётчиков."""

import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import app as server  # noqa: E402
import make_docs as md  # noqa: E402
from docx.shared import Cm  # noqa: E402


def docx_bytes(doc):
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def broken():
    doc = md.good_document()
    doc.sections[0].left_margin = Cm(2)
    doc.styles["Normal"].paragraph_format.line_spacing = 1.0
    return doc


def post(client, url, **fields):
    return client.post(url, data=fields, content_type="multipart/form-data")


def logged_in_client():
    """Клиент, вошедший как пользователь университета."""
    c = server.app.test_client()
    assert c.post("/api/login", json={"login": "admin", "password": "admin-pass-123"}).status_code == 200
    return c


def test_check_then_fix_by_upload_id():
    c = logged_in_client()
    data = docx_bytes(broken())
    r = post(c, "/api/check", profile="vkr", file=(io.BytesIO(data), "работа.docx"))
    rep = r.get_json()
    assert r.status_code == 200 and rep["total"] > 0 and rep["upload_id"]

    r = post(c, "/api/fix", profile="vkr", upload_id=rep["upload_id"])   # файл не отправляем
    fix = r.get_json()
    assert r.status_code == 200
    # «до» совпадает с тем, что пользователь видел в отчёте, и счётчики сходятся
    assert fix["issues_before"] == rep["total"]
    assert fix["total_fixed"] == sum(c["fixed"] for c in fix["categories"])
    assert fix["total_fixed"] - fix["total_new"] == fix["issues_before"] - fix["issues_after"]
    assert fix["file"] == "работа.docx"

    r = c.get("/api/fixed/" + fix["download_id"])
    assert r.status_code == 200 and r.data[:2] == b"PK"
    assert "attachment" in r.headers["Content-Disposition"]


def test_fix_with_unknown_upload_id_asks_for_file():
    c = logged_in_client()
    r = post(c, "/api/fix", profile="vkr", upload_id="0" * 32)
    assert r.status_code == 410 and r.get_json()["code"] == "upload_expired"


def test_fix_fallback_with_file():
    c = logged_in_client()
    r = post(c, "/api/fix", profile="vkr", file=(io.BytesIO(docx_bytes(broken())), "w.docx"))
    assert r.status_code == 200 and r.get_json()["total_fixed"] > 0


def test_pdf_has_no_upload_id():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from make_pdfs import make_pdf
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        p = os.path.join(tmp, "w.pdf")
        make_pdf(p)
        c = server.app.test_client()
        r = post(c, "/api/check", profile="vkr", file=(open(p, "rb"), "w.pdf"))
        assert r.status_code == 200 and r.get_json()["upload_id"] is None


def test_store_path_traversal_rejected():
    assert server.store.get("../app.py", "upload") is None
    assert server.store.get("", "upload") is None


def test_check_reports_fixable_estimate_and_price():
    c = server.app.test_client()
    rep = post(c, "/api/check", profile="vkr", file=(io.BytesIO(docx_bytes(broken())), "w.docx")).get_json()
    assert 0 < rep["fixable"] <= rep["total"]
    cfg = c.get("/api/config").get_json()
    assert cfg["autofix_price"] > 0 and cfg["payments_enabled"] is False
