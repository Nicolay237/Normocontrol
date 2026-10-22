# -*- coding: utf-8 -*-
"""
Поисковая оптимизация: у каждой публичной страницы свои <title>, описание, канонический
адрес, разметка для соцсетей и schema.org, а внутри <div id="root"> — готовый HTML с
текстом страницы. Поисковый робот (особенно Яндекс, который плохо выполняет JavaScript)
сразу видит содержимое; в браузере React просто рисует поверх него интерфейс.

Адрес сайта — переменная SITE_URL (https://normocontrol.site). Пока она не задана,
ссылки строятся от адреса текущего запроса и никаких перенаправлений нет.
"""

import os
import json
import html
from datetime import date

from checker import PROFILES, describe_profile

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SITE_NAME = "Нормоконтроль"
e = html.escape


def site_url():
    return os.environ.get("SITE_URL", "").strip().rstrip("/")


def _load_gost():
    with open(os.path.join(BASE_DIR, "content", "gost.json"), encoding="utf-8") as fh:
        return json.load(fh)


GOST = _load_gost()


# ── публичные страницы ────────────────────────────────────────────────────

def _profile_page(key, path, title, description):
    p = PROFILES[key]

    def body():
        norms = "".join(f"<li><b>{e(n['name'])}</b> — {e(n['value'])}</li>"
                        for n in describe_profile(p)["norms"])
        return (f"<h1>{e(p['title'])} — проверка оформления по ГОСТ 7.32-2017</h1>"
                f"<p>{e(p['description'])}</p>"
                "<p>Загрузите файл .docx или .pdf: сервис покажет каждое отклонение от норм с номером "
                "страницы и абзаца, а для .docx — выдаст копию работы с отметками на местах ошибок.</p>"
                f"<h2>Что проверяется</h2><ul>{norms}</ul>"
                '<p><a href="/gost">Требования ГОСТ 7.32-2017 к оформлению</a></p>')
    return {"path": path, "title": title, "description": description, "body": body}


def _home_body():
    return (
        "<h1>Нормоконтроль онлайн — проверка оформления ВКР и курсовых по ГОСТ</h1>"
        "<p>Загрузите работу в формате .docx или .pdf — сервис сверит поля, шрифт, межстрочный интервал, "
        "абзацный отступ, заголовки, подписи к рисункам и таблицам и нумерацию страниц с ГОСТ 7.32-2017 "
        "и покажет, где именно найдены отклонения.</p>"
        '<ul><li><a href="/vkr">Проверка выпускной квалификационной работы (ВКР, диплом)</a></li>'
        '<li><a href="/coursework">Проверка курсовой работы и реферата</a></li>'
        '<li><a href="/gost">Требования ГОСТ 7.32-2017 к оформлению</a></li></ul>'
    )


def _gost_body():
    parts = [f"<h1>{e(GOST['title'])}</h1>", f"<p>{e(GOST['intro'])}</p>"]
    for s in GOST["sections"]:
        items = "".join(f"<li>{e(i)}</li>" for i in s["items"])
        parts.append(f"<h2>{e(s['heading'])} ({e(s['clause'])})</h2><ul>{items}</ul>")
    parts.append("<h2>Частые вопросы</h2>")
    for f in GOST["faq"]:
        parts.append(f"<h3>{e(f['q'])}</h3><p>{e(f['a'])}</p>")
    parts.append('<p><a href="/vkr">Проверить ВКР</a> · <a href="/coursework">Проверить курсовую</a></p>')
    return "".join(parts)


def _standards_body():
    from checker.standards import GROUPS, STANDARDS
    parts = ["<h1>Проверка оформления работы по выбранным ГОСТам</h1>",
             "<p>Отметьте стандарты из своей методички — сервис проверит работу только по ним. "
             "Взаимоисключающие стандарты выбрать вместе нельзя.</p>"]
    for g in GROUPS:
        items = "".join(f"<li><b>{e(s['code'])}</b> — {e(s['title'])}. {e(s['about'])}</li>"
                        for s in STANDARDS if s["group"] == g["key"])
        parts.append(f"<h2>{e(g['title'])}</h2><p>{e(g['hint'])}</p><ul>{items}</ul>")
    return "".join(parts)


PAGES = {
    "/": {"path": "/",
          "title": "Нормоконтроль онлайн — проверка оформления ВКР и курсовых по ГОСТ 7.32-2017",
          "description": "Бесплатная проверка оформления дипломной, выпускной и курсовой работы по ГОСТ 7.32-2017: "
                         "поля, шрифт, интервалы, отступы, заголовки, подписи и нумерация страниц. "
                         "Загрузите .docx или .pdf.",
          "body": _home_body},
    "/vkr": _profile_page(
        "vkr", "/vkr", "Проверка оформления ВКР и диплома по ГОСТ 7.32-2017 онлайн — Нормоконтроль",
        "Проверьте оформление выпускной квалификационной работы по ГОСТ 7.32-2017: поля, Times New Roman 14, "
        "интервал 1,5, отступ 1,25, заголовки, подписи, нумерация. Отчёт с номерами страниц."),
    "/coursework": _profile_page(
        "coursework", "/coursework", "Проверка оформления курсовой работы по ГОСТ онлайн — Нормоконтроль",
        "Онлайн-проверка оформления курсовой работы и реферата по ГОСТ 7.32-2017: поля, шрифт 12–14 пт, "
        "интервалы, отступы, заголовки, рисунки и таблицы. Загрузите .docx или .pdf."),
    "/standards": {"path": "/standards",
                   "title": "Проверка по ГОСТ 7.32, ГОСТ Р 2.105, ГОСТ Р 7.0.11 и 7.0.100 онлайн — Нормоконтроль",
                   "description": "Выберите стандарты из своей методички: ГОСТ 7.32-2017, ГОСТ Р 2.105-2019 (ЕСКД), "
                                  "ГОСТ Р 7.0.11-2011 (диссертации), список литературы по ГОСТ Р 7.0.100-2018 или "
                                  "ГОСТ 7.1-2003, ссылки по ГОСТ Р 7.0.5-2008.",
                   "body": _standards_body},
    "/gost": {"path": "/gost", "title": f"{GOST['title']} — Нормоконтроль",
              "description": GOST["description"], "body": _gost_body},
}

# служебные страницы: доступны, но не индексируются
NOINDEX = {"/login", "/register", "/account", "/admin"}


# ── вставка в index.html ──────────────────────────────────────────────────

def _jsonld(page, base):
    data = [{
        "@context": "https://schema.org", "@type": "WebApplication", "name": SITE_NAME,
        "url": base + "/", "applicationCategory": "EducationalApplication", "operatingSystem": "Web",
        "inLanguage": "ru", "description": PAGES["/"]["description"],
        "offers": {"@type": "Offer", "price": "0", "priceCurrency": "RUB"},
    }]
    if page["path"] == "/gost":
        data.append({
            "@context": "https://schema.org", "@type": "FAQPage",
            "mainEntity": [{"@type": "Question", "name": f["q"],
                            "acceptedAnswer": {"@type": "Answer", "text": f["a"]}} for f in GOST["faq"]],
        })
    return "".join(
        '<script type="application/ld+json">' + json.dumps(d, ensure_ascii=False).replace("</", "<\\/") + "</script>"
        for d in data)


def head_and_body(path, base):
    """
    Для пути запроса: {"head": теги для <head>, "body": HTML внутри #root, "status": HTTP-код,
    "title"/"description": None — оставить значения из index.html}. base — адрес сайта без «/» в конце.
    """
    path = path.rstrip("/") or "/"
    page = PAGES.get(path)
    tags = []
    for env, name in (("YANDEX_VERIFICATION", "yandex-verification"),
                      ("GOOGLE_VERIFICATION", "google-site-verification")):
        if os.environ.get(env):
            tags.append(f'<meta name="{name}" content="{e(os.environ[env])}">')

    if not page:
        status = 200 if path in NOINDEX else 404
        tags.append('<meta name="robots" content="noindex">')
        return {"head": "".join(tags), "body": "", "status": status, "title": None, "description": None}

    url = base + (page["path"] if page["path"] != "/" else "/")
    title, desc = page["title"], page["description"]
    tags += [
        f'<link rel="canonical" href="{e(url)}">',
        f'<meta property="og:type" content="website">',
        f'<meta property="og:site_name" content="{SITE_NAME}">',
        f'<meta property="og:locale" content="ru_RU">',
        f'<meta property="og:title" content="{e(title)}">',
        f'<meta property="og:description" content="{e(desc)}">',
        f'<meta property="og:url" content="{e(url)}">',
        f'<meta property="og:image" content="{e(base)}/og.png">',
        f'<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">',
        f'<meta name="twitter:card" content="summary_large_image">',
        _jsonld(page, base),
    ]
    return {"head": "".join(tags), "body": f'<div class="seo-prerender">{page["body"]()}</div>',
            "status": 200, "title": title, "description": desc}


def robots_txt(base):
    return (
        "User-agent: *\n"
        "Disallow: /api/\n"
        "Disallow: /admin\n"
        "Disallow: /account\n"
        "Disallow: /login\n"
        "Disallow: /register\n"
        f"\nSitemap: {base}/sitemap.xml\n"
    )


def sitemap_xml(base, lastmod=None):
    lastmod = lastmod or date.today().isoformat()
    prio = {"/": "1.0", "/vkr": "0.9", "/coursework": "0.9", "/standards": "0.8", "/gost": "0.8"}
    urls = "".join(
        f"<url><loc>{e(base + (p if p != '/' else '/'))}</loc><lastmod>{lastmod}</lastmod>"
        f"<priority>{prio.get(p, '0.5')}</priority></url>"
        for p in PAGES)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n')
