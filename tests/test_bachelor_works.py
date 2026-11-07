# -*- coding: utf-8 -*-
"""
Случаи из реальных бакалаврских ВКР (29 работ, ноябрь 2026), на которых проверка ошибалась:
код обычным шрифтом под подписью «Листинг», строки содержания в стиле «TOCEntry», перечень
«сокращений, обозначений и терминов», интервал «[0; 1]» как ссылка на источник, а в PDF —
пробел на стыке шрифтов, точки-заполнители в содержании и нижние индексы в формулах.
"""

from docx.enum.style import WD_STYLE_TYPE
from docx.shared import Cm, Pt
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate

import make_docs as md
from checker import run_normocontrol
from checker.pdf_checks import FORMULA_LINE_RE, TOC_LEADER_RE, _join_words
from checker.typography import check_typography
from checker.report import Report


def check(doc, tmp_path, profile="vkr"):
    path = tmp_path / "work.docx"
    doc.save(path)
    return run_normocontrol(str(path), profile).issues


def plain(doc, text, size=12):
    """Строка кода, набранная обычным шрифтом без отступа — как в реальных работах."""
    p = doc.add_paragraph(text)
    p.paragraph_format.first_line_indent = Cm(0)
    for r in p.runs:
        r.font.size = Pt(size)
    return p


def test_lines_under_listing_caption_are_code(tmp_path):
    doc = md.new_document()
    md.toc(doc)
    md.structural(doc, "ВВЕДЕНИЕ")
    md.body(doc)
    doc.add_heading("1 Реализация", level=1)
    md.body(doc)
    md.body(doc, "Листинг 1.1 – Файловая структура проекта")
    for line in ("vk_news_bot/", "├── main.py          # точка входа, запуск бота",
                 "├── config.py        # конфигурация: токен, категории", "└── requirements.txt # зависимости"):
        plain(doc, line)
    md.body(doc, "Листинг 1.2 – Зависимости проекта")
    for line in ("vkbottle==4.3.4", "feedparser==6.0.11"):
        plain(doc, line)
    after = md.body(doc, "Файл с зависимостями фиксирует точные версии внешних библиотек проекта.")
    after.paragraph_format.first_line_indent = Cm(0)    # ошибка в обычном тексте после листинга
    md.structural(doc, "ЗАКЛЮЧЕНИЕ")
    md.body(doc)
    issues = check(doc, tmp_path)
    code_lines = ("vk_news_bot", "main.py", "config.py", "requirements.txt", "vkbottle", "feedparser")
    wrong = [(i.category, i.location) for i in issues
             if any(c in i.location for c in code_lines) and i.category != "Листинги"]
    assert not wrong, wrong
    # текст после листинга по-прежнему проверяется как текст
    assert any(i.category == "Красная строка" and "Файл с зависимостями" in i.location for i in issues)


def test_caption_below_listing_does_not_swallow_text(tmp_path):
    doc = md.new_document()
    md.toc(doc)
    md.structural(doc, "ВВЕДЕНИЕ")
    md.body(doc)
    t = doc.add_table(rows=1, cols=1)
    t.cell(0, 0).text = "def heartbeat(request):\n    return ok()"
    md.body(doc, "Листинг 1 – Приём сигналов состояния")
    src = plain(doc, "Источник: server/apps/api/services/agent_service.py.", 14)
    src.paragraph_format.first_line_indent = Cm(1.25)
    md.body(doc, "Фрагмент демонстрирует обработку событий и проверку принадлежности устройства.")
    md.structural(doc, "ЗАКЛЮЧЕНИЕ")
    md.body(doc)
    issues = check(doc, tmp_path)
    assert not any(i.category == "Листинги" and "Источник" in i.location for i in issues)


def test_toc_lines_in_tocentry_style(tmp_path):
    doc = md.new_document()
    md.structural(doc, "СОДЕРЖАНИЕ", page_break=False)
    style = doc.styles.add_style("TOCEntry", WD_STYLE_TYPE.PARAGRAPH)
    for line in ("ВВЕДЕНИЕ\t3", "1.7 Сравнение альтернативных подходов\t23", "ЗАКЛЮЧЕНИЕ\t30"):
        doc.add_paragraph(line, style=style)   # левый край, без отступа, интервал 1 — как в содержании
    md.structural(doc, "ВВЕДЕНИЕ")
    md.body(doc)
    md.structural(doc, "ЗАКЛЮЧЕНИЕ")
    md.body(doc)
    issues = check(doc, tmp_path)
    wrong = [(i.category, i.message) for i in issues
             if "Сравнение альтернативных" in i.location and i.category in ("Выравнивание", "Красная строка",
                                                                           "Межстрочный интервал")]
    assert not wrong, wrong


def test_free_form_glossary_heading_and_dash_still_checked(tmp_path):
    doc = md.new_document()
    md.toc(doc)
    md.structural(doc, "ПЕРЕЧЕНЬ СОКРАЩЕНИЙ, ОБОЗНАЧЕНИЙ И ТЕРМИНОВ")
    plain(doc, "API — Application Programming Interface, программный интерфейс", 14)
    plain(doc, "GPU - Graphics Processing Unit, графический процессор", 14)
    md.structural(doc, "ВВЕДЕНИЕ")
    md.body(doc)
    md.structural(doc, "ЗАКЛЮЧЕНИЕ")
    md.body(doc)
    issues = check(doc, tmp_path)
    assert not any(i.category == "Красная строка" and ("API" in i.location or "GPU" in i.location) for i in issues)
    # дефис вместо тире в перечне — настоящая ошибка, её по-прежнему видно
    assert any(i.category == "Пробелы" and "GPU" in i.location and "тире" in i.message for i in issues)


def test_numeric_interval_is_not_a_citation(tmp_path):
    doc = md.new_document()
    md.toc(doc)
    md.structural(doc, "ВВЕДЕНИЕ")
    md.body(doc, "Оценка близости нормирована в диапазоне [0; 1], а сходство — в интервале [0, 1] [1].")
    md.structural(doc, "ЗАКЛЮЧЕНИЕ")
    md.body(doc)
    md.structural(doc, "СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ")
    md.body(doc, "1. Иванов, И. И. Методы анализа данных / И. И. Иванов. – Москва : Наука, 2020. – 240 с.")
    issues = check(doc, tmp_path)
    assert not any("несуществующий источник" in i.message for i in issues)


# ── PDF ──

def word(text, x0, x1, size=14):
    return {"text": text, "x0": x0, "x1": x1, "size": size}


def test_pdf_words_joined_by_real_gaps():
    # «string» моноширинным и точка Times вплотную — одно слово; обычный пробел — 3,5 pt
    assert _join_words([word("тип", 0, 20), word("string", 23.5, 60), word(".", 60, 63)]) == "тип string."
    assert _join_words([word("handler", 0, 40), word(",", 40.3, 43), word("далее", 46.5, 80)]) == "handler, далее"


def test_pdf_toc_leaders_and_formulas_skip_space_checks():
    assert TOC_LEADER_RE.sub("", "1.1 Особенности организации . . . . . 14") == "1.1 Особенности организации"
    assert TOC_LEADER_RE.sub("", "ВВЕДЕНИЕ ............ 11") == "ВВЕДЕНИЕ"
    assert FORMULA_LINE_RE.search("С = 𝑃 × С × 𝑇 , (1)") and not FORMULA_LINE_RE.search("слово , слово")
    rep = Report()
    check_typography([("стр. 3", TOC_LEADER_RE.sub("", "1.1 Обзор . . . . 14")),
                      ("стр. 9", "С = 𝑃 × 𝑇 , (1)", "formula")], rep)
    assert not rep.issues


def test_pdf_font_switch_before_punctuation(tmp_path):
    path = str(tmp_path / "mono.pdf")
    style = ParagraphStyle("b", fontName="Times-Roman", fontSize=14, leading=21)
    story = [Paragraph("The value has type <font face='Courier'>string</font>. Next the "
                       "<font face='Courier'>handler</font>, which accepts a request object.", style)
             for _ in range(30)]
    SimpleDocTemplate(path, pagesize=A4, leftMargin=3 * cm, rightMargin=1.5 * cm).build(story)
    issues = run_normocontrol(path, "vkr").issues
    assert not any("перед знаком препинания" in i.message for i in issues), \
        [i.location for i in issues if "перед знаком" in i.message][:3]


def test_explanation_starting_with_equation_object(tmp_path):
    """«Ct<Tab>– затраты…»: символ набран в старом редакторе формул (объект OLE), текста его не видно."""
    from docx.oxml import parse_xml
    doc = md.new_document()
    md.toc(doc)
    md.structural(doc, "ВВЕДЕНИЕ")
    md.body(doc)
    p = doc.add_paragraph()
    p._p.append(parse_xml('<w:r xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                          '<w:object/></w:r>'))
    p.add_run("\t– затраты i-го периода реализации проекта;")
    spaced = md.body(doc, "     СТ – стоимость 1 кВт/ч электроэнергии;")   # пробелы вместо отступа — ошибка
    md.structural(doc, "ЗАКЛЮЧЕНИЕ")
    md.body(doc)
    issues = check(doc, tmp_path)
    starts = [i.location for i in issues if "начинается с пробела" in i.message]
    assert not any("затраты" in loc for loc in starts), starts
    assert any("стоимость 1 кВт" in loc for loc in starts)


def test_picture_in_the_caption_paragraph(tmp_path):
    doc = md.new_document()
    md.toc(doc)
    md.structural(doc, "ВВЕДЕНИЕ")
    md.body(doc)
    p = doc.add_paragraph()
    run = p.add_run()
    run.add_picture(md._png(), width=Cm(4))
    run.add_break()
    p.add_run("Рисунок 1 – Место тестирования в процессе обеспечения качества")
    md.body(doc)
    md.structural(doc, "ЗАКЛЮЧЕНИЕ")
    md.body(doc)
    issues = check(doc, tmp_path)
    assert not any("нет рисунка" in i.message for i in issues)
