# -*- coding: utf-8 -*-
"""Эталонная курсовая (scripts/make_sample_coursework.py): ни одного замечания ни в одном режиме."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
from make_sample_coursework import build  # noqa: E402

from checker import run_normocontrol  # noqa: E402
from checker.fixers import fix_docx  # noqa: E402
from checker.norms import PROFILES  # noqa: E402


@pytest.fixture(scope="module")
def sample(tmp_path_factory):
    path = tmp_path_factory.mktemp("sample") / "coursework.docx"
    build().save(path)
    return str(path)


@pytest.mark.parametrize("profile, standards", [
    ("coursework", ()),
    ("vkr", ()),
    ("custom", ("gost-7.32", "gost-7.0.100", "gost-7.0.5")),
])
def test_sample_has_no_issues(sample, profile, standards):
    report = run_normocontrol(sample, profile, standards=standards)
    assert [(i.location, i.message) for i in report.issues] == []


def test_autofix_leaves_sample_clean(sample, tmp_path):
    result = fix_docx(sample, str(tmp_path / "fixed.docx"), PROFILES["coursework"])
    assert result.after.issues == [] and result.total_fixed == 0
