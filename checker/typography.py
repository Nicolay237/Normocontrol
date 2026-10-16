# -*- coding: utf-8 -*-
"""Типографика: пробелы и пустые строки (общее для docx/pdf)."""

import re

# пробел перед знаком препинания: «слово , слово»; «1 : 2» (отношение) не трогаем
SPACE_BEFORE_SIMPLE = re.compile(r"(?<=[^\s\d]) +([,;!?])(?=\s|$)")
SPACE_BEFORE_DOT = re.compile(r"(?<=[^\s\d.…]) +([.:])(?=\s|$)")
MULTI_SPACE = re.compile(r"(?<=\S)  +(?=\S)")


def check_typography(labeled, report):
    """
    labeled: список (location, text, role, has_page_break) — для docx;
             или (location, text) — для pdf (роль/разрыв не известны).
    Пустым считается абзац без текста, без рисунка и без разрыва страницы:
    абзацы-рисунки и разрывы разделов пустыми строками не являются.
    """
    prev_empty = False
    for entry in labeled:
        loc, text = entry[0], entry[1]
        role = entry[2] if len(entry) > 2 else None
        page_break = entry[3] if len(entry) > 3 else False

        if role in ("image", "table") or page_break:
            prev_empty = False
            continue
        stripped = (text or "").strip()
        if not stripped:
            if prev_empty:
                report.add(loc, "Пустые строки", "два и более пустых абзаца подряд")
            prev_empty = True
            continue
        prev_empty = False

        if role in ("formula",):
            continue
        if MULTI_SPACE.search(text):
            report.add(loc, "Пробелы", "обнаружен двойной (или более) пробел")
        m = SPACE_BEFORE_SIMPLE.search(text) or SPACE_BEFORE_DOT.search(text)
        if m:
            report.add(loc, "Пробелы", f"лишний пробел перед знаком препинания «{m.group(1)}»")
        if role not in ("heading", "structural") and (text.startswith(" ") or text.startswith("\t")):
            report.add(loc, "Пробелы", "текст начинается с пробела/табуляции вместо красной строки")
