# -*- coding: utf-8 -*-
"""
Отзывы о сервисе: оставить может любой посетитель (вход не нужен), на странице /reviews они
появляются после одобрения администратором в /admin. О новом отзыве администратору приходит письмо.

Таблица живёт в общей metadata из auth.py — модуль нужно импортировать до auth.init_app,
тогда create_all создаст её вместе с остальными.
"""

import os
import re
import logging
import threading

from flask import Blueprint, jsonify, request
from sqlalchemy import Table, Column, Integer, String, Text, DateTime, select, insert, update, delete, func

import auth
import mailer
from auth import metadata, current_user, admin_required, client_ip, _too_many, _fail, _now, _aware

log = logging.getLogger("normocontrol.reviews")
bp = Blueprint("reviews", __name__)

reviews = Table(
    "reviews", metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String(80), nullable=False, default=""),
    Column("rating", Integer, nullable=False),
    Column("text", Text, nullable=False),
    Column("status", String(16), nullable=False, default="pending"),   # pending | published | hidden
    Column("source", String(16), nullable=True),                       # check | fix — откуда пришли
    Column("user_id", Integer, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

TEXT_MIN, TEXT_MAX, NAME_MAX = 10, 2000, 80
REVIEW_WINDOW, REVIEW_LIMIT = 60 * 60, 3      # отзывов с одного IP в час
STATUSES = {"pending", "published", "hidden"}
SOURCES = {"check", "fix"}
_URL_RE = re.compile(r"https?://|www\.", re.I)


def _public(r):
    return {"id": r["id"], "name": r["name"] or "Аноним", "rating": r["rating"], "text": r["text"],
            "date": _aware(r["created_at"]).date().isoformat()}


def published(limit=200):
    """Одобренные отзывы, новые сверху, и сводка: {"items", "count", "average"}."""
    with auth.engine.connect() as c:
        rows = c.execute(select(reviews).where(reviews.c.status == "published")
                         .order_by(reviews.c.created_at.desc()).limit(limit)).mappings().all()
        count, avg = c.execute(select(func.count(), func.avg(reviews.c.rating))
                               .where(reviews.c.status == "published")).first()
    return {"items": [_public(r) for r in rows], "count": count or 0,
            "average": round(float(avg), 1) if avg else None}


@bp.get("/api/reviews")
def list_reviews():
    return jsonify(published())


@bp.post("/api/reviews")
def create_review():
    data = request.get_json(silent=True) or {}
    key = f"review:{client_ip()}"
    if _too_many(key, REVIEW_WINDOW, REVIEW_LIMIT):
        return jsonify(error="Слишком много отзывов подряд. Попробуйте позже."), 429
    if data.get("website"):          # скрытое поле: его заполняют только боты
        return jsonify(ok=True)
    try:
        rating = int(data.get("rating"))
    except (TypeError, ValueError):
        rating = 0
    if not 1 <= rating <= 5:
        return jsonify(error="Поставьте оценку от 1 до 5."), 400
    text = re.sub(r"[ \t]+", " ", (data.get("text") or "").strip())
    text = re.sub(r"\n{3,}", "\n\n", text)
    if len(text) < TEXT_MIN:
        return jsonify(error=f"Напишите хотя бы пару слов — не меньше {TEXT_MIN} символов."), 400
    if len(text) > TEXT_MAX:
        return jsonify(error=f"Отзыв слишком длинный: не больше {TEXT_MAX} символов."), 400
    if _URL_RE.search(text):
        return jsonify(error="Ссылки в отзывах не публикуются — уберите адрес сайта из текста."), 400
    name = re.sub(r"\s+", " ", (data.get("name") or "").strip())[:NAME_MAX]
    source = data.get("source") if data.get("source") in SOURCES else None
    u = current_user()
    _fail(key)
    with auth.engine.begin() as c:
        rid = c.execute(insert(reviews).values(
            name=name, rating=rating, text=text, status="pending", source=source,
            user_id=u["id"] if u else None, created_at=_now())).inserted_primary_key[0]
    _notify(rid, name, rating, text, source)
    return jsonify(ok=True, id=rid), 201


def _notify(rid, name, rating, text, source):
    """Письмо администратору о новом отзыве — в отдельном потоке, чтобы посетитель не ждал SMTP."""
    to = os.environ.get("ALERT_EMAIL", "").strip() or os.environ.get("CONTACT_EMAIL", "").strip()
    if not (to and mailer.enabled()):
        return
    site = (os.environ.get("SITE_URL") or request.host_url).rstrip("/")
    where = {"check": " (после проверки)", "fix": " (после исправления)"}.get(source, "")
    body = (f"Новый отзыв{where}: {'★' * rating}{'☆' * (5 - rating)}\n"
            f"Имя: {name or 'не указано'}\n\n{text}\n\n"
            f"Опубликовать или скрыть: {site}/admin#reviews\n")

    def send():
        try:
            mailer.send(to, f"Новый отзыв №{rid}: {rating} из 5", body)
        except Exception as e:
            log.warning("письмо об отзыве %s не отправлено: %s", rid, e)
    threading.Thread(target=send, daemon=True).start()


# ── администрирование ─────────────────────────────────────────────────────

@bp.get("/api/admin/reviews")
@admin_required
def admin_list():
    with auth.engine.connect() as c:
        rows = c.execute(select(reviews).order_by(reviews.c.created_at.desc()).limit(500)).mappings().all()
    return jsonify(reviews=[{**_public(r), "name": r["name"], "status": r["status"], "source": r["source"],
                             "created_at": _aware(r["created_at"]).isoformat()} for r in rows])


@bp.patch("/api/admin/reviews/<int:rid>")
@admin_required
def admin_update(rid):
    status = (request.get_json(silent=True) or {}).get("status")
    if status not in STATUSES:
        return jsonify(error="Неизвестный статус."), 400
    with auth.engine.begin() as c:
        n = c.execute(update(reviews).where(reviews.c.id == rid).values(status=status)).rowcount
    return (jsonify(ok=True), 200) if n else (jsonify(error="Отзыв не найден."), 404)


@bp.delete("/api/admin/reviews/<int:rid>")
@admin_required
def admin_delete(rid):
    with auth.engine.begin() as c:
        n = c.execute(delete(reviews).where(reviews.c.id == rid)).rowcount
    return (jsonify(ok=True), 200) if n else (jsonify(error="Отзыв не найден."), 404)
