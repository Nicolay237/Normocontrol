# -*- coding: utf-8 -*-
import os
import sys

import pytest
from reportlab.lib.enums import TA_LEFT

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from checker import run_normocontrol  # noqa: E402
from make_pdfs import make_pdf  # noqa: E402


def run(tmp_path, profile="vkr", **kw):
    p = str(tmp_path / "w.pdf")
    make_pdf(p, **kw)
    return run_normocontrol(p, profile)


def cats(r):
    return {i.category for i in r.issues}


def dump(r):
    return "\n".join(f"[{i.category}] {i.location}: {i.message}" for i in r.issues)


def non_structure(r):
    return [i for i in r.issues if i.category != "Структура"]  # у синтетики нет русских разделов


def test_good_pdf_clean(tmp_path):
    r = run(tmp_path)
    assert not non_structure(r), dump(r)


def test_pdf_wrong_left_margin(tmp_path):
    assert "Поля страницы" in cats(run(tmp_path, left=2.0))


def test_pdf_right_margin_1cm_ok(tmp_path):
    assert "Поля страницы" not in cats(run(tmp_path, right=1.0))


def test_pdf_single_spacing(tmp_path):
    assert "Межстрочный интервал (оценка)" in cats(run(tmp_path, leading=14 * 1.15))


def test_pdf_left_aligned(tmp_path):
    assert "Выравнивание (оценка)" in cats(run(tmp_path, align=TA_LEFT))


def test_pdf_no_indent(tmp_path):
    assert "Красная строка (оценка)" in cats(run(tmp_path, indent=0))


def test_pdf_font_size(tmp_path):
    assert "Кегль шрифта" in cats(run(tmp_path, size=11, leading=11 * 1.15 * 1.5))


def test_pdf_no_page_numbers(tmp_path):
    assert "Нумерация страниц" in cats(run(tmp_path, numbers=False))
