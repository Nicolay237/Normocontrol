# -*- coding: utf-8 -*-
"""SEO: свои заголовки и текст у страниц, robots.txt, sitemap.xml, перенаправление на основной домен."""

import os
import re

import pytest

import app as server

needs_dist = pytest.mark.skipif(not os.path.isdir(server.DIST_DIR), reason="фронтенд не собран")


def client():
    return server.app.test_client()


def title(html):
    return re.search(r"<title>(.*?)</title>", html, re.S).group(1)


@needs_dist
@pytest.mark.parametrize("path,needle", [
    ("/", "Нормоконтроль онлайн"),
    ("/vkr", "Проверка оформления ВКР"),
    ("/coursework", "курсовой работы"),
    ("/gost", "Требования ГОСТ 7.32-2017"),
])
def test_public_pages_have_own_title_text_and_canonical(path, needle):
    r = client().get(path)
    html = r.data.decode()
    assert r.status_code == 200
    assert needle in title(html)
    assert html.count("<title>") == 1 and html.count('name="description"') == 1
    assert f'<link rel="canonical" href="http://localhost{path}">' in html
    assert 'property="og:image"' in html and "application/ld+json" in html
    # текст страницы есть в HTML ещё до запуска JavaScript
    root = html.split('<div id="root">', 1)[1].split("</body>", 1)[0]
    assert "<h1>" in root and len(root) > 300


@needs_dist
def test_gost_page_has_faq_markup():
    html = client().get("/gost").data.decode()
    assert '"@type": "FAQPage"' in html and "Какие поля в курсовой" in html


@needs_dist
def test_private_and_unknown_pages_not_indexed():
    for path in ("/login", "/admin", "/account"):
        r = client().get(path)
        assert r.status_code == 200 and 'name="robots" content="noindex"' in r.data.decode()
    r = client().get("/no-such-page")
    assert r.status_code == 404 and 'content="noindex"' in r.data.decode()


def test_robots_and_sitemap(monkeypatch):
    monkeypatch.setenv("SITE_URL", "https://normocontrol.site")
    c = client()
    robots = c.get("/robots.txt", base_url="https://normocontrol.site").data.decode()
    assert "Disallow: /api/" in robots and "Sitemap: https://normocontrol.site/sitemap.xml" in robots
    sm = c.get("/sitemap.xml", base_url="https://normocontrol.site")
    assert sm.mimetype == "application/xml"
    locs = re.findall(r"<loc>(.*?)</loc>", sm.data.decode())
    assert locs == ["https://normocontrol.site/", "https://normocontrol.site/vkr",
                    "https://normocontrol.site/coursework", "https://normocontrol.site/standards",
                    "https://normocontrol.site/gost"]


def test_redirect_to_canonical_domain(monkeypatch):
    monkeypatch.setenv("SITE_URL", "https://normocontrol.site")
    c = client()
    for host in ("http://www.normocontrol.site", "https://normocontrol.onrender.com"):
        r = c.get("/vkr?x=1", base_url=host)
        assert r.status_code == 301 and r.headers["Location"] == "https://normocontrol.site/vkr?x=1"
    # проверка здоровья Render и API работают на любом адресе
    assert c.get("/health", base_url="https://normocontrol.onrender.com").status_code == 200
    assert c.get("/api/profiles", base_url="https://normocontrol.onrender.com").status_code == 200
    # на основном домене и локально — без перенаправлений
    assert c.get("/robots.txt", base_url="https://normocontrol.site").status_code == 200
    assert c.get("/robots.txt").status_code == 200


def test_no_redirect_without_site_url(monkeypatch):
    monkeypatch.delenv("SITE_URL", raising=False)
    assert client().get("/robots.txt", base_url="https://normocontrol.onrender.com").status_code == 200


@needs_dist
def test_verification_meta(monkeypatch):
    monkeypatch.setenv("YANDEX_VERIFICATION", "abc123")
    monkeypatch.setenv("GOOGLE_VERIFICATION", "g-456")
    html = client().get("/").data.decode()
    assert '<meta name="yandex-verification" content="abc123">' in html
    assert '<meta name="google-site-verification" content="g-456">' in html
