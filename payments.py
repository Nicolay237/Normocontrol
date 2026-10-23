# -*- coding: utf-8 -*-
"""
Оплата через ЮKassa (самозанятый): разовое автоисправление и подписка.

  YOOKASSA_SHOP_ID     номер магазина (shopId) из кабинета ЮKassa
  YOOKASSA_SECRET_KEY  секретный ключ: «Интеграция → Ключи API» (test_… — тестовый магазин)

Как идёт оплата:
  1. /api/orders создаёт заказ и платёж в ЮKassa, покупатель уходит на её страницу оплаты;
  2. после оплаты ЮKassa возвращает его на /pay/<номер заказа>, страница спрашивает статус;
  3. статус сайт всегда узнаёт у самой ЮKassa (GET /v3/payments/{id}) — и по возврату
     покупателя, и по уведомлению (вебхуку); телу уведомления не доверяем, его может прислать кто угодно;
  4. оплаченный заказ «выполняется» ровно один раз: +1 исправление или +30 дней подписки.

Чеки самозанятого формируются в «Мой налог» — список оплат для этого есть в /admin.
"""

import os
import ssl
import json
import uuid
import base64
import logging
import urllib.error
import urllib.request

log = logging.getLogger("normocontrol.payments")
API = "https://api.yookassa.ru/v3"


class PaymentError(Exception):
    pass


def _creds():
    return os.environ.get("YOOKASSA_SHOP_ID", "").strip(), os.environ.get("YOOKASSA_SECRET_KEY", "").strip()


def enabled():
    shop, key = _creds()
    return bool(shop and key)


def test_mode():
    return _creds()[1].startswith("test_")


def _ssl_context():
    """Сертификаты из certifi: не зависим от того, обновлено ли хранилище сертификатов системы."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def _request(method, path, body=None, idempotence_key=None):
    """Запрос к API ЮKassa. Ошибку сети или ответ с ошибкой превращает в PaymentError."""
    shop, key = _creds()
    headers = {
        "Authorization": "Basic " + base64.b64encode(f"{shop}:{key}".encode()).decode(),
        "Content-Type": "application/json",
    }
    if idempotence_key:
        headers["Idempotence-Key"] = idempotence_key
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20, context=_ssl_context()) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:500]
        log.error("ЮKassa %s %s → %s: %s", method, path, e.code, detail)
        raise PaymentError(f"ЮKassa ответила ошибкой {e.code}") from e
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        log.error("ЮKassa %s %s: %s", method, path, e)
        raise PaymentError("ЮKassa недоступна") from e


def create_payment(order_id, amount_rub, description, return_url):
    """Платёж с подтверждением через страницу ЮKassa. Возвращает (id платежа, ссылка на оплату)."""
    payment = _request("POST", "/payments", {
        "amount": {"value": f"{amount_rub:.2f}", "currency": "RUB"},
        "capture": True,
        "confirmation": {"type": "redirect", "return_url": return_url},
        "description": description[:128],
        "metadata": {"order_id": order_id},
    }, idempotence_key=order_id)
    url = (payment.get("confirmation") or {}).get("confirmation_url")
    if not payment.get("id") or not url:
        raise PaymentError("ЮKassa не вернула ссылку на оплату")
    return payment["id"], url


def get_payment(payment_id):
    return _request("GET", f"/payments/{payment_id}")


def new_order_id():
    return uuid.uuid4().hex
