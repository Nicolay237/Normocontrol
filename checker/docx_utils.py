# -*- coding: utf-8 -*-
"""
Разбор .docx: обход абзацев и вычисление ФАКТИЧЕСКОГО форматирования
(прямое форматирование → стиль символа → стиль абзаца и его родители →
docDefaults), как это делает Word. Это главный источник ложных срабатываний
в наивных проверках: python-docx возвращает None, когда значение взято из
стиля, и по None нельзя судить о нарушении.
"""

import re
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph
from docx.text.run import Run
from docx.table import Table

MATH_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"
TWIPS_TO_CM = 2.54 / 1440.0
HALF_PT = 0.5


# ── обход тела документа ──────────────────────────────────────────────────

def iter_blocks(document):
    """
    Блоки верхнего уровня по порядку: ('p', Paragraph) или ('tbl', Table).
    Заходит в content control (<w:sdt>) — так Word оборачивает оглавление.
    """
    def walk(parent):
        for child in parent:
            tag = child.tag.split('}')[-1]
            if tag == 'p':
                yield 'p', Paragraph(child, document)
            elif tag == 'tbl':
                yield 'tbl', Table(child, document)
            elif tag == 'sdt':
                content = child.find(qn('w:sdtContent'))
                if content is not None:
                    yield from walk(content)

    yield from walk(document.element.body)


def get_all_runs(paragraph):
    """Все runs абзаца, включая лежащие внутри <w:hyperlink>."""
    return [Run(r, paragraph) for r in paragraph._p.findall('.//' + qn('w:r'))]


def run_in_hyperlink(run):
    parent = run._r.getparent()
    return parent is not None and parent.tag == qn('w:hyperlink')


def emu_to_cm(v):
    return None if v is None else round(v / 360000.0, 3)


def preview(p, n=60):
    t = p.text.strip()
    return t[:n] + "..." if len(t) > n else (t or "(пустой абзац)")


def has_image(p):
    return bool(p._p.xpath('.//w:drawing | .//w:pict | .//w:object'))


def is_formula(p):
    return p._p.find(f".//{MATH_NS}oMath") is not None


def has_page_break(p):
    for br in p._p.findall('.//' + qn('w:br')):
        if br.get(qn('w:type')) == 'page':
            return True
    ppr = p._p.pPr
    return ppr is not None and ppr.find(qn('w:sectPr')) is not None


def starts_with_page_break(p):
    """Разрыв страницы стоит внутри самого абзаца до его первого текста."""
    for el in p._p.iter(qn('w:br'), qn('w:t')):
        if el.tag == qn('w:br'):
            if el.get(qn('w:type')) == 'page':
                return True
        elif el.text:
            return False
    return False


# ── цепочки стилей ────────────────────────────────────────────────────────

def style_chain(style):
    seen = set()
    while style is not None and id(style.element) not in seen:
        seen.add(id(style.element))
        yield style
        style = style.base_style


def para_style(p):
    """
    Стиль абзаца с кешем по id стиля. p.style в python-docx при каждом вызове
    заново ищет стиль по умолчанию среди всех стилей — на большой работе это
    десятки тысяч обходов и основная часть времени проверки.
    """
    cache = p.part.__dict__.setdefault('_nc_pstyle', {})
    ppr = p._p.pPr
    sid = ppr.pStyle.val if ppr is not None and ppr.pStyle is not None else None
    if sid not in cache:
        cache[sid] = p.style
    return cache[sid]


def run_style(run):
    """Стиль символа run'а (или None) с кешем по id стиля."""
    rpr = run._r.rPr
    if rpr is None or rpr.rStyle is None:
        return None
    sid = rpr.rStyle.val
    cache = run.part.__dict__.setdefault('_nc_rstyle', {})
    if sid not in cache:
        cache[sid] = run.style
    return cache[sid]


def style_name(p):
    st = para_style(p)
    return st.name if st is not None else ""


def _on(el):
    """Булево свойство <w:b/>, <w:u/>…: отсутствие w:val = включено."""
    if el is None:
        return None
    v = el.get(qn('w:val'))
    return v not in ('0', 'false', 'off', 'none')


class Resolver:
    """Вычисляет фактические свойства абзацев и run'ов с кешем по документу."""

    def __init__(self, doc):
        self.doc = doc
        styles_el = doc.styles.element
        dd = styles_el.find(qn('w:docDefaults'))
        self._ppr_default = None
        self._rpr_default = None
        if dd is not None:
            self._ppr_default = dd.find(qn('w:pPrDefault') + '/' + qn('w:pPr'))
            self._rpr_default = dd.find(qn('w:rPrDefault') + '/' + qn('w:rPr'))
        self._theme = None
        self._cache = {}

    # -- темы шрифтов
    def _theme_fonts(self):
        if self._theme is None:
            self._theme = {}
            try:
                from lxml import etree
                for part in self.doc.part.package.iter_parts():
                    if str(part.partname).startswith('/word/theme/'):
                        root = etree.fromstring(part.blob)
                        ns = {'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'}
                        for kind in ('major', 'minor'):
                            lat = root.find(f'.//a:{kind}Font/a:latin', ns)
                            if lat is not None:
                                self._theme[kind] = lat.get('typeface')
                        break
            except Exception:
                pass
        return self._theme

    # -- уровни наследования
    def _para_levels(self, p):
        """pPr: прямое → стили абзаца (с родителями) → docDefaults."""
        return [l for l in [p._p.pPr] + self._chain(para_style(p), 'pPr') + [self._ppr_default]
                if l is not None]

    def _chain(self, style, kind):
        """pPr/rPr стиля и его родителей (кешируется по стилю)."""
        if style is None:
            return []
        key = (style.style_id, style.type, kind)
        if key not in self._cache:
            self._cache[key] = [getattr(s.element, kind) for s in style_chain(style)]
        return self._cache[key]

    def _run_levels(self, run, p):
        """rPr: прямое → стиль символа → стили абзаца → docDefaults."""
        levels = [run._r.rPr] + self._chain(run_style(run), 'rPr')             + self._chain(para_style(p), 'rPr') + [self._rpr_default]
        return [l for l in levels if l is not None]

    # -- свойства run'а
    def font_name(self, run, p):
        for rpr in self._run_levels(run, p):
            f = rpr.find(qn('w:rFonts'))
            if f is None:
                continue
            name = f.get(qn('w:ascii')) or f.get(qn('w:hAnsi'))
            if name:
                return name
            theme = f.get(qn('w:asciiTheme')) or f.get(qn('w:hAnsiTheme'))
            if theme:
                kind = 'major' if theme.startswith('major') else 'minor'
                return self._theme_fonts().get(kind)
        return None

    def font_size(self, run, p):
        for rpr in self._run_levels(run, p):
            sz = rpr.find(qn('w:sz'))
            if sz is not None and sz.get(qn('w:val')):
                return int(sz.get(qn('w:val'))) * HALF_PT
        return None

    def bold(self, run, p):
        for rpr in self._run_levels(run, p):
            b = rpr.find(qn('w:b'))
            if b is not None:
                return _on(b)
        return False

    def underline(self, run, p):
        for rpr in self._run_levels(run, p):
            u = rpr.find(qn('w:u'))
            if u is not None:
                return u.get(qn('w:val')) not in ('none', '0', 'false')
        return False

    def script(self, run, p):
        """'superscript' / 'subscript' / None — такие run'ы мельче по определению."""
        for rpr in self._run_levels(run, p):
            va = rpr.find(qn('w:vertAlign'))
            if va is not None:
                v = va.get(qn('w:val'))
                return v if v in ('superscript', 'subscript') else None
        return None

    def color(self, run, p):
        """Цвет шрифта hex ('000000') либо None, если авто/чёрный/тема текста."""
        for rpr in self._run_levels(run, p):
            c = rpr.find(qn('w:color'))
            if c is None:
                continue
            val = (c.get(qn('w:val')) or '').upper()
            theme = c.get(qn('w:themeColor'))
            if theme in ('text1', 'dark1'):
                return None
            if val in ('', 'AUTO', '000000'):
                return None
            return val
        return None

    # -- свойства абзаца
    def _para_attr(self, p, tag, attr):
        for ppr in self._para_levels(p):
            el = ppr.find(qn(tag))
            if el is not None and el.get(qn(attr)) is not None:
                return el.get(qn(attr))
        return None

    def line_spacing(self, p):
        """
        ('ratio', 1.5) — множитель; ('exact'|'atLeast', pt) — фиксированная
        высота строки. Если нигде не задано — Word использует одинарный (1.0).
        """
        line = self._para_attr(p, 'w:spacing', 'w:line')
        if line is None:
            return 'ratio', 1.0
        rule = self._para_attr(p, 'w:spacing', 'w:lineRule') or 'auto'
        v = int(line)
        if rule == 'auto':
            return 'ratio', round(v / 240.0, 3)
        return rule, round(v / 20.0, 1)

    def alignment(self, p):
        """'justify' | 'left' | 'center' | 'right'."""
        jc = self._para_attr(p, 'w:jc', 'w:val')
        return {
            'both': 'justify', 'distribute': 'justify', 'thaiDistribute': 'justify',
            'center': 'center', 'right': 'right', 'end': 'right',
        }.get(jc, 'left')

    def first_line_indent_cm(self, p, font_size_pt=14.0):
        for ppr in self._para_levels(p):
            ind = ppr.find(qn('w:ind'))
            if ind is None:
                continue
            fl = ind.get(qn('w:firstLine'))
            hg = ind.get(qn('w:hanging'))
            flc = ind.get(qn('w:firstLineChars'))
            hgc = ind.get(qn('w:hangingChars'))
            if fl is not None:
                return round(int(fl) * TWIPS_TO_CM, 3)
            if hg is not None:
                return round(-int(hg) * TWIPS_TO_CM, 3)
            if flc is not None:
                return round(int(flc) / 100.0 * font_size_pt * 2.54 / 72, 3)
            if hgc is not None:
                return round(-int(hgc) / 100.0 * font_size_pt * 2.54 / 72, 3)
        return 0.0

    def page_break_before(self, p):
        for ppr in self._para_levels(p):
            el = ppr.find(qn('w:pageBreakBefore'))
            if el is not None:
                return _on(el)
        return False

    def is_numbered(self, p):
        """Абзац входит в автоматический список (нумерация/маркеры Word)."""
        for ppr in self._para_levels(p):
            num = ppr.find(qn('w:numPr'))
            if num is not None:
                nid = num.find(qn('w:numId'))
                return nid is not None and nid.get(qn('w:val')) != '0'
        return False


# ── постраничная привязка ─────────────────────────────────────────────────

def build_page_map(doc, paragraphs):
    """
    {id(p._p): (страница, номер абзаца на странице)}.

    Word сохраняет в файле <w:lastRenderedPageBreak/> в местах, где реально
    произошёл перенос страницы при последнем сохранении — по ним номера
    страниц ТОЧНЫЕ. Если таких отметок нет (файл создан не Word'ом), делается
    грубая оценка по объёму текста. Возвращает (карта, is_exact).
    """
    body = doc.element.body
    lrpb = qn('w:lastRenderedPageBreak')
    wp = qn('w:p')
    target = {id(p._p): p for p in paragraphs}

    has_marks = body.find('.//' + lrpb) is not None
    mapping = {}
    if has_marks:
        page, per_page = 1, {}
        for el in body.iter(wp, lrpb):
            if el.tag == lrpb:
                page += 1
                continue
            if id(el) in target:
                # отметка до первого текста абзаца — абзац начинает новую страницу
                first_text = el.find('.//' + qn('w:t'))
                first_mark = el.find('.//' + lrpb)
                starts_new = (
                    first_mark is not None
                    and (first_text is None or _doc_before(first_mark, first_text, el))
                )
                pg = page + (1 if starts_new else 0)
                per_page[pg] = per_page.get(pg, 0) + 1
                mapping[id(el)] = (pg, per_page[pg])
        return mapping, True

    return _estimate_pagination(doc, paragraphs), False


def _doc_before(a, b, root):
    for el in root.iter():
        if el is a:
            return True
        if el is b:
            return False
    return False


def _estimate_pagination(doc, paragraphs):
    import math
    sec = doc.sections[0]
    try:
        content_w = sec.page_width.pt - sec.left_margin.pt - sec.right_margin.pt
        content_h = sec.page_height.pt - sec.top_margin.pt - sec.bottom_margin.pt
    except Exception:
        content_w, content_h = 453.0, 700.0
    res = Resolver(doc)
    mapping, page, used = {}, 1, 0.0
    per_page = {}
    for p in paragraphs:
        size = 14.0
        for r in get_all_runs(p):
            s = res.font_size(r, p)
            if s:
                size = s
                break
        kind, v = res.line_spacing(p)
        spacing = v if kind == 'ratio' else 1.5
        line_h = size * 1.15 * spacing
        cpl = max(1, content_w / (size * 0.5))
        lpp = max(1, content_h / line_h)
        n_lines = max(1, math.ceil(len(p.text.strip()) / cpl)) if p.text.strip() else 1
        if has_page_break(p) or res.page_break_before(p):
            if used > 0:
                page, used = page + 1, 0.0
        if used > 0 and used + n_lines > lpp:
            page, used = page + 1, 0.0
        used += n_lines
        per_page[page] = per_page.get(page, 0) + 1
        mapping[id(p._p)] = (page, per_page[page])
    return mapping
