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
            {"name": name, "count": len(items), "issues": [asdict(i) for i in items]}
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

_CSS = """
:root{--paper:#f6f2e8;--ink:#23241f;--soft:#5b5a52;--red:#a3323d;--green:#3f6b46;--line:#ddd5c0}
body{margin:0;padding:40px 20px;background:var(--paper);color:var(--ink);
 font-family:Georgia,"Times New Roman",serif;line-height:1.5}
.card{max-width:860px;margin:0 auto;background:#fffdf8;border:1px solid var(--line);padding:40px 48px}
h1{font-size:26px;margin:0 0 6px}.meta{color:var(--soft);font-size:14px}
.stamp{display:inline-block;margin:18px 0;padding:8px 16px;border:3px solid;border-radius:6px;font-weight:bold}
.bad{color:var(--red)}.ok{color:var(--green)}
details{border:1px solid var(--line);border-radius:4px;margin-bottom:12px}
summary{cursor:pointer;padding:10px 16px;font-weight:bold;display:flex;justify-content:space-between}
table{width:100%;border-collapse:collapse;font-size:14px}
td{padding:7px 16px;border-top:1px solid var(--line);vertical-align:top}
td.loc{width:40%;color:var(--soft);font-size:12.5px}
.notes{color:var(--soft);font-size:14px}
"""


def build_html_report(report, source_name):
    e = html_lib.escape
    clean = report.is_clean()
    total = len(report.issues)
    stamp = ("СООТВЕТСТВУЕТ НОРМАМ" if clean else f"ЗАМЕЧАНИЙ: {total}")
    sections = ""
    for category, items in report.by_category().items():
        rows = "".join(
            f'<tr><td class="loc">{e(i.location)}</td><td>{e(i.message)}</td></tr>' for i in items
        )
        sections += (f'<details open><summary><span>{e(category)}</span><span>{len(items)}</span>'
                     f'</summary><table>{rows}</table></details>')
    notes = "".join(f"<li>{e(n)}</li>" for n in report.notes)
    body = (f'<ul class="notes">{notes}</ul>' if notes else "") + (
        "<p class='ok'>Замечаний не обнаружено.</p>" if clean else sections)
    return f"""<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8">
<title>Нормоконтроль — {e(source_name)}</title><style>{_CSS}</style></head>
<body><div class="card">
<h1>Отчёт нормоконтроля</h1>
<div class="meta">{e(source_name)} · {e(report.profile_title)} · {datetime.now().strftime('%d.%m.%Y %H:%M')}</div>
<div class="stamp {'ok' if clean else 'bad'}">{stamp}</div>
{body}
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
