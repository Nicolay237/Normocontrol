# -*- coding: utf-8 -*-
"""Модель отчёта и его представления (JSON, HTML для скачивания, текст)."""

import os
import html as html_lib
from dataclasses import dataclass, field, asdict
from datetime import datetime


@dataclass
class Issue:
    location: str
    category: str
    message: str
    # Место в .docx для отметок в файле: ("p", номер блока) — абзац верхнего уровня,
    # ("cell", номер блока, строка, столбец) — ячейка таблицы, None — замечание ко всему документу.
    # Номер блока — порядковый номер в iter_blocks(), он одинаков при каждом открытии файла.
    anchor: object = field(default=None, compare=False, repr=False)

    def public(self):
        return {"location": self.location, "category": self.category, "message": self.message}


@dataclass
class Report:
    issues: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    profile_key: str = ""
    profile_title: str = ""
    _seen: set = field(default_factory=set, repr=False)

    def add(self, location, category, message):
        key = (location, category, message)
        if key in self._seen:  # один и тот же run/ячейка не должны плодить дубли
            return
        self._seen.add(key)
        self.issues.append(Issue(location, category, message))

    def note(self, text):
        if text not in self.notes:
            self.notes.append(text)

    def is_clean(self):
        return not self.issues

    def by_category(self):
        out = {}
        for i in self.issues:
            out.setdefault(i.category, []).append(i)
        return out

    def to_dict(self, source_name=""):
        cats = [
            {"name": name, "count": len(items), "issues": [i.public() for i in items]}
            for name, items in self.by_category().items()
        ]
        return {
            "file": source_name,
            "profile": {"key": self.profile_key, "title": self.profile_title},
            "clean": self.is_clean(),
            "total": len(self.issues),
            "categories": cats,
            "notes": self.notes,
            "checked_at": datetime.now().strftime("%d.%m.%Y %H:%M"),
        }


# ── автономный HTML-отчёт для скачивания ──────────────────────────────────
# Тот же дизайн, что у сайта (Material 3, иконки Lucide), но одним файлом:
# CSS и SVG встроены, работает офлайн, светлая/тёмная тема, версия для печати.

_ICONS = {
    "brand": '<path d="M21.801 10A10 10 0 1 1 17 3.335"/><path d="m9 11 3 3L22 4"/>',
    "ok": '<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>',
    "bad": ('<path d="M12 16h.01"/><path d="M12 8v4"/><path d="M15.312 2a2 2 0 0 1 1.414.586l4.688 4.688A2 2 0 '
            '0 1 22 8.688v6.624a2 2 0 0 1-.586 1.414l-4.688 4.688a2 2 0 0 1-1.414.586H8.688a2 2 0 0 1-1.414-.586'
            'l-4.688-4.688A2 2 0 0 1 2 15.312V8.688a2 2 0 0 1 .586-1.414l4.688-4.688A2 2 0 0 1 8.688 2z"/>'),
    "info": '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
    "chevron": '<path d="m6 9 6 6 6-6"/>',
}


def _svg(name, size=24):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" '
            f'fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" '
            f'stroke-linejoin="round" aria-hidden="true">{_ICONS[name]}</svg>')


def plural_issues(n):
    if n % 10 == 1 and n % 100 != 11:
        return "замечание"
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return "замечания"
    return "замечаний"


_CSS = """
:root{color-scheme:light;
 --primary:#9b2c3a;--on-primary:#fff;
 --error:#ba1a1a;--on-error:#fff;--error-container:#ffdad6;--on-error-container:#410002;
 --ok:#2e6a3b;--ok-container:#b0f2b5;--on-ok-container:#00210c;
 --surface:#fff8f7;--on-surface:#231918;--on-surface-variant:#534342;--outline-variant:#d8c2c0;
 --sc-low:#fff0ef}
@media (prefers-color-scheme:dark){:root{color-scheme:dark;
 --primary:#ffb3b2;--on-primary:#5f1220;
 --error:#ffb4ab;--on-error:#690005;--error-container:#93000a;--on-error-container:#ffdad6;
 --ok:#95d59a;--ok-container:#145226;--on-ok-container:#b0f2b5;
 --surface:#1a1111;--on-surface:#f1dedd;--on-surface-variant:#d8c2c0;--outline-variant:#534342;
 --sc-low:#231919}}
*{box-sizing:border-box}
body{margin:0;background:var(--surface);color:var(--on-surface);
 font:400 14px/20px Roboto,"Segoe UI",system-ui,-apple-system,sans-serif;letter-spacing:.25px}
.wrap{max-width:920px;margin:0 auto;padding:24px 16px 48px}
.bar{display:flex;align-items:center;gap:12px;margin-bottom:24px;font-size:20px;line-height:28px}
.mark{display:grid;place-items:center;width:36px;height:36px;border-radius:50%;background:var(--primary);color:var(--on-primary)}
.mark svg{width:20px;height:20px}
.tag{margin-left:auto;font-size:12px;line-height:16px;font-weight:500;color:var(--on-surface-variant);padding:4px 10px;
 border:1px solid var(--outline-variant);border-radius:8px}
.summary{display:flex;gap:16px;align-items:flex-start;padding:20px 24px;border-radius:16px;
 background:var(--sc-low);border:1px solid var(--outline-variant)}
.s-icon{display:grid;place-items:center;flex-shrink:0;width:48px;height:48px;border-radius:50%}
.s-icon.bad{background:var(--error-container);color:var(--on-error-container)}
.s-icon.ok{background:var(--ok-container);color:var(--on-ok-container)}
.headline{font-size:24px;line-height:32px;font-weight:400;margin:0 0 4px}
.file{font-weight:500;font-size:16px;line-height:24px;overflow-wrap:anywhere}
.meta{color:var(--on-surface-variant)}
.overview{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0 0;padding:0;list-style:none}
.overview a{display:inline-flex;align-items:center;gap:6px;min-height:32px;padding:4px 12px;border-radius:8px;
 border:1px solid var(--outline-variant);color:var(--on-surface);text-decoration:none;font-weight:500}
.overview b{color:var(--error);font-weight:500}
.notes{list-style:none;padding:0;margin:16px 0 0;color:var(--on-surface-variant);display:grid;gap:8px}
.notes li{display:flex;gap:8px}.notes svg{width:18px;height:18px;flex-shrink:0;margin-top:1px}
.clean{color:var(--ok);font-size:16px;line-height:24px;margin-top:16px}
details{margin-top:12px;border-radius:12px;background:var(--sc-low);border:1px solid transparent;overflow:hidden}
summary{display:flex;align-items:center;gap:12px;padding:14px 24px;cursor:pointer;list-style:none;
 font-weight:500;font-size:16px;line-height:24px}
summary::-webkit-details-marker{display:none}
summary .name{flex:1}
.badge{min-width:24px;padding:2px 8px;border-radius:12px;text-align:center;font-size:12px;line-height:16px;
 background:var(--error);color:var(--on-error)}
.chev{display:grid;color:var(--on-surface-variant);transition:transform .2s}
details[open] .chev{transform:rotate(180deg)}
ul.issues{list-style:none;margin:0;padding:0}
ul.issues li{padding:12px 24px;border-top:1px solid var(--outline-variant)}
.msg{display:block}.loc{display:block;margin-top:2px;font-size:12px;line-height:16px;font-weight:500;
 color:var(--on-surface-variant);overflow-wrap:anywhere}
footer{margin-top:32px;padding-top:16px;border-top:1px solid var(--outline-variant);color:var(--on-surface-variant);
 font-size:12px;text-align:center}
@media (max-width:560px){.summary{flex-direction:column;padding:16px}summary{padding:14px 16px}ul.issues li{padding:12px 16px}.tag{display:none}}
@media print{:root{color-scheme:light}
 body{background:#fff;color:#000}.wrap{max-width:none;padding:0}
 .summary,details{background:none;border:1px solid #ccc}
 .overview a{border-color:#ccc}.chev{display:none}
 ul.issues li{break-inside:avoid}}
"""


def build_html_report(report, source_name):
    e = html_lib.escape
    clean = report.is_clean()
    total = len(report.issues)
    cats = report.by_category()
    headline = "Соответствует нормам" if clean else f"{total} {plural_issues(total)}"

    overview = "" if clean else '<ul class="overview">' + "".join(
        f'<li><a href="#cat-{i}">{e(name)} <b>{len(items)}</b></a></li>'
        for i, (name, items) in enumerate(cats.items())) + "</ul>"

    sections = "".join(
        f'<details open id="cat-{i}"><summary><span class="name">{e(name)}</span>'
        f'<span class="badge">{len(items)}</span><span class="chev">{_svg("chevron")}</span></summary>'
        '<ul class="issues">' + "".join(
            f'<li><span class="msg">{e(it.message)}</span><span class="loc">{e(it.location)}</span></li>'
            for it in items) + "</ul></details>"
        for i, (name, items) in enumerate(cats.items()))

    notes = "".join(f"<li>{_svg('info')}<span>{e(n)}</span></li>" for n in report.notes)
    body = (f'<ul class="notes">{notes}</ul>' if notes else "") + (
        '<p class="clean">Замечаний не обнаружено. Документ соответствует заданным нормам.</p>'
        if clean else sections)
    kind = "ok" if clean else "bad"

    return f"""<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>Отчёт нормоконтроля — {e(source_name)}</title><style>{_CSS}</style></head>
<body><div class="wrap">
<div class="bar"><span class="mark">{_svg("brand")}</span>Нормоконтроль<span class="tag">ГОСТ 7.32-2017</span></div>
<div class="summary">
  <span class="s-icon {kind}">{_svg(kind)}</span>
  <div>
    <h1 class="headline">{headline}</h1>
    <div class="file">{e(source_name)}</div>
    <div class="meta">{e(report.profile_title)} · проверено {datetime.now().strftime('%d.%m.%Y %H:%M')}</div>
    {overview}
  </div>
</div>
{body}
<footer>Нормы: ГОСТ 7.32-2017. Отчёт даёт предварительную оценку — окончательное решение остаётся
за нормоконтролем кафедры.</footer>
</div></body></html>"""


def format_text_report(report, source_path):
    lines = ["=" * 70, "ОТЧЁТ НОРМОКОНТРОЛЯ", f"Файл: {source_path}",
             f"Тип работы: {report.profile_title}", "=" * 70]
    if report.notes:
        lines.append("")
        lines += [f"ⓘ {n}" for n in report.notes]
    if report.is_clean():
        lines.append("\nЗамечаний не обнаружено. Документ соответствует заданным нормам.")
        return "\n".join(lines)
    lines.append(f"\nВсего замечаний: {len(report.issues)}\n")
    for category, items in report.by_category().items():
        lines.append(f"--- {category} ({len(items)}) ---")
        lines += [f"  [{i.location}] {i.message}" for i in items]
        lines.append("")
    return "\n".join(lines)
