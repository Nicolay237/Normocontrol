# -*- coding: utf-8 -*-
"""
Сравнение титульного листа с образцом. Сравнивается не текст, а форматирование
каждой строки (шрифт, кегль, начертание, выравнивание). Пока образец не задан
(TITLE_PAGE_TEMPLATE_PATH пуст), проверка пропускается с пометкой в отчёте.
"""

import os
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict

from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph

from .docx_utils import Resolver, get_all_runs, iter_blocks

TITLE_PAGE_TEMPLATE_PATH: Optional[str] = None


@dataclass
class ParagraphProfile:
    index: int
    font_name: Optional[str]
    font_size_pt: Optional[float]
    bold: bool
    alignment: Optional[str]
    text_len: int


@dataclass
class TitlePageTemplate:
    paragraphs: List[ParagraphProfile]
    source_path: str

    @classmethod
    def from_docx(cls, path):
        from docx import Document
        return cls(paragraphs=_extract_profile(Document(path)), source_path=path)

    def to_dict(self):
        return {"source_path": self.source_path, "paragraphs": [asdict(p) for p in self.paragraphs]}


_CACHE: Dict[str, tuple] = {}


def load_title_page_template(path):
    if not path:
        return None
    mtime = os.path.getmtime(path)
    cached = _CACHE.get(path)
    if cached and cached[1] == mtime:
        return cached[0]
    template = TitlePageTemplate.from_docx(path)
    _CACHE[path] = (template, mtime)
    return template


def _first_page_paragraphs(doc):
    body = doc.element.body
    first = next((c for c in body if c.tag.split('}')[-1] in ('p', 'tbl')), None)
    if first is not None and first.tag.split('}')[-1] == 'tbl':
        return [Paragraph(p, doc) for p in first.findall('.//' + qn('w:p'))]
    paragraphs = [obj for kind, obj in iter_blocks(doc) if kind == 'p']
    for i, p in enumerate(paragraphs):
        for br in p._p.findall('.//' + qn('w:br')):
            if br.get(qn('w:type')) == 'page':
                return paragraphs[: i + 1]
        if p._p.pPr is not None and p._p.pPr.find(qn('w:sectPr')) is not None:
            return paragraphs[: i + 1]
    return paragraphs[:25]


def _extract_profile(doc):
    res = Resolver(doc)
    out = []
    for i, p in enumerate(_first_page_paragraphs(doc), start=1):
        runs = [r for r in get_all_runs(p) if r.text.strip()]
        name = size = None
        bold = False
        if runs:
            name, size = res.font_name(runs[0], p), res.font_size(runs[0], p)
            bold = bool(res.bold(runs[0], p))
        out.append(ParagraphProfile(i, name, size, bold, res.alignment(p), len(p.text.strip())))
    return out


def check_title_page(doc, template, report):
    if template is None:
        return  # образец не задан — титульный лист не сравнивается
    current, ref = _extract_profile(doc), template.paragraphs
    if len(current) != len(ref):
        report.add("Титульный лист", "Титульный лист",
                   f"количество строк титульного листа ({len(current)}) не совпадает с шаблоном ({len(ref)})")
    for i, (cur, exp) in enumerate(zip(current, ref), start=1):
        if cur.text_len == 0 or exp.text_len == 0:
            continue
        loc = f"Титульный лист, строка {i}"
        if exp.font_name and cur.font_name and cur.font_name != exp.font_name:
            report.add(loc, "Титульный лист", f"шрифт «{cur.font_name}», в шаблоне «{exp.font_name}»")
        if exp.font_size_pt and cur.font_size_pt and abs(cur.font_size_pt - exp.font_size_pt) > 0.5:
            report.add(loc, "Титульный лист", f"кегль {cur.font_size_pt:g} пт, в шаблоне {exp.font_size_pt:g} пт")
        if cur.bold != exp.bold:
            report.add(loc, "Титульный лист",
                       f"начертание {'жирное' if cur.bold else 'обычное'}, в шаблоне {'жирное' if exp.bold else 'обычное'}")
        if exp.alignment and cur.alignment != exp.alignment:
            report.add(loc, "Титульный лист", f"выравнивание «{cur.alignment}», в шаблоне «{exp.alignment}»")
