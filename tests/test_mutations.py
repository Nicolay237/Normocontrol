# -*- coding: utf-8 -*-
"""
Проверка «от противного»: в эталонную курсовую по одной вносятся ошибки оформления
(каталог — tests/mutations.py), и каждая должна попасть в отчёт. Для исправимых —
автоисправление должно её убрать. Отдельно — все совместимые ошибки в одной работе.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
from make_sample_coursework import build  # noqa: E402

from checker import run_normocontrol  # noqa: E402
from checker.fixers import fix_docx  # noqa: E402
from checker.norms import PROFILES  # noqa: E402
from mutations import COMBINED, MUTATIONS  # noqa: E402

BY_KEY = {m.key: m for m in MUTATIONS}


def broken(tmp_path, *mutations):
    doc = build()
    for m in mutations:
        m.apply(doc)
    path = tmp_path / "broken.docx"
    doc.save(path)
    return str(path)


def report_for(path, profile):
    return [i.message for i in run_normocontrol(path, profile).issues]


@pytest.mark.parametrize("m", MUTATIONS, ids=[m.key for m in MUTATIONS])
def test_error_is_caught(m, tmp_path):
    msgs = report_for(broken(tmp_path, m), m.profile)
    assert any(m.expect in x for x in msgs), f"{m.title} ({m.gost}) не найдено. Замечания: {msgs[:8]}"


FIXABLE = [m for m in MUTATIONS if m.fixable]


@pytest.mark.parametrize("m", FIXABLE, ids=[m.key for m in FIXABLE])
def test_error_is_autofixed(m, tmp_path):
    path = broken(tmp_path, m)
    result = fix_docx(path, str(tmp_path / "fixed.docx"), PROFILES[m.profile])
    left = [i.message for i in result.after.issues if m.expect in i.message]
    assert not left, f"{m.title}: после автоисправления осталось {left}"


def test_combined_document_catches_every_error(tmp_path):
    mutations = [BY_KEY[k] for k in COMBINED]
    assert not any(m.standalone for m in mutations)
    msgs = report_for(broken(tmp_path, *mutations), "vkr")
    missed = [f"{m.key}: {m.title}" for m in mutations if not any(m.expect in x for x in msgs)]
    assert not missed, f"не найдено в работе со всеми ошибками: {missed}"


def test_combined_document_autofix(tmp_path):
    mutations = [BY_KEY[k] for k in COMBINED]
    path = broken(tmp_path, *mutations)
    result = fix_docx(path, str(tmp_path / "fixed.docx"), PROFILES["vkr"])
    still = [m.key for m in mutations if m.fixable and any(m.expect in i.message for i in result.after.issues)]
    assert not still, f"автоисправление не справилось в общей работе: {still}"
    assert len(result.after.issues) < len(result.before.issues) / 2
