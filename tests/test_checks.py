# -*- coding: utf-8 -*-
"""
Тесты проверок. Принцип: эталонный документ даёт НОЛЬ замечаний (нет ложных
срабатываний), а каждое намеренное нарушение даёт замечание ровно в своей
категории.
"""

import os
import sys

import pytest
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, Cm, RGBColor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from checker import run_normocontrol  # noqa: E402
import make_docs as md  # noqa: E402


def check(doc, tmp_path, profile="vkr"):
    path = tmp_path / "work.docx"
    doc.save(path)
    return run_normocontrol(str(path), profile)


def cats(report):
    return {i.category for i in report.issues}


def dump(report):
    return "\n".join(f"[{i.category}] {i.location}: {i.message}" for i in report.issues)


@pytest.mark.parametrize("profile", ["vkr", "coursework"])
def test_good_document_is_clean(tmp_path, profile):
    report = check(md.good_document(), tmp_path, profile)
    assert report.is_clean(), dump(report)


# ── поля ────────────────────────────────────────────────────────────────

def test_right_margin_1cm_and_1_5cm_both_ok(tmp_path):
    for right in (1.0, 1.5):
        doc = md.good_document()
        doc.sections[0].right_margin = Cm(right)
        assert check(doc, tmp_path).is_clean()


def test_wrong_margins_flagged(tmp_path):
    doc = md.good_document()
    doc.sections[0].left_margin = Cm(2.0)
    doc.sections[0].right_margin = Cm(3.0)
    r = check(doc, tmp_path)
    assert "Поля страницы" in cats(r)
    assert len([i for i in r.issues if i.category == "Поля страницы"]) == 2


def test_page_size_not_a4(tmp_path):
    doc = md.good_document()
    doc.sections[0].page_width = Cm(21.59)
    doc.sections[0].page_height = Cm(27.94)  # Letter
    assert "Формат листа" in cats(check(doc, tmp_path))


# ── шрифты ──────────────────────────────────────────────────────────────

def test_font_inherited_from_style_is_detected(tmp_path):
    # нарушение лежит в стиле, а не в run'ах — раньше такое пропускалось
    doc = md.good_document()
    md.set_style_font(doc.styles["Normal"], "Arial", 14)
    assert "Шрифт" in cats(check(doc, tmp_path))


def test_size_12_flagged_for_vkr_but_not_coursework(tmp_path):
    doc = md.new_document(body_size=12)
    md.structural(doc, "ВВЕДЕНИЕ", page_break=False)
    for _ in range(4):
        md.body(doc)
    md.structural(doc, "ЗАКЛЮЧЕНИЕ")
    md.body(doc)
    md.structural(doc, "СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ")
    md.body(doc, "1. Источник.")
    assert "Кегль шрифта" in cats(check(doc, tmp_path, "vkr"))
    assert "Кегль шрифта" not in cats(check(doc, tmp_path, "coursework"))


def test_size_below_12_flagged_for_coursework(tmp_path):
    doc = md.good_document()
    doc.styles["Normal"].font.size = Pt(10)
    assert "Кегль шрифта" in cats(check(doc, tmp_path, "coursework"))


def test_mono_font_in_listing_allowed(tmp_path):
    doc = md.good_document()
    p = doc.add_paragraph()
    r = p.add_run("print('hello')")
    r.font.name = "Consolas"
    assert "Шрифт" not in cats(check(doc, tmp_path))


def test_superscript_not_flagged_as_small(tmp_path):
    doc = md.good_document()
    p = doc.add_paragraph("Площадь равна 5 м")
    r = p.add_run("2")
    r.font.superscript = True
    r.font.size = Pt(9)
    assert "Кегль шрифта" not in cats(check(doc, tmp_path))


def test_colored_text_flagged(tmp_path):
    doc = md.good_document()
    p = doc.add_paragraph()
    r = p.add_run("Красный текст в основной части.")
    r.font.color.rgb = RGBColor(255, 0, 0)
    assert "Цвет шрифта" in cats(check(doc, tmp_path))


# ── интервал, отступ, выравнивание ──────────────────────────────────────

def test_single_spacing_flagged(tmp_path):
    doc = md.good_document()
    doc.styles["Normal"].paragraph_format.line_spacing = 1.0
    assert "Межстрочный интервал" in cats(check(doc, tmp_path))


def test_unset_spacing_means_single(tmp_path):
    # интервал нигде не задан → в Word это одинарный
    doc = md.good_document()
    ppr = doc.styles["Normal"].element.pPr
    sp = ppr.find(md.qn("w:spacing"))
    for a in list(sp.attrib):
        if a.endswith("line") or a.endswith("lineRule"):
            del sp.attrib[a]
    assert "Межстрочный интервал" in cats(check(doc, tmp_path))


def test_exact_line_spacing_does_not_crash_or_misreport(tmp_path):
    from docx.enum.text import WD_LINE_SPACING
    doc = md.good_document()
    pf = doc.styles["Normal"].paragraph_format
    pf.line_spacing_rule = WD_LINE_SPACING.EXACTLY
    pf.line_spacing = Pt(12)
    r = check(doc, tmp_path)
    msgs = [i.message for i in r.issues if i.category == "Межстрочный интервал"]
    assert msgs and all("228600" not in m and "152400" not in m for m in msgs)


def test_exact_21pt_is_close_to_1_5_and_ok(tmp_path):
    from docx.enum.text import WD_LINE_SPACING
    doc = md.good_document()
    pf = doc.styles["Normal"].paragraph_format
    pf.line_spacing_rule = WD_LINE_SPACING.EXACTLY
    pf.line_spacing = Pt(24)
    assert "Межстрочный интервал" not in cats(check(doc, tmp_path))


def test_left_alignment_flagged(tmp_path):
    doc = md.good_document()
    doc.styles["Normal"].paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
    assert "Выравнивание" in cats(check(doc, tmp_path))


def test_missing_alignment_means_left(tmp_path):
    doc = md.good_document()
    jc = doc.styles["Normal"].element.pPr.find(md.qn("w:jc"))
    doc.styles["Normal"].element.pPr.remove(jc)
    assert "Выравнивание" in cats(check(doc, tmp_path))


def test_wrong_indent_flagged(tmp_path):
    doc = md.good_document()
    doc.styles["Normal"].paragraph_format.first_line_indent = Cm(0.5)
    assert "Красная строка" in cats(check(doc, tmp_path))


def test_where_after_formula_may_have_no_indent(tmp_path):
    from docx.oxml import OxmlElement
    doc = md.good_document()
    f = doc.add_paragraph()
    f._p.append(OxmlElement("m:oMath"))
    w = doc.add_paragraph("где x – значение параметра, определяемое в ходе эксперимента.")
    w.paragraph_format.first_line_indent = Cm(0)
    assert "Красная строка" not in cats(check(doc, tmp_path))


# ── заголовки ───────────────────────────────────────────────────────────

def test_heading_checks(tmp_path):
    doc = md.good_document()
    h = doc.add_heading("2. Практическая часть.", level=1)
    h.runs[0].bold = False
    doc.styles["Heading 1"].font.bold = False
    r = check(doc, tmp_path)
    msgs = " | ".join(i.message for i in r.issues if i.category == "Оформление заголовка")
    assert "жирным" in msgs
    assert "не должно быть точки" in msgs
    assert "после номера" in msgs


def test_default_word_blue_calibri_heading_flagged(tmp_path):
    doc = md.good_document()
    st = doc.styles["Heading 2"]
    md.set_style_font(st, "Calibri Light", 16)
    st.font.color.rgb = RGBColor(0x2F, 0x54, 0x96)
    r = check(doc, tmp_path)
    msgs = " | ".join(i.message for i in r.issues if i.category == "Оформление заголовка")
    assert "Calibri" in msgs and "цвет" in msgs and "16" in msgs


def test_structural_heading_must_be_caps_and_centered(tmp_path):
    doc = md.good_document()
    p = md.structural(doc, "Приложение")
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p2 = md.structural(doc, "Введение.")
    r = check(doc, tmp_path)
    msgs = " | ".join(i.message for i in r.issues if i.category == "Оформление заголовка")
    assert "ПРОПИСНЫМИ" in msgs and "по центру" in msgs and "точки" in msgs


def test_heading_without_new_page_flagged(tmp_path):
    doc = md.good_document()
    doc.styles["Heading 1"].paragraph_format.page_break_before = False
    doc.add_heading("3 Новый раздел без разрыва", level=1)
    r = check(doc, tmp_path)
    assert any("новой страницы" in i.message for i in r.issues)


def test_heading_after_explicit_page_break_ok(tmp_path):
    from docx.enum.text import WD_BREAK
    doc = md.good_document()
    doc.styles["Heading 1"].paragraph_format.page_break_before = False
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
    doc.add_heading("3 Новый раздел", level=1)
    r = check(doc, tmp_path)
    assert not any("новой страницы" in i.message and "Новый раздел" in i.location for i in r.issues)


# ── подписи ─────────────────────────────────────────────────────────────

def test_figure_caption_centered_is_not_alignment_violation(tmp_path):
    # регрессия: центрированная подпись раньше давала «Выравнивание»
    report = check(md.good_document(), tmp_path)
    assert "Выравнивание" not in cats(report)


def test_bad_captions(tmp_path):
    doc = md.good_document()
    img = doc.add_paragraph()
    img.add_run().add_picture(md._png(), width=Cm(3))
    cap = doc.add_paragraph("Рис. 2. схема.")
    cap.alignment = WD_ALIGN_PARAGRAPH.LEFT
    cap.paragraph_format.first_line_indent = Cm(0)
    t = doc.add_paragraph("Таблица 5 Данные")
    t.paragraph_format.first_line_indent = Cm(1.25)
    doc.add_table(rows=1, cols=1).rows[0].cells[0].paragraphs[0].add_run("x")
    r = check(doc, tmp_path)
    c = [i for i in r.issues if i.category in ("Подписи к рисункам и таблицам", "Нумерация")]
    text = " | ".join(i.message for i in c)
    assert "без сокращения" in text
    assert "по центру" in text
    assert "абзацным отступом" in text
    assert "сквозная нумерация" in text


def test_body_sentence_starting_with_word_table_is_not_a_caption(tmp_path):
    doc = md.good_document()
    doc.add_paragraph("Таблица 1 показывает, что результаты эксперимента согласуются с теорией.")
    assert check(doc, tmp_path).is_clean()


# ── списки и прочее ─────────────────────────────────────────────────────

def test_bullet_marker_flagged_dash_ok(tmp_path):
    doc = md.good_document()
    doc.add_paragraph("• пункт с маркером")
    r = check(doc, tmp_path)
    assert "Перечисления" in cats(r)
    assert len([i for i in r.issues if i.category == "Перечисления"]) == 1


def test_page_numbers_missing(tmp_path):
    doc = md.new_document(page_numbers=False)
    md.body(doc)
    assert "Нумерация страниц" in cats(check(doc, tmp_path))


def test_page_numbers_left_aligned(tmp_path):
    doc = md.good_document()
    doc.sections[0].footer.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.LEFT
    assert "Нумерация страниц" in cats(check(doc, tmp_path))


def test_missing_required_sections(tmp_path):
    doc = md.new_document()
    for _ in range(8):
        md.body(doc)
    r = check(doc, tmp_path)
    assert len([i for i in r.issues if i.category == "Структура"]) == 4   # содержание, введение, заключение, список источников


def test_image_paragraphs_are_not_empty_lines(tmp_path):
    doc = md.good_document()
    for _ in range(3):
        p = doc.add_paragraph()
        p.add_run().add_picture(md._png(), width=Cm(2))
        p.paragraph_format.first_line_indent = Cm(0)
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    assert "Пустые строки" not in cats(check(doc, tmp_path))


def test_two_empty_paragraphs_flagged(tmp_path):
    doc = md.good_document()
    doc.add_paragraph("")
    doc.add_paragraph("")
    assert "Пустые строки" in cats(check(doc, tmp_path))


def test_typography(tmp_path):
    doc = md.good_document()
    doc.add_paragraph("Это  предложение с двойным пробелом и лишним пробелом , перед запятой.")
    r = check(doc, tmp_path)
    assert sum(1 for i in r.issues if i.category == "Пробелы") == 2


def test_ratio_and_ellipsis_not_flagged(tmp_path):
    doc = md.good_document()
    doc.add_paragraph("Соотношение сторон 16 : 9, далее идёт многоточие ... и конец текста.")
    assert "Пробелы" not in cats(check(doc, tmp_path))


def test_merged_cells_do_not_duplicate_issues(tmp_path):
    doc = md.good_document()
    t = doc.add_table(rows=1, cols=3)
    a = t.cell(0, 0).merge(t.cell(0, 2))
    a.paragraphs[0].add_run("Объединённая").font.name = "Arial"
    r = check(doc, tmp_path)
    assert len([i for i in r.issues if i.category == "Шрифт (таблица)"]) == 1


def test_unsupported_extension(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("x")
    with pytest.raises(ValueError):
        run_normocontrol(str(f))


def test_unknown_profile(tmp_path):
    f = tmp_path / "a.docx"
    md.good_document().save(f)
    with pytest.raises(ValueError):
        run_normocontrol(str(f), "nope")


def test_page_number_inside_content_control_is_found(tmp_path):
    # Word кладёт «Номер страницы» из галереи в <w:sdt> — раньше это давало ложное «номера не найдены»
    from docx.oxml import OxmlElement
    doc = md.new_document(page_numbers=False)
    md.body(doc)
    footer = doc.sections[0].footer
    p = footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sdt = OxmlElement("w:sdt")
    content = OxmlElement("w:sdtContent")
    sdt.append(content)
    footer._element.remove(p._p)
    content.append(p._p)
    footer._element.append(sdt)
    md._page_field(p)
    assert "Нумерация страниц" not in cats(check(doc, tmp_path))


def test_html_report_is_self_contained_new_design(tmp_path):
    from checker import build_html_report
    doc = md.good_document()
    doc.styles["Normal"].paragraph_format.line_spacing = 1.0
    r = check(doc, tmp_path)
    html = build_html_report(r, "работа <тест>.docx")
    assert 'class="summary"' in html and 'class="overview"' in html
    assert "prefers-color-scheme:dark" in html and "@media print" in html
    assert "работа &lt;тест&gt;.docx" in html          # имя файла экранировано
    assert "<script" not in html and "http" not in html.split("<body>")[1].replace("http://www.w3.org", "")


def test_page_number_note_only_when_issues(tmp_path):
    assert not any("Номера страниц" in n for n in check(md.good_document(), tmp_path).notes)


def test_section_without_page_numbers_flagged(tmp_path):
    from docx.enum.section import WD_SECTION, WD_ORIENT
    doc = md.good_document()
    sec = doc.add_section(WD_SECTION.NEW_PAGE)
    sec.orientation = WD_ORIENT.LANDSCAPE
    sec.page_width, sec.page_height = Cm(29.7), Cm(21.0)
    sec.footer.is_linked_to_previous = False   # пустой собственный колонтитул — номеров нет
    md.body(doc)
    r = check(doc, tmp_path)
    issues = [i for i in r.issues if i.category == "Нумерация страниц"]
    assert len(issues) == 1 and "Раздел документа №2" in issues[0].location


def test_linked_footer_inherits_page_numbers(tmp_path):
    from docx.enum.section import WD_SECTION
    doc = md.good_document()
    doc.add_section(WD_SECTION.NEW_PAGE)   # колонтитул связан с предыдущим — номер наследуется
    md.body(doc)
    assert "Нумерация страниц" not in cats(check(doc, tmp_path))
