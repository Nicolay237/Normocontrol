# -*- coding: utf-8 -*-
"""Отзывы: оставить может любой, на странице — только одобренные администратором."""

import app as server
from test_auth import admin_client, client

GOOD = {"rating": 5, "name": "Маша", "text": "Нашёл все поля и отступы, исправил за минуту.", "source": "fix"}


def post(c, data, ip="10.9.0.1"):
    return c.post("/api/reviews", json=data, environ_base={"REMOTE_ADDR": ip})


def admin_find(text):
    rows = admin_client().get("/api/admin/reviews").get_json()["reviews"]
    return next(r for r in rows if r["text"] == text)


def test_review_hidden_until_published_then_on_page():
    text = "Отличный сервис, нормоконтроль прошёл с первого раза."
    assert post(client(), {**GOOD, "text": text}).status_code == 201
    assert text not in [r["text"] for r in client().get("/api/reviews").get_json()["items"]]

    r = admin_find(text)
    assert r["status"] == "pending" and r["source"] == "fix"
    assert admin_client().patch(f"/api/admin/reviews/{r['id']}", json={"status": "published"}).status_code == 200

    data = client().get("/api/reviews").get_json()
    assert text in [x["text"] for x in data["items"]] and data["count"] >= 1 and data["average"]
    page = client().get("/reviews")
    assert page.status_code == 200 and text in page.get_data(as_text=True)   # пререндер для поисковиков

    admin_client().patch(f"/api/admin/reviews/{r['id']}", json={"status": "hidden"})
    assert text not in [x["text"] for x in client().get("/api/reviews").get_json()["items"]]
    assert admin_client().delete(f"/api/admin/reviews/{r['id']}").status_code == 200


def test_review_validation():
    c = client()
    assert post(c, {**GOOD, "rating": 0}).status_code == 400
    assert post(c, {**GOOD, "rating": 6}).status_code == 400
    assert post(c, {**GOOD, "text": "ок"}).status_code == 400
    assert post(c, {**GOOD, "text": "x" * 2001}).status_code == 400
    assert post(c, {**GOOD, "text": "Заходите на https://spam.example всё дёшево"}).status_code == 400


def test_anonymous_name_and_honeypot():
    text = "Без имени, но всё понравилось."
    assert post(client(), {**GOOD, "name": "  ", "text": text}, ip="10.9.0.2").status_code == 201
    r = admin_find(text)
    admin_client().patch(f"/api/admin/reviews/{r['id']}", json={"status": "published"})
    item = next(x for x in client().get("/api/reviews").get_json()["items"] if x["text"] == text)
    assert item["name"] == "Аноним"

    bot = "Бот заполнил скрытое поле и ушёл."
    assert post(client(), {**GOOD, "text": bot, "website": "x"}, ip="10.9.0.3").status_code == 200
    rows = admin_client().get("/api/admin/reviews").get_json()["reviews"]
    assert bot not in [x["text"] for x in rows]


def test_review_rate_limited_per_ip():
    c = client()
    codes = [post(c, {**GOOD, "text": f"Отзыв номер {n}, всё хорошо."}, ip="10.9.0.9").status_code for n in range(4)]
    assert codes == [201, 201, 201, 429]


def test_review_admin_only():
    assert client().get("/api/admin/reviews").status_code == 401
    assert client().patch("/api/admin/reviews/1", json={"status": "published"}).status_code == 401
    assert admin_client().patch("/api/admin/reviews/1", json={"status": "boom"}).status_code == 400


def test_reviews_in_sitemap():
    assert "/reviews" in server.app.test_client().get("/sitemap.xml").get_data(as_text=True)
