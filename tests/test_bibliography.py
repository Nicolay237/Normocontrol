# -*- coding: utf-8 -*-
"""Список источников: оформление записей по ГОСТ Р 7.0.100-2018 и ссылки [N] в тексте."""

import pytest
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm

import make_docs as md
from checker import run_normocontrol
from checker.bibliography import check_entry, _parse_cite
from checker.fixers import fix_docx
from checker.norms import get_profile

GOOD = [
    "Иванов, И. И. Методы анализа данных / И. И. Иванов. – Москва : Наука, 2020. – 240 с.",
    "Шереметьева, А. Интегрированный поиск в каталогах библиотек / А. Шереметьева. – Текст : электронный "
    "// Наука и инновации. – 2019. – № 5 (195). – С. 12–14. – URL: https://elibrary.ru/item.asp?id=38240108 "
    "(дата обращения: 15.10.2019).",
    "Об образовании в Российской Федерации : Федеральный закон № 273-ФЗ от 29.12.2012. – Текст : электронный.",
    "ГОСТ 7.32–2017. Отчёт о научно-исследовательской работе. Структура и правила оформления. – Москва : "
    "Стандартинформ, 2017. – 32 с.",
    "Python : официальный сайт. – URL: https://www.python.org (дата обращения: 01.05.2025).",
]


@pytest.mark.parametrize("entry", GOOD)
def test_correct_entries_have_no_remarks(entry):
    assert check_entry(entry) == []


@pytest.mark.parametrize("entry,needle", [
    ("Иванов И.И. Методы анализа данных. – Москва : Наука, 2020. – 240 с.", "запятая"),
    ("Иванов, И.И. Методы анализа данных. – Москва : Наука, 2020. – 240 с.", "через пробел"),
    ("Иванов, И. И. Методы анализа. – М.: Наука, 2020. – 240 с.", "Москва"),
    ("Иванов, И. И. Методы анализа. – Москва: Наука, 2020. – 240 с.", "двоеточием"),
    ("Иванов, И. И. Методы анализа. - Москва : Наука, 2020. - 240 с.", "тире"),
    ("Иванов, И. И. Методы анализа. – Москва : Наука, 2020.", "объём"),
    ("Иванов, И. И. Методы анализа. – Москва : Наука. – 240 с.", "год"),
    ("Статья // Журнал. – 2020. – №5. – С. 3–5.", "№ 5"),
    ("Сайт [Электронный ресурс]. – URL: https://a.ru (дата обращения: 01.01.2024).", "Электронный ресурс"),
    ("Сайт // habr URL: https://habr.com (дата обращения: 01.01.2024).", "точка и тире"),
    ("Сайт. – https://habr.com (дата обращения: 01.01.2024).", "«URL:»"),
    ("Сайт. – URL: https://habr.com", "дата обращения"),
])
def test_entry_errors(entry, needle):
    msgs = check_entry(entry)
    assert any(needle in m for m in msgs), msgs


@pytest.mark.parametrize("inner,expected", [
    ("3", {3}), ("3, с. 25", {3}), ("1–4", {1, 2, 3, 4}), ("1, 5; 7", {1, 5, 7}),
    ("принят Государственной думой", None), ("Электронный ресурс", None),
])
def test_parse_citation(inner, expected):
    assert _parse_cite(inner) == expected


def work(entries, citations):
    """Работа: текст со ссылками и список источников."""
    doc = md.new_document()
    md.structural(doc, "ВВЕДЕНИЕ", page_break=False)
    for c in citations:
        md.body(doc, f"Подход описан в литературе {c}, его применяют в разных областях знания и практики.")
    md.structural(doc, "ЗАКЛЮЧЕНИЕ")
    md.body(doc)
    md.structural(doc, "СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ")
    for i, e in enumerate(entries, 1):
        md.body(doc, f"{i}. {e}")
    return doc


def bib_issues(doc, tmp_path):
    path = tmp_path / "w.docx"
    doc.save(path)
    return [i for i in run_normocontrol(str(path), "vkr").issues if i.category == "Список источников"]


def test_correct_list_with_citations_is_clean(tmp_path):
    assert bib_issues(work(GOOD[:3], ["[1]", "[2, с. 13]", "[3]"]), tmp_path) == []


def test_citation_problems(tmp_path):
    issues = bib_issues(work(GOOD[:4], ["[2]", "[1]", "[7]"]), tmp_path)
    text = " | ".join(i.message for i in issues)
    assert "несуществующий источник" in text            # [7] при 4 источниках
    assert "порядке упоминания" in text                 # [2] раньше [1]
    assert sum("нет ссылки" in i.message for i in issues) == 2   # 3 и 4 не упомянуты


def test_numbering_problems(tmp_path):
    doc = md.new_document()
    md.structural(doc, "СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ", page_break=False)
    md.body(doc, "1) " + GOOD[0])
    md.body(doc, "3. " + GOOD[3])
    text = " | ".join(i.message for i in bib_issues(doc, tmp_path))
    assert "цифра с точкой" in text and "ожидался № 2" in text


def test_text_after_list_is_not_an_entry(tmp_path):
    doc = work(GOOD[:1], ["[1]"])
    md.body(doc, "Обычный абзац после списка без признаков библиографической записи.")
    assert bib_issues(doc, tmp_path) == []


def test_fixer_corrects_entries_and_keeps_spaced_colons(tmp_path):
    bad = [
        "Иванов И.И. Методы анализа данных / И. И. Иванов. - М.: Наука, 2020. - 240 с.",
        "Статья о распознавании // habr URL: https://habr.com/ru/articles/1/ (дата обращения: 15.05.2025).",
        "Петров, П. П. Статья // Журнал. – 2021. – №7. – С. 5–9.",
    ]
    doc = work(bad, ["[1]", "[2]", "[3]"])
    src, dst = tmp_path / "src.docx", tmp_path / "dst.docx"
    doc.save(src)
    r = fix_docx(str(src), str(dst), get_profile("vkr"))
    before = [i for i in r.before.issues if i.category == "Список источников"]
    after = [i for i in r.after.issues if i.category == "Список источников"]
    assert before and after == [], [i.message for i in after]
    from docx import Document
    texts = [p.text for p in Document(str(dst)).paragraphs]
    assert "1. Иванов, И. И. Методы анализа данных / И. И. Иванов. – Москва : Наука, 2020. – 240 с." in texts
    assert any("// habr. – URL: https://habr.com" in t for t in texts)
    assert any("№ 7" in t for t in texts)
