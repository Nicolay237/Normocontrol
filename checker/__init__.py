# -*- coding: utf-8 -*-
"""Нормоконтроль: проверка .docx/.pdf на соответствие ГОСТ 7.32-2017."""

import os
import time
import hashlib
import threading

from .norms import PROFILES, get_profile, describe_profile
from .report import Report, Issue, build_html_report, format_text_report
from . import title_page as _tp


def resolve_profile(profile, standards=()):
    """'vkr' | 'coursework' | 'custom' (+ набор ГОСТов, см. standards.py) или готовый словарь норм."""
    if not isinstance(profile, str):
        return profile
    if profile == "custom":
        from .standards import build_profile
        return build_profile(standards)
    return get_profile(profile)


def run_normocontrol(path, profile="vkr", title_page_template=None, packs=(), standards=()):
    """
    Проверяет файл по профилю норм ('vkr' | 'coursework' | 'custom') и возвращает Report.
    packs — дополнительные проверки вуза [(ключ, настройки JSON)], см. checker/packs;
    standards — выбранные ГОСТы для профиля 'custom', см. checker/standards.py.
    """
    norms = resolve_profile(profile, standards)
    report = Report(profile_key=norms["key"], profile_title=norms["title"])
    ext = os.path.splitext(path)[1].lower()
    if ext == ".docx":
        from docx import Document
        from .docx_checks import check_docx
        doc = Document(path)
        check_docx(doc, report, norms, packs)
        if title_page_template is None and _tp.TITLE_PAGE_TEMPLATE_PATH:
            title_page_template = _tp.load_title_page_template(_tp.TITLE_PAGE_TEMPLATE_PATH)
        _tp.check_title_page(doc, title_page_template, report)
    elif ext == ".pdf":
        from .pdf_checks import check_pdf
        check_pdf(path, report, norms)
    else:
        raise ValueError(f"Неподдерживаемый формат файла: '{ext}'. Ожидается .docx или .pdf")
    if norms.get("strip_clauses"):
        from .docx_checks import strip_gost732_refs
        for issue in report.issues:
            issue.message = strip_gost732_refs(issue.message)
    return report


# ── кеш по содержимому файла ──────────────────────────────────────────────

_CACHE = {}
_LOCK = threading.Lock()
_TTL = 3600
_MAX = 200


def _file_hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run_normocontrol_cached(path, profile="vkr", packs=(), standards=()):
    """Повторная проверка того же файла (побайтово) с тем же профилем и пакетами берётся из кеша."""
    packs, standards = tuple(packs), tuple(standards)
    key = (_file_hash(path), profile, os.path.splitext(path)[1].lower(), packs, standards)
    now = time.time()
    with _LOCK:
        hit = _CACHE.get(key)
        if hit and now - hit[1] < _TTL:
            return hit[0]
    report = run_normocontrol(path, profile, packs=packs, standards=standards)
    with _LOCK:
        if len(_CACHE) >= _MAX:
            _CACHE.pop(min(_CACHE, key=lambda k: _CACHE[k][1]), None)
        _CACHE[key] = (report, now)
    return report
