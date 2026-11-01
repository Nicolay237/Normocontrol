# -*- coding: utf-8 -*-
"""
Оформление научной статьи по правилам журнала «Интеллектуальные технологии на транспорте»
(ПГУПС): поля, шрифты и абзацы по шаблону редакции, заголовочная часть (УДК, название,
авторы, «Для цитирования», аннотация, ключевые слова, шифр специальности), разделы,
таблицы, рисунки, список источников и английский блок.

Части статьи распознаются по ключевым словам и порядку. Что нельзя исправить автоматически
(объём аннотации, число ключевых слов и источников, ссылки, английский блок) — в списке
замечаний для автора.

Функция не продаётся: доступна только тем, кому её открыл администратор (users.article_access).
"""

import copy
import re
from collections import Counter
from dataclasses import dataclass, field

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt
from docx.text.paragraph import Paragraph

from .docx_utils import get_all_runs, has_image, is_formula, iter_blocks
from .fixers import _set_black, _set_font_name, _set_font_size

JOURNAL = "Интеллектуальные технологии на транспорте"

# шаблон редакции: поля и размеры шрифтов
MARGINS_CM = {"left": 1.29, "right": 1.29, "top": 1.9, "bottom": 2.5}
HEAD_PT, TITLE_PT, BODY_PT, TABLE_PT, REFS_PT = 12, 24, 14, 11, 12
INDENT_CM = 0.5

J, L, C, R = WD_ALIGN_PARAGRAPH.JUSTIFY, WD_ALIGN_PARAGRAPH.LEFT, WD_ALIGN_PARAGRAPH.CENTER, WD_ALIGN_PARAGRAPH.RIGHT

UDC_RE = re.compile(r"^\s*УДК\b\s*(.*)$")
CITE_RU_RE = re.compile(r"^\s*Для\s+цитирования\s*:", re.I)
ABSTRACT_RU_RE = re.compile(r"^\s*Аннотация\s*[.:]?", re.I)
KEYWORDS_RU_RE = re.compile(r"^\s*Ключевые\s+слова\s*[:.]?", re.I)
THANKS_RE = re.compile(r"^\s*Благодарност[ьи]\s*[.:]?", re.I)
SPECIALTY_RE = re.compile(r"^\s*(\d\.\d\.\d{1,2}\.?)\s*[—–-]")
AUTHOR_RU_RE = re.compile(r"^\s*[А-ЯЁ][а-яё-]+\s+(?:[А-ЯЁ][а-яё-]+\s+[А-ЯЁ][а-яё-]+|[А-ЯЁ]\.\s?[А-ЯЁ]\.)\s*[—–-]\s")
REFS_HEAD_RE = re.compile(r"^\s*(список\s+(использованных\s+|используемых\s+)?(источников|литературы)|литература|"
                          r"библиографический\s+список)\s*:?\s*$", re.I)
DATES_RU_RE = re.compile(r"^\s*(Дата\s+поступления|Решение\s+о\s+публикации)\b", re.I)
CITE_EN_RE = re.compile(r"^\s*For\s+citation\s*:", re.I)
ABSTRACT_EN_RE = re.compile(r"^\s*Abstract\s*[.:]?", re.I)
KEYWORDS_EN_RE = re.compile(r"^\s*Key\s*words\s*[:.]?", re.I)
REFS_EN_RE = re.compile(r"^\s*references\s*:?\s*$", re.I)
DATES_EN_RE = re.compile(r"^\s*(Received|Accepted)\s*:", re.I)
AUTHOR_EN_HINT = re.compile(r"Research\s+interests|E-?mail", re.I)
TABLE_RE = re.compile(r"^\s*Табл(?:ица|\.)\s*(\d+(?:\.\d+)?)\s*(?:[.:–—-]\s*(.*))?$", re.I | re.S)
FIGURE_RE = re.compile(r"^\s*Рис(?:унок|\.)?\s*(\d+(?:\.\d+)?)\s*[.:–—-]?\s*(.*)$", re.I | re.S)
LIST_MARK_RE = re.compile(r"^(\s*)[-–—•·*▪●]\s+")
NUM_PREFIX_RE = re.compile(r"^\s*\[?\d+[.)\]]\s*")
CITATION_RE = re.compile(r"\[(\d+(?:\s*[,;–—-]\s*\d+)*)(?:\s*,\s*[сcСpP]\.[^\]]*)?\]")
# диапазон «15-20», «181-189.» → через тире; «7.0.5-2008» (номер стандарта) не трогаем
RANGE_RE = re.compile(r"(?<![\d.,\w])(\d+)-(\d+)(?![\d\w]|[.,]\d)")
DECIMAL_DOT_RE = re.compile(r"(?<![\d.\w])\d+\.\d+(?![\d.\w])")
SECTION_WORDS = {"введение", "заключение"}


@dataclass
class ArticleResult:
    done: Counter = field(default_factory=Counter)      # что сделано: описание → сколько
    warnings: list = field(default_factory=list)       # что проверить и исправить автору

    def to_dict(self):
        return {"done": [{"name": k, "count": v} for k, v in self.done.items()],
                "warnings": self.warnings}


# ── низкоуровневое ────────────────────────────────────────────────────────

def _text(p):
    return p.text.strip()


def _new_paragraph_after(p, text=""):
    el = OxmlElement("w:p")
    ppr = p._p.find(qn("w:pPr"))
    if ppr is not None:
        el.append(copy.deepcopy(ppr))
    p._p.addnext(el)
    np_ = Paragraph(el, p._parent)
    if text:
        np_.add_run(text)
    return np_


def _new_paragraph_before(p):
    el = OxmlElement("w:p")
    p._p.addprevious(el)
    return Paragraph(el, p._parent)


def _gap_before(p):
    """Пустая строка перед абзацем, если её там нет — как в шаблоне между блоками."""
    prev = p._p.getprevious()
    if prev is not None and prev.tag == qn("w:p") and Paragraph(prev, p._parent).text.strip():
        _new_paragraph_before(p)
        return True
    return False


def _para(p, align, indent=0.0, spacing=1.0, before=0, after=0):
    pf = p.paragraph_format
    pf.alignment = align
    pf.left_indent = Cm(0)
    pf.right_indent = Cm(0)
    pf.first_line_indent = Cm(indent)
    if spacing == 1.0:
        pf.line_spacing_rule = WD_LINE_SPACING.SINGLE
    else:
        pf.line_spacing = spacing
    pf.space_before = Pt(before)
    pf.space_after = Pt(after)


def _runs(p, size, bold=None, italic=None, small_caps=None):
    for r in get_all_runs(p):
        _set_font_name(r)
        _set_font_size(r, size)
        _set_black(r)
        r.font.highlight_color = None
        if bold is not None:
            r.font.bold = bold
        if italic is not None:
            r.font.italic = italic
        if small_caps is not None:
            r.font.small_caps = small_caps


def _split_run_at(run, k):
    """Делит run на два по k-му символу; возвращает правую часть."""
    right = copy.deepcopy(run._r)
    run._r.addnext(right)
    t_left, t_right = run._r.findall(qn("w:t")), right.findall(qn("w:t"))
    text = run.text
    for t in t_left[1:]:
        t.getparent().remove(t)
    for t in t_right[1:]:
        t.getparent().remove(t)
    t_left[0].text, t_right[0].text = text[:k], text[k:]
    for t in (t_left[0], t_right[0]):
        t.set(qn("xml:space"), "preserve")
    from docx.text.run import Run
    return Run(right, run._parent)


def _style_prefix(p, n, bold=True, italic=None, rest_bold=None, rest_italic=None):
    """Первые n символов абзаца — bold/italic, остальное — rest_* (None: как было)."""
    pos = 0
    for r in get_all_runs(p):
        t = r.text
        if not t:
            continue
        if pos < n < pos + len(t) and len(r._r.findall(qn("w:t"))) >= 1:
            right = _split_run_at(r, n - pos)
            r.font.bold, right.font.bold = bold, rest_bold if rest_bold is not None else right.font.bold
            if italic is not None:
                r.font.italic = italic
            if rest_italic is not None:
                right.font.italic = rest_italic
            pos += len(t)
            continue
        if pos + len(t) <= n:
            r.font.bold = bold
            if italic is not None:
                r.font.italic = italic
        else:
            if rest_bold is not None:
                r.font.bold = rest_bold
            if rest_italic is not None:
                r.font.italic = rest_italic
        pos += len(t)


def _t_nodes(p):
    return [t for t in p._p.iter(qn("w:t"))]


def _replace_text(p, fn):
    """Применяет fn к тексту каждого w:t; возвращает число изменённых узлов."""
    n = 0
    for t in _t_nodes(p):
        old = t.text or ""
        new = fn(old)
        if new != old:
            t.text = new
            t.set(qn("xml:space"), "preserve")
            n += 1
    return n


def _set_text(p, text):
    """Текст абзаца целиком в первом run (оформление первого run сохраняется)."""
    runs = get_all_runs(p)
    if not runs:
        p.add_run(text)
        return
    ts = [t for t in _t_nodes(p)]
    ts[0].text = text
    ts[0].set(qn("xml:space"), "preserve")
    for t in ts[1:]:
        t.text = ""


def _strip_end(p, chars="."):
    ts = [t for t in _t_nodes(p) if (t.text or "").strip()]
    if ts and ts[-1].text.rstrip().endswith(tuple(chars)):
        ts[-1].text = ts[-1].text.rstrip().rstrip(chars)
        return True
    return False


def _latin_share(s):
    letters = [ch for ch in s if ch.isalpha()]
    return sum("a" <= ch.lower() <= "z" for ch in letters) / len(letters) if letters else 0


def _is_heading_style(p):
    name = (p.style.name if p.style is not None else "").lower()
    return name.startswith(("heading", "заголовок"))


def _all_bold(p):
    runs = [r for r in get_all_runs(p) if r.text.strip()]
    return bool(runs) and all(r.bold or (r.style is not None and r.style.font.bold) or
                              (p.style is not None and p.style.font.bold and r.bold is not False) for r in runs)


def _numbered(p):
    ppr = p._p.find(qn("w:pPr"))
    return ppr is not None and ppr.find(qn("w:numPr")) is not None


# ── типографика ───────────────────────────────────────────────────────────

def _typography(p, stats):
    """Кавычки «ёлочки», тире между словами и в диапазонах, ё → е (кроме слов с прописной)."""
    state = {"open": True}

    def quotes(s):
        s2 = s.replace("“", "«").replace("”", "»").replace("„", "«")
        out = []
        for ch in s2:
            if ch == '"':
                out.append("«" if state["open"] else "»")
                state["open"] = not state["open"]
            else:
                out.append(ch)
        return "".join(out)

    def fix(s):
        s1 = quotes(s)
        if s1 != s:
            stats["quotes"] += 1
        s2 = re.sub(r"(?<=\S) [-—] (?=\S)", " – ", s1)
        s2 = RANGE_RE.sub(r"\1–\2", s2)
        if s2 != s1:
            stats["dash"] += 1
        s3 = re.sub(r"(?<![А-ЯЁа-яё])[а-яё][а-яё-]*", lambda m: m.group(0).replace("ё", "е"), s2)
        if s3 != s2:
            stats["yo"] += 1
        return s3

    _replace_text(p, fix)


# ── распознавание и оформление ────────────────────────────────────────────

class ArticleFormatter:
    def __init__(self, doc):
        self.doc = doc
        self.res = ArticleResult()
        self.typo = Counter()
        self.found = Counter()
        self.body_text = []          # абзацы основного текста — для проверки ссылок и десятичных точек
        self.refs = []               # записи списка источников
        self.abstract_ru = None
        self.keywords_ru = None
        self.tables = 0
        self.table_labels = 0
        self.gaps = 0

    # -- страница и стили
    def page(self):
        for s in self.doc.sections:
            s.page_width, s.page_height = Cm(21.0), Cm(29.7)
            s.left_margin, s.right_margin = Cm(MARGINS_CM["left"]), Cm(MARGINS_CM["right"])
            s.top_margin, s.bottom_margin = Cm(MARGINS_CM["top"]), Cm(MARGINS_CM["bottom"])
            s.header_distance = s.footer_distance = Cm(1.27)
        normal = self.doc.styles["Normal"]
        normal.font.name = "Times New Roman"
        normal.font.size = Pt(BODY_PT)
        rpr = normal.element.get_or_add_rPr()
        rf = rpr.find(qn("w:rFonts"))
        if rf is None:
            rf = OxmlElement("w:rFonts")
            rpr.insert(0, rf)
        for a in list(rf.attrib):
            del rf.attrib[a]
        for a in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
            rf.set(qn(a), "Times New Roman")
        self.res.done["Поля страницы и формат A4 — по шаблону редакции"] += 1

    # -- основной проход
    def run(self):
        self.page()
        blocks = list(iter_blocks(self.doc))
        zone = "head"
        head_seen = Counter()
        prev_head = None             # роль предыдущего непустого абзаца шапки
        en_prev = None
        pending_table_title = False
        for kind, obj in blocks:
            if kind == "tbl":
                self.table(obj)
                pending_table_title = False
                continue
            p = obj
            text = _text(p)
            if not text and not has_image(p) and not is_formula(p):
                continue

            # переходы между частями статьи
            if zone in ("head", "body") and REFS_HEAD_RE.match(text):
                self.refs_heading(p)
                zone = "refs"
                continue
            if zone in ("refs", "body") and DATES_RU_RE.match(text):
                self.plain(p, HEAD_PT, L)
                self.found["dates_ru"] += 1
                zone = "dates"
                continue
            if zone in ("refs", "dates") and _latin_share(text) > 0.6 and not DATES_RU_RE.match(text):
                if zone == "refs" and not (REFS_EN_RE.match(text) or CITE_EN_RE.match(text)) and \
                        (re.match(r"^\s*\d", text) or "//" in text or "URL" in text):
                    pass   # иноязычный источник в русском списке
                else:
                    zone = "en"
            if zone == "en_refs" and DATES_EN_RE.match(text):
                self.plain(p, HEAD_PT, J)
                continue

            if zone == "head":
                role = self.head_role(p, text, head_seen, prev_head)
                if role == "body":
                    zone = "body"
                else:
                    head_seen[role] += 1
                    # блоки шапки разделены пустой строкой; подряд идут только авторы одной
                    # организации и строки её адреса
                    if prev_head and not (role == prev_head and role in ("author", "affiliation")):
                        self.gaps += _gap_before(p)
                    self.head(p, role, text)
                    prev_head = role
                    continue

            if zone == "body":
                pending_table_title = self.body(p, text, pending_table_title)
            elif zone == "refs":
                self.ref_entry(p, text)
            elif zone == "dates":
                self.plain(p, HEAD_PT, L)
            elif zone == "en":
                if REFS_EN_RE.match(text):
                    _set_text(p, "REFERENCES")
                    self.plain(p, REFS_PT, J, before=6)
                    _runs(p, REFS_PT, bold=False)
                    self.found["refs_en"] += 1
                    zone = "en_refs"
                    continue
                en_prev = self.english(p, text, en_prev)
            elif zone == "en_refs":
                self.plain(p, REFS_PT, J, indent=INDENT_CM)

        self.spacing()
        self.summary(head_seen)
        return self.res

    # -- шапка
    def head_role(self, p, text, seen, prev):
        if UDC_RE.match(text):
            return "udc"
        if CITE_RU_RE.match(text):
            return "citation"
        if ABSTRACT_RU_RE.match(text):
            return "abstract"
        if KEYWORDS_RU_RE.match(text):
            return "keywords"
        if THANKS_RE.match(text):
            return "thanks"
        if SPECIALTY_RE.match(text):
            return "specialty"
        if text.lower().rstrip(".") in SECTION_WORDS or _is_heading_style(p):
            return "body"
        after_abstract = seen["abstract"] or seen["keywords"] or seen["specialty"]
        if after_abstract:
            return "body"
        if not seen["title"]:
            return "title"
        if AUTHOR_RU_RE.match(text) or re.search(r"Научные\s+интересы|E-?mail", text, re.I):
            return "author"
        if seen["citation"]:
            return "body"
        return "affiliation"

    def head(self, p, role, text):
        self.found[role] += 1
        if role == "udc":
            m = UDC_RE.match(text)
            _set_text(p, f"УДК {m.group(1).strip()}".rstrip())
            self.plain(p, HEAD_PT, L, bold=False)
        elif role == "title":
            _strip_end(p)
            self.plain(p, TITLE_PT, J, bold=True)
        elif role == "author":
            _typography(p, self.typo)
            _replace_text(p, lambda s: re.sub(r"(?<=\S) [–-] (?=\S)", " — ", s, count=1))
            self.plain(p, HEAD_PT, J, bold=False)
            m = re.search(r"\s[—–-]\s", p.text)
            if m:
                _style_prefix(p, m.start(), bold=True, rest_bold=False)
            if re.search(r"E-?mail\s*:?\s*\S+@\S+\.$", p.text, re.I):
                _strip_end(p)
        elif role == "affiliation":
            self.plain(p, HEAD_PT, J, bold=False)
        elif role == "citation":
            self.plain(p, HEAD_PT, J, bold=False)
            _style_prefix(p, len("Для цитирования:"), bold=True, rest_bold=False)
        elif role == "abstract":
            _typography(p, self.typo)
            self.plain(p, HEAD_PT, J)
            m = ABSTRACT_RU_RE.match(p.text)
            _style_prefix(p, m.end(), bold=True)
            self.abstract_ru = p.text[m.end():].strip()
        elif role == "keywords":
            _strip_end(p, ".;")
            self.plain(p, HEAD_PT, J)
            m = KEYWORDS_RU_RE.match(p.text)
            _style_prefix(p, m.end(), bold=True, rest_bold=False)
            self.keywords_ru = p.text[m.end():].strip()
        elif role == "thanks":
            self.plain(p, HEAD_PT, J)
            m = THANKS_RE.match(p.text)
            _style_prefix(p, m.end(), bold=True)
        elif role == "specialty":
            _strip_end(p, ".;")
            self.plain(p, HEAD_PT, J, bold=False, italic=True)
            m = SPECIALTY_RE.match(p.text)
            _style_prefix(p, len(m.group(1)) + (len(p.text) - len(p.text.lstrip())), bold=True, italic=True,
                          rest_bold=False, rest_italic=True)

    def plain(self, p, size, align, indent=0.0, bold=None, italic=None, before=0, after=0, spacing=1.0):
        _para(p, align, indent, spacing=spacing, before=before, after=after)
        _runs(p, size, bold=bold, italic=italic)

    # -- основной текст
    def body(self, p, text, pending_table_title):
        if has_image(p) and not text:
            _para(p, C, 0)
            self.found["image"] += 1
            return pending_table_title
        if is_formula(p):
            _runs(p, BODY_PT)
            self.found["formula"] += 1
            return pending_table_title

        m_tab = TABLE_RE.match(text)
        if m_tab and len(text) < 300:
            num, title = m_tab.group(1), (m_tab.group(2) or "").strip()
            _set_text(p, f"Таблица {num}")
            self.plain(p, BODY_PT, R, bold=False, italic=True)
            self.table_labels += 1
            if title:
                t = _new_paragraph_after(p, title)
                self.table_title(t)
                return False
            return True
        if pending_table_title:
            self.table_title(p)
            return False

        m_fig = FIGURE_RE.match(text)
        if m_fig and len(text) < 300 and (m_fig.group(2) or not text.lower().startswith("рисунок")):
            num, title = m_fig.group(1), m_fig.group(2).strip().rstrip(".").strip()
            label = f"Рис. {num}."
            _set_text(p, f"{label} {title}".strip())
            self.plain(p, BODY_PT, C, bold=False, italic=False, before=6, after=6)
            _style_prefix(p, len(label), bold=False, italic=True, rest_bold=False, rest_italic=False)
            self.found["figure"] += 1
            return False

        if self.is_heading(p, text):
            self.gaps += _gap_before(p)
            _strip_end(p)
            self.plain(p, BODY_PT, J, bold=True, italic=False, spacing=0.9)
            for r in get_all_runs(p):
                r.font.small_caps = True
            self.found["heading"] += 1
            return False

        _typography(p, self.typo)
        if LIST_MARK_RE.match(p.text):
            ts = [t for t in _t_nodes(p) if t.text]
            if ts:
                ts[0].text = LIST_MARK_RE.sub(r"\1– ", ts[0].text, count=1).lstrip()
            self.found["list"] += 1
        self.plain(p, BODY_PT, J, indent=INDENT_CM)
        self.found["body"] += 1
        self.body_text.append(p.text)
        return False

    def is_heading(self, p, text):
        if len(text) > 150 or text.startswith(("Таблица", "Рис")) or "[" in text:
            return False
        if text.lower().rstrip(".") in SECTION_WORDS:
            return True
        if _is_heading_style(p):
            return True
        if text.endswith((".", ":", ";", ",")) and not re.match(r"^\d+(\.\d+)*\.\s", text):
            return False
        return _all_bold(p) and len(text.split()) <= 20

    def table_title(self, p):
        _strip_end(p)
        self.plain(p, BODY_PT, C, bold=False, italic=False)

    def table(self, t):
        self.tables += 1
        for row in t.rows:
            for cell in row.cells:
                for cp in cell.paragraphs:
                    pf = cp.paragraph_format
                    pf.first_line_indent = Cm(0)
                    pf.line_spacing_rule = WD_LINE_SPACING.SINGLE
                    pf.space_before = pf.space_after = Pt(0)
                    _runs(cp, TABLE_PT)

    # -- список источников
    def refs_heading(self, p):
        self.gaps += _gap_before(p)
        _set_text(p, "СПИСОК ИСТОЧНИКОВ")
        self.plain(p, REFS_PT, L, indent=INDENT_CM, bold=False, spacing=0.9)
        self.found["refs_heading"] += 1

    def ref_entry(self, p, text):
        _replace_text(p, lambda s: RANGE_RE.sub(r"\1–\2", s))
        if not NUM_PREFIX_RE.match(text) and not _numbered(p):
            ts = [t for t in _t_nodes(p) if t.text]
            if ts:
                ts[0].text = f"{len(self.refs) + 1}. " + ts[0].text.lstrip()
                self.res.done["Источники пронумерованы"] += 1
        self.plain(p, REFS_PT, J, indent=INDENT_CM)
        self.refs.append(text)

    # -- английский блок
    def english(self, p, text, prev):
        if CITE_EN_RE.match(text):
            self.plain(p, HEAD_PT, J, bold=False)
            self.found["cite_en"] += 1
            return "citation"
        if ABSTRACT_EN_RE.match(text):
            self.plain(p, HEAD_PT, J)
            _style_prefix(p, ABSTRACT_EN_RE.match(p.text).end(), bold=True)
            self.found["abstract_en"] += 1
            return "abstract"
        if KEYWORDS_EN_RE.match(text):
            _strip_end(p, ".;")
            self.plain(p, HEAD_PT, J)
            _style_prefix(p, KEYWORDS_EN_RE.match(p.text).end(), bold=True, rest_bold=False)
            self.found["keywords_en"] += 1
            return "keywords"
        if prev is None:
            _strip_end(p)
            self.plain(p, TITLE_PT, J, bold=True)
            self.found["title_en"] += 1
            return "title"
        if AUTHOR_EN_HINT.search(text):
            self.plain(p, HEAD_PT, J, bold=False)
            m = re.search(r"\s[—–-]\s", p.text)
            if m:
                _style_prefix(p, m.start(), bold=True, rest_bold=False)
            self.found["author_en"] += 1
            return "author"
        self.plain(p, HEAD_PT, J, bold=False)
        return "affiliation"

    # -- пустые строки: по одной между блоками шапки и перед разделами, лишние убираем
    def spacing(self):
        body = self.doc.element.body
        prev_empty = False
        for el in list(body):
            if el.tag != qn("w:p"):
                prev_empty = False
                continue
            p = Paragraph(el, self.doc)
            empty = not _text(p) and not has_image(p) and not is_formula(p) and \
                not p._p.xpath(".//w:br[@w:type='page'] | .//w:sectPr")
            if empty and prev_empty:
                body.remove(el)
                self.res.done["Удалены лишние пустые строки"] += 1
                continue
            prev_empty = empty

    # -- итоги и замечания
    def summary(self, head_seen):
        d, f, w = self.res.done, self.found, self.res.warnings
        d["Шрифт Times New Roman во всей статье"] += 1
        names = [
            ("udc", "УДК"), ("title", "Название статьи — 24 пт, полужирный"),
            ("author", "Сведения об авторах — ФИО полужирным"), ("affiliation", "Сведения об организациях"),
            ("citation", "«Для цитирования»"), ("abstract", "Аннотация — 12 пт, интервал 1,0"),
            ("keywords", "Ключевые слова"), ("specialty", "Шифр научной специальности — курсивом"),
            ("heading", "Заголовки разделов — 14 пт, полужирные малые прописные"),
            ("body", "Абзацы текста — 14 пт, отступ 0,5 см, интервал 1,0, по ширине"),
            ("list", "Перечисления — через тире"),
            ("figure", "Подписи к рисункам — «Рис. N. Название» по центру"),
            ("refs_heading", "Заголовок «СПИСОК ИСТОЧНИКОВ»"),
            ("title_en", "Английское название"), ("author_en", "Сведения об авторах на английском"),
            ("abstract_en", "Abstract"), ("keywords_en", "Keywords"), ("refs_en", "REFERENCES"),
        ]
        for key, label in names:
            if f[key]:
                d[label] += f[key]
        if self.gaps:
            d["Пустые строки между блоками — как в шаблоне"] += self.gaps
        if self.tables:
            d["Таблицы — текст 11 пт"] += self.tables
        if self.table_labels:
            d["Подписи «Таблица N» справа курсивом, название по центру"] += self.table_labels
        if self.refs:
            d["Список источников — 12 пт, отступ 0,5 см"] += len(self.refs)
        if self.typo["quotes"]:
            d["Кавычки заменены на «ёлочки»"] += self.typo["quotes"]
        if self.typo["dash"]:
            d["Дефисы заменены на тире"] += self.typo["dash"]
        if self.typo["yo"]:
            d["Буква «ё» заменена на «е» (кроме слов с прописной — фамилий)"] += self.typo["yo"]

        # чего не хватает
        for key, label in (("udc", "УДК (подберите на teacode.com/online/udc)"), ("title", "название статьи"),
                           ("author", "сведения об авторах (ФИО — степень, звание, должность, научные "
                                      "интересы, E-mail)"),
                           ("citation", "строка «Для цитирования: …»"), ("abstract", "аннотация"),
                           ("keywords", "ключевые слова"),
                           ("specialty", "шифр научной специальности (1–2 шифра из списка редакции)")):
            if not f[key]:
                w.append(f"Не найдено: {label}.")
        if self.abstract_ru is not None and not 800 <= len(self.abstract_ru) <= 1200:
            w.append(f"Объём аннотации {len(self.abstract_ru)} знаков с пробелами — нужно 800–1200.")
        if self.keywords_ru is not None:
            kw = [k for k in re.split(r"[;,]", self.keywords_ru) if k.strip()]
            if not 7 <= len(kw) <= 10:
                w.append(f"Ключевых слов {len(kw)} — нужно 7–10.")
        headings = f["heading"]
        if headings and headings - 2 < 2:
            w.append("Разделов (кроме введения и заключения) меньше двух — так требует редакция.")
        if not f["heading"]:
            w.append("Не найдены заголовки разделов: сделайте их отдельными строками полужирным "
                     "или стилем «Заголовок».")
        if not f["refs_heading"]:
            w.append("Не найден список источников (заголовок «СПИСОК ИСТОЧНИКОВ»).")
        elif not 15 <= len(self.refs) <= 30:
            w.append(f"Источников {len(self.refs)} — редакция рекомендует 15–30.")
        self.check_citations(w)
        decimals = [m.group(0) for t in self.body_text for m in DECIMAL_DOT_RE.finditer(t)]
        if decimals:
            w.append("Десятичные дроби набираются через запятую: " + ", ".join(sorted(set(decimals))[:6])
                     + (" и др." if len(set(decimals)) > 6 else "") + " (проверьте, что это не номера версий).")
        if not (f["title_en"] and f["abstract_en"] and f["keywords_en"] and f["refs_en"]):
            miss = [n for k, n in (("title_en", "название"), ("author_en", "сведения об авторах"),
                                   ("abstract_en", "Abstract"), ("keywords_en", "Keywords"),
                                   ("refs_en", "REFERENCES")) if not f[k]]
            w.append("Английский блок неполный — не найдено: " + ", ".join(miss) + ".")
        if self.tables > self.table_labels:
            w.append(f"Таблиц {self.tables}, а подписей «Таблица N» — {self.table_labels}: "
                     "над каждой таблицей нужна подпись и название.")
        if not f["dates_ru"]:
            w.append("Нет строк «Дата поступления» и «Решение о публикации» после списка источников "
                     "(даты ставит редакция — оставьте 00.00.2025).")

    def check_citations(self, w):
        if not self.refs:
            return
        order, cited = [], set()
        for t in self.body_text:
            for m in CITATION_RE.finditer(t):
                for part in re.split(r"\s*[,;]\s*", m.group(1)):
                    rng = re.split(r"\s*[–—-]\s*", part)
                    nums = range(int(rng[0]), int(rng[-1]) + 1) if len(rng) == 2 and rng[0].isdigit() \
                        and rng[-1].isdigit() and int(rng[-1]) - int(rng[0]) < 50 else [int(x) for x in rng if x.isdigit()]
                    for k in nums:
                        if k not in cited:
                            cited.add(k)
                            order.append(k)
        n = len(self.refs)
        missing = [k for k in range(1, n + 1) if k not in cited]
        if missing:
            w.append("На источники нет ссылок в тексте: " + ", ".join(f"[{k}]" for k in missing[:10])
                     + (" и др." if len(missing) > 10 else "") + " — в список включают только цитируемые.")
        extra = sorted(k for k in cited if k > n)
        if extra:
            w.append("Ссылки на несуществующие источники: " + ", ".join(f"[{k}]" for k in extra[:10]) + ".")
        bad = next((k for i, k in enumerate(order) if k != i + 1 and k <= n), None)
        if bad and not missing:
            w.append(f"Источники должны идти в порядке цитирования: [{bad}] упоминается раньше, чем ожидалось.")


def format_article(src_path, dst_path):
    doc = Document(src_path)
    result = ArticleFormatter(doc).run()
    doc.save(dst_path)
    return result
