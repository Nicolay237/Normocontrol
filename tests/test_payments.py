# -*- coding: utf-8 -*-
"""Оплата через ЮKassa: API ЮKassa подменён, проверяется вся цепочка заказ → оплата → начисление."""

import uuid

import pytest

import payments

from test_auth import admin_client, client, fix_request, register


class FakeYooKassa:
    """Минимальная ЮKassa в памяти: создаёт платежи и отдаёт их статус."""

    def __init__(self):
        self.payments = {}

    def __call__(self, method, path, body=None, idempotence_key=None):
        if method == "POST" and path == "/payments":
            pid = f"pay-{uuid.uuid4().hex[:12]}"   # у настоящей ЮKassa номера платежей не повторяются
            self.payments[pid] = {"id": pid, "status": "pending", "paid": False, "amount": body["amount"],
                                  "metadata": body["metadata"],
                                  "confirmation": {"confirmation_url": f"https://yoomoney.test/{pid}"}}
            return self.payments[pid]
        pid = path.rsplit("/", 1)[-1]
        if pid not in self.payments:
            raise payments.PaymentError("ЮKassa ответила ошибкой 404")
        return self.payments[pid]

    def pay(self, pid, status="succeeded"):
        self.payments[pid].update(status=status, paid=status == "succeeded")


@pytest.fixture
def kassa(monkeypatch):
    monkeypatch.setenv("YOOKASSA_SHOP_ID", "1504467")
    monkeypatch.setenv("YOOKASSA_SECRET_KEY", "test_secret")
    fake = FakeYooKassa()
    monkeypatch.setattr(payments, "_request", fake)
    return fake


def buyer(ip):
    c = client()
    register(c, f"buyer{ip.replace('.', '')}@mail.ru", ip=ip)
    return c


def order(c, kind="autofix", **extra):
    return c.post("/api/orders", json={"kind": kind, **extra})


def test_orders_need_payments_and_login(monkeypatch):
    monkeypatch.delenv("YOOKASSA_SHOP_ID", raising=False)
    assert order(buyer("10.5.0.1")).get_json()["code"] == "payments_disabled"
    assert client().get("/api/config").get_json()["payments_enabled"] is False


def test_single_autofix_purchase(kassa):
    c = buyer("10.5.0.2")
    assert fix_request(c).get_json()["code"] == "payment_required"
    assert order(client()).status_code == 401                            # без входа — нельзя
    assert order(c, kind="cake").status_code == 400

    r = order(c, upload_id="abc", profile="vkr", file_name="Работа.docx")
    assert r.status_code == 201
    body = r.get_json()
    pid = next(p for p, v in kassa.payments.items() if v["metadata"]["order_id"] == body["order_id"])
    assert body["confirmation_url"] == f"https://yoomoney.test/{pid}"
    assert kassa.payments[pid]["amount"] == {"value": "99.00", "currency": "RUB"}

    # пока не оплачено — ничего не начислено
    st = c.get(f"/api/orders/{body['order_id']}").get_json()
    assert st["order"]["status"] == "pending" and st["user"]["autofix_credits"] == 0
    assert st["order"]["upload_id"] == "abc" and st["order"]["profile"] == "vkr"

    kassa.pay(pid)
    st = c.get(f"/api/orders/{body['order_id']}").get_json()
    assert st["order"]["status"] == "succeeded" and st["user"]["autofix_credits"] == 1 and st["autofix_enabled"]
    # повторный запрос статуса и уведомление не начисляют второй раз
    c.get(f"/api/orders/{body['order_id']}")
    client().post("/api/payments/webhook", json={"event": "payment.succeeded", "object": {"id": pid}})
    assert c.get("/api/me").get_json()["user"]["autofix_credits"] == 1

    # исправление списывает оплаченное
    r = fix_request(c)
    assert r.status_code == 200 and r.get_json()["autofix_credits"] == 0
    assert fix_request(c).get_json()["code"] == "payment_required"


def test_subscription_purchase_via_webhook(kassa):
    c = buyer("10.5.0.3")
    oid = order(c, kind="subscription").get_json()["order_id"]
    pid = next(p for p, v in kassa.payments.items() if v["metadata"]["order_id"] == oid)
    assert kassa.payments[pid]["amount"]["value"] == "299.00"
    kassa.pay(pid)
    # покупатель закрыл вкладку — заказ выполняет уведомление ЮKassa
    assert client().post("/api/payments/webhook", json={"event": "payment.succeeded",
                                                        "object": {"id": pid}}).status_code == 200
    me = c.get("/api/me").get_json()
    assert me["user"]["subscription"]["active"] and me["autofix_enabled"]


def test_fake_webhook_changes_nothing(kassa):
    c = buyer("10.5.0.4")
    oid = order(c).get_json()["order_id"]
    pid = next(p for p, v in kassa.payments.items() if v["metadata"]["order_id"] == oid)
    # злоумышленник присылает «оплачено» — но ЮKassa говорит, что платёж не оплачен
    r = client().post("/api/payments/webhook", json={"event": "payment.succeeded",
                                                     "object": {"id": pid, "status": "succeeded", "paid": True}})
    assert r.status_code == 200
    assert c.get("/api/me").get_json()["user"]["autofix_credits"] == 0
    # неизвестный платёж — просто 200
    assert client().post("/api/payments/webhook", json={"object": {"id": "nope"}}).status_code == 200


def test_canceled_payment(kassa):
    c = buyer("10.5.0.5")
    oid = order(c).get_json()["order_id"]
    pid = next(p for p, v in kassa.payments.items() if v["metadata"]["order_id"] == oid)
    kassa.pay(pid, status="canceled")
    st = c.get(f"/api/orders/{oid}").get_json()
    assert st["order"]["status"] == "canceled" and st["user"]["autofix_credits"] == 0


def test_order_is_private(kassa):
    oid = order(buyer("10.5.0.6")).get_json()["order_id"]
    assert buyer("10.5.0.7").get(f"/api/orders/{oid}").status_code == 404
    assert admin_client().get(f"/api/orders/{oid}").status_code == 200


def test_admin_sees_paid_orders_for_receipts(kassa):
    c = buyer("10.5.0.8")
    oid = order(c).get_json()["order_id"]
    pid = next(p for p, v in kassa.payments.items() if v["metadata"]["order_id"] == oid)
    kassa.pay(pid)
    c.get(f"/api/orders/{oid}")
    admin = admin_client()
    rows = admin.get("/api/admin/orders").get_json()["orders"]
    row = next(r for r in rows if r["id"] == oid)
    assert row["amount"] == 99 and row["receipt_issued"] is False and row["login"].startswith("buyer")
    assert admin.patch(f"/api/admin/orders/{oid}", json={"receipt_issued": True}).status_code == 200
    assert next(r for r in admin.get("/api/admin/orders").get_json()["orders"] if r["id"] == oid)["receipt_issued"]
    assert c.get("/api/admin/orders").status_code == 403


def test_receipt_link_is_emailed_and_shown_to_buyer(kassa, monkeypatch):
    import mailer
    for k, v in (("SMTP_HOST", "smtp.test"), ("SMTP_USER", "noreply@normocontrol.site"), ("SMTP_PASSWORD", "x")):
        monkeypatch.setenv(k, v)
    sent = []
    monkeypatch.setattr(mailer, "send", lambda to, subject, text: sent.append((to, subject, text)))

    c = buyer("10.5.0.9")
    # регистрация при включённой почте требует код — подтвердим его
    import re as _re
    code = _re.search(r"\b(\d{6})\b", sent[-1][2]).group(1)
    c.post("/api/email/verify", json={"code": code})
    oid = order(c).get_json()["order_id"]
    pid = next(p for p, v in kassa.payments.items() if v["metadata"]["order_id"] == oid)
    kassa.pay(pid)
    c.get(f"/api/orders/{oid}")
    assert c.get("/api/account/orders").get_json()["orders"][0]["receipt_url"] is None

    admin = admin_client()
    r = admin.patch(f"/api/admin/orders/{oid}", json={"receipt_url": "https://evil.example/receipt"})
    assert r.status_code == 400
    link = "https://lknpd.nalog.ru/api/v1/receipt/123456789012/200abc/print"
    r = admin.patch(f"/api/admin/orders/{oid}", json={"receipt_url": link})
    assert r.status_code == 200 and r.get_json()["mail_sent"] is True
    to, subject, text = sent[-1]
    assert to == "buyer10509@mail.ru" and "Чек" in subject and link in text and "99 ₽" in text

    row = next(o for o in admin.get("/api/admin/orders").get_json()["orders"] if o["id"] == oid)
    assert row["receipt_issued"] is True and row["receipt_url"] == link
    mine = c.get("/api/account/orders").get_json()["orders"]
    assert mine[0]["receipt_url"] == link and mine[0]["amount"] == 99
    # чужие оплаты в кабинете не видны
    assert buyer("10.5.0.10").get("/api/account/orders").get_json()["orders"] == []
