# -*- coding: utf-8 -*-
"""Проверка .docx на соответствие профилю норм (см. norms.py)."""

import re
from docx import Document
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph

from .docx_utils import (
    Resolver, iter_blocks, get_all_runs, run_in_hyperlink, has_image,
    is_formula, has_page_break, preview, emu_to_cm, build_page_map,
)
from .norms import STRUCTURAL_HEADINGS
from .typography import check_typography

HEADING_STYLE_RE = re.compile(r"^(?:heading|заголовок)\s*(\d+)$", re.IGNORECASE)
TITLE_STYLES = ("title", "название", "subtitle", "подзаголовок")
# Другая гарнитура допустима для терминов, формул и листингов (ГОСТ 7.32-2017, 6.1.1)
ALT_FONTS = {
    "cambria math", "symbol", "mt extra", "euclid math one", "courier new",
    "consolas", "lucida console", "cascadia code", "cascadia mono",
    "jetbrains mono", "fira code", "monaco", "menlo", "source code pro",
}
LIST_MARKERS = re.compile(r"^\s*([-–—•·*▪●○]|\d+[.)]|[а-яa-z]\))\s+", re.IGNORECASE)
BULLET_MARKERS = re.compile(r"^\s*[•·*▪●○]\s*")
TOC_TAIL_RE = re.compile(r"(?:[\t.…]{2,}|\t)\s*\d+\s*$")
STRUCT_APPENDIX_RE = re.compile(r"^ПРИЛОЖЕНИЕ(?:\s+[А-ЯA-Z])?$")
DASHES = "–—-"
FIG_RE = re.compile(r"^\s*(Рис(?:унок)?)(\.?)\s*(\d+(?:\.\d+)?|[А-ЯA-Z]\.\d+)(.*)$", re.IGNORECASE | re.DOTALL)
TAB_RE = re.compile(r"^\s*(Табл(?:ица)?)(\.?)\s*(\d+(?:\.\d+)?|[А-ЯA-Z]\.\d+)(.*)$", re.IGNORECASE | re.DOTALL)
CHAPTER_NUMBER_RE = re.compile(
    r"^(?:(?:РАЗДЕЛ|ГЛАВА)\s+)?(\d+(?:\.\d+)*)(\.)?(?=\s|$)", re.IGNORECASE)
NUMBERED_HEADING_RE = re.compile(r"^\d+(?:\.\d+){0,3}\.?\s+\S")


def _norm_caps(text):
    t = re.sub(r"^\s*\d+(?:\.\d+)*\.?\s+", "", text.strip())  # возможная ручная нумерация
    return t.rstrip(".:").strip().upper()


def _structural_name(text):
    t = _norm_caps(text)
    if not t or len(t) > 60:
        return None
    if t in STRUCTURAL_HEADINGS or STRUCT_APPENDIX_RE.match(t):
        return t
    return None


def _toc_level(p):
    name = (p.style.name if p.style else "").strip().lower()
    m = re.match(r"(?:toc|оглавлени[ея]|содержани[ея])\s*(\d+)", name)
    return int(m.group(1)) if m else None


def _is_toc(p):
    name = (p.style.name if p.style else "").lower()
    if "toc" in name or "оглавлен" in name or "содержан" in name:
        # сам заголовок «СОДЕРЖАНИЕ» может иметь стиль «TOC Heading»
        return _toc_level(p) is not None
    return bool(TOC_TAIL_RE.search(p.text))


def _heading_level(p):
    name = (p.style.name if p.style else "").strip()
    m = HEADING_STYLE_RE.match(name)
    return int(m.group(1)) if m else None


def _fmt(v):
    return f"{v:g}".replace(".", ",")


class DocxChecker:
    def __init__(self, doc, report, profile):
        self.doc, self.report, self.n = doc, report, profile
        self.res = Resolver(doc)

    # ── вспомогательное ──────────────────────────────────────────────────

    def _runs(self, p):
        return [r for r in get_all_runs(p) if r.text.strip()]

    def _loc(self, p, kind="абзац"):
        page, n = self.page_map.get(id(p._p), (None, None))
        base = f"Страница {page}, {kind} {n}" if page else kind.capitalize()
        return f"{base} («{preview(p)}»)"

    def _first_size(self, p, default=14.0):
        for r in self._runs(p):
            s = self.res.font_size(r, p)
            if s:
                return s
        return default

    # ── классификация ────────────────────────────────────────────────────

    def classify(self):
        """Размечает блоки верхнего уровня ролями. Возвращает список записей."""
        blocks = list(iter_blocks(self.doc))
        items = []
        for i, (kind, obj) in enumerate(blocks):
            items.append({"kind": kind, "obj": obj, "role": None, "level": None, "i": i})

        def next_nonempty(idx, step):
            j = idx + step
            while 0 <= j < len(items):
                it = items[j]
                if it["kind"] == "tbl" or items[j]["obj"].text.strip() or has_image(items[j]["obj"]):
                    return it
                j += step
            return None

        for it in items:
            if it["kind"] != "p":
                it["role"] = "table"
                continue
            p = it["obj"]
            text = p.text.strip()
            sname = (p.style.name if p.style else "").strip().lower()

            if is_formula(p):  # текст формулы python-docx не отдаёт — абзац выглядит пустым
                it["role"] = "formula"
                continue
            if not text:
                it["role"] = "image" if has_image(p) else "empty"
                continue
            if sname in TITLE_STYLES:
                it["role"] = "skip"
                continue
            if _is_toc(p):
                it["role"] = "toc"
                continue

            lvl = _heading_level(p)
            struct = _structural_name(text)
            if lvl is not None or struct:
                if struct and (lvl is not None or len(text) < 60):
                    runs = self._runs(p)
                    caps_like = text.upper() == text
                    centered = self.res.alignment(p) == 'center'
                    bold = bool(runs) and all(self.res.bold(r, p) for r in runs)
                    if lvl is not None or caps_like or centered or bold:
                        it["role"], it["level"] = "structural", lvl or 1
                        continue
                if lvl is not None:
                    it["role"], it["level"] = "heading", lvl
                    continue

            if is_formula(p):
                it["role"] = "formula"
                continue

            # подпись к таблице: над таблицей либо в стиле Caption
            m_tab = TAB_RE.match(text)
            m_fig = FIG_RE.match(text)
            is_caption_style = "caption" in sname or sname.startswith("подпись") \
                or "название объекта" in sname
            if m_tab and len(text) < 300:
                nxt = next_nonempty(it["i"], +1)
                if (nxt and nxt["kind"] == "tbl") or is_caption_style:
                    it["role"] = "table_caption"
                    continue
            if m_fig and len(text) < 300:
                prv = next_nonempty(it["i"], -1)
                if (prv and prv["kind"] == "p" and has_image(prv["obj"])) or is_caption_style:
                    it["role"] = "figure_caption"
                    continue

            # заголовок, оформленный вручную (нумерованный, короткий, полностью жирный)
            if len(text) < 120 and NUMBERED_HEADING_RE.match(text) and not text.endswith(("!", "?")):
                runs = self._runs(p)
                if runs and all(self.res.bold(r, p) for r in runs):
                    it["role"], it["level"] = "heading", text.split()[0].rstrip(".").count(".") + 1
                    continue

            if self.res.is_numbered(p) or "list" in sname or LIST_MARKERS.match(text):
                it["role"] = "list"
                continue
            it["role"] = "body"
        return items

    # ── запуск ───────────────────────────────────────────────────────────

    def run(self):
        items = self.classify()
        paragraphs = [it["obj"] for it in items if it["kind"] == "p"]
        self.page_map, self.exact = build_page_map(self.doc, paragraphs)
        self.report.note(
            "Номера страниц в замечаниях взяты из разметки Word и точны." if self.exact else
            "Номера страниц в замечаниях — приблизительная оценка по объёму текста "
            "(файл не содержит разметки Word), реальная разбивка может отличаться."
        )
        self.check_page_setup()
        self.check_page_numbers()
        self.check_body(items)
        self.check_headings(items)
        self.check_toc(items)
        self.check_captions(items)
        self.check_tables(items)
        self.check_structure(items)
        self.check_new_page(items)
        check_typography(
            [(self._loc(it["obj"]), it["obj"].text, it["role"], has_page_break(it["obj"]))
             for it in items if it["kind"] == "p" and it["role"] not in ("toc", "skip")],
            self.report,
        )

    # ── страница ─────────────────────────────────────────────────────────

    def check_page_setup(self):
        n = self.n
        tol = n["margins_tolerance_cm"]
        w0, h0 = n["page_size_cm"]
        for i, s in enumerate(self.doc.sections, start=1):
            loc = f"Раздел документа №{i}"
            try:
                w, h = emu_to_cm(s.page_width), emu_to_cm(s.page_height)
            except Exception:
                w = h = None
            landscape = bool(w and h and w > h)
            if w and h:
                a, b = sorted((w, h))
                ok_a4 = abs(a - w0) <= n["page_size_tolerance_cm"] and abs(b - h0) <= n["page_size_tolerance_cm"]
                ok_a3 = abs(a - 29.7) <= 0.5 and abs(b - 42.0) <= 0.5
                if not (ok_a4 or ok_a3):
                    self.report.add(loc, "Формат листа",
                                    f"размер страницы {_fmt(w)}×{_fmt(h)} см, ожидается A4 (21×29,7 см)")
            if landscape:
                continue  # у альбомных листов поля повёрнуты — не сравниваем
            vals = {"left": emu_to_cm(s.left_margin), "right": emu_to_cm(s.right_margin),
                    "top": emu_to_cm(s.top_margin), "bottom": emu_to_cm(s.bottom_margin)}
            names = {"left": "левое", "right": "правое", "top": "верхнее", "bottom": "нижнее"}
            for side, (lo, hi) in n["margins_cm"].items():
                actual = vals[side]
                if actual is None:
                    continue
                if actual < lo - tol or actual > hi + tol:
                    want = f"{_fmt(lo)} см" if lo == hi else f"от {_fmt(lo)} до {_fmt(hi)} см"
                    self.report.add(loc, "Поля страницы",
                                    f"{names[side]} поле {_fmt(actual)} см, ожидается {want}")

    def check_page_numbers(self):
        if not self.n["check_page_numbers"]:
            return
        found, bad_align = False, None
        for s in self.doc.sections:
            for part, is_footer in ((s.footer, True), (s.header, False)):
                if part is None or part.is_linked_to_previous:
                    continue
                # обходим весь XML колонтитула: Word кладёт номер в <w:sdt>, которого нет в part.paragraphs
                for p_el in part._element.iter(qn('w:p')):
                    xml = p_el.xml
                    if "PAGE" in xml and ("instrText" in xml or "fldSimple" in xml):
                        found = True
                        if is_footer:
                            p = Paragraph(p_el, part)
                            has_tab = "<w:tab/>" in xml
                            if self.res.alignment(p) in ("left", "right", "justify") and not has_tab:
                                bad_align = self.res.alignment(p)
                        else:
                            bad_align = bad_align or "header"
        if not found:
            self.report.add("Документ", "Нумерация страниц",
                            "номера страниц не найдены: нужна нумерация арабскими цифрами "
                            "внизу страницы по центру (Вставка → Номер страницы)")
        elif bad_align == "header":
            self.report.add("Документ", "Нумерация страниц",
                            "номер страницы стоит в верхнем колонтитуле, по ГОСТ 7.32-2017 (п. 6.3.1) — "
                            "внизу страницы по центру")
        elif bad_align:
            ru = {"left": "слева", "right": "справа", "justify": "по ширине"}[bad_align]
            self.report.add("Документ", "Нумерация страниц",
                            f"номер страницы выровнен {ru}, ожидается по центру нижней части страницы")

    # ── основной текст ───────────────────────────────────────────────────

    def _check_runs(self, p, loc, formula, size_floor_only=False):
        n, res = self.n, self.res
        tol = n["font_size_tolerance_pt"]
        for run in self._runs(p):
            if res.script(run, p):
                continue
            fname = res.font_name(run, p)
            if (fname and fname != n["font_name"] and fname.lower() not in ALT_FONTS and not formula):
                self.report.add(loc, "Шрифт", f"использован шрифт «{fname}», ожидается «{n['font_name']}»")
            size = res.font_size(run, p)
            if size is not None and not formula:
                lo, hi = n["font_size_min_pt"] - tol, n["font_size_max_pt"] + tol
                if size_floor_only:
                    lo, hi = n["font_size_floor_pt"] - tol, 999
                if size < lo or size > hi:
                    want = (f"{_fmt(n['font_size_pt'])} пт" if n["font_size_min_pt"] == n["font_size_max_pt"]
                            else f"{_fmt(n['font_size_min_pt'])}–{_fmt(n['font_size_max_pt'])} пт")
                    self.report.add(loc, "Кегль шрифта", f"размер шрифта {_fmt(size)} пт, ожидается {want}")
            if not run_in_hyperlink(run):
                color = res.color(run, p)
                if color and not formula:
                    self.report.add(loc, "Цвет шрифта", f"цвет текста #{color}, ожидается чёрный")

    def _check_spacing(self, p, loc, caption=False):
        n = self.n
        kind, v = self.res.line_spacing(p)
        if has_image(p):
            return
        label = "Подписи к рисункам и таблицам" if caption else "Межстрочный интервал"
        size = self._first_size(p)
        if kind != 'ratio':
            approx = v / (size * n["line_height_factor"])
            if caption:
                return
            if abs(approx - n["line_spacing"]) > 0.15:
                self.report.add(loc, label,
                                f"задан точный/минимальный интервал {_fmt(v)} пт (≈ {_fmt(round(approx, 2))}), "
                                f"ожидается полуторный ({_fmt(n['line_spacing'])})")
            return
        tol = n["line_spacing_tolerance"]
        if caption:
            if v > n["caption_line_spacing_max"] + tol or v < 1.0 - tol:
                self.report.add(loc, label, f"интервал {_fmt(v)}, ожидается от 1 до {_fmt(n['caption_line_spacing_max'])}")
        elif abs(v - n["line_spacing"]) > tol:
            self.report.add(loc, label, f"интервал {_fmt(v)}, ожидается {_fmt(n['line_spacing'])}")

    def check_body(self, items):
        n, res = self.n, self.res
        tol_i = n["first_line_indent_tolerance_cm"]
        prev_formula = False
        for it in items:
            role = it["role"]
            if it["kind"] != "p":
                prev_formula = False
                continue
            p = it["obj"]
            if role == "formula":
                prev_formula = True
                continue
            if role not in ("body", "list", "figure_caption", "table_caption"):
                if role not in ("empty", "image"):
                    prev_formula = False
                continue
            text = p.text.strip()
            loc = self._loc(p)
            caption = role in ("figure_caption", "table_caption")
            self._check_runs(p, loc, False, size_floor_only=caption)
            self._check_spacing(p, loc, caption=caption)

            if role == "list":
                if BULLET_MARKERS.match(p.text):
                    self.report.add(loc, "Перечисления",
                                    "маркер перечисления — не дефис; по ГОСТ 7.32-2017 (п. 6.4.5) "
                                    "перед элементом ставится дефис (тире)")
                prev_formula = False
                continue

            align = res.alignment(p)
            indent = res.first_line_indent_cm(p, self._first_size(p))
            if role == "figure_caption":
                if align != 'center':
                    self.report.add(loc, "Подписи к рисункам и таблицам",
                                    f"подпись к рисунку выровнена {self._ru_align(align)}, ожидается по центру (п. 6.5.7)")
                elif abs(indent) > tol_i:
                    self.report.add(loc, "Подписи к рисункам и таблицам",
                                    "у подписи к рисунку не должно быть абзацного отступа (она центрируется)")
            elif role == "table_caption":
                if align not in ('left', 'justify'):
                    self.report.add(loc, "Подписи к рисункам и таблицам",
                                    f"название таблицы выровнено {self._ru_align(align)}, ожидается слева над таблицей (п. 6.6.3)")
                if abs(indent) > tol_i:
                    self.report.add(loc, "Подписи к рисункам и таблицам",
                                    f"название таблицы с абзацным отступом {_fmt(indent)} см — ожидается без отступа (п. 6.6.3)")
            else:
                continued = prev_formula and re.match(r"^\s*где\b", text, re.IGNORECASE)
                if align != 'justify':
                    self.report.add(loc, "Выравнивание",
                                    f"выравнивание {self._ru_align(align)}, ожидается по ширине")
                if not continued and abs(indent - n["first_line_indent_cm"]) > tol_i:
                    self.report.add(loc, "Красная строка",
                                    f"отступ первой строки {_fmt(indent)} см, ожидается {_fmt(n['first_line_indent_cm'])} см")
            prev_formula = False

    @staticmethod
    def _ru_align(a):
        return {"left": "по левому краю", "right": "по правому краю",
                "center": "по центру", "justify": "по ширине"}.get(a, a)

    # ── заголовки ────────────────────────────────────────────────────────

    def check_headings(self, items):
        n, res = self.n, self.res
        tol = n["font_size_tolerance_pt"]
        for it in items:
            if it["role"] not in ("heading", "structural"):
                continue
            p = it["obj"]
            text = p.text.strip()
            loc = self._loc(p, "заголовок в абзаце")
            runs = self._runs(p)
            structural = it["role"] == "structural"

            if not structural and runs and not all(res.bold(r, p) for r in runs):
                self.report.add(loc, "Оформление заголовка", "заголовок раздела должен быть выделен жирным (п. 6.2.3)")
            if text.endswith("."):
                self.report.add(loc, "Оформление заголовка", "в конце заголовка не должно быть точки")
            if any(res.underline(r, p) for r in runs):
                self.report.add(loc, "Оформление заголовка", "заголовок не должен быть подчёркнут")

            if structural:
                letters = [c for c in text if c.isalpha()]
                if letters and any(c.islower() for c in letters) and not STRUCT_APPENDIX_RE.match(text.upper()):
                    self.report.add(loc, "Оформление заголовка",
                                    "заголовок структурного элемента должен быть ПРОПИСНЫМИ буквами (п. 6.2.1)")
                if res.alignment(p) != 'center':
                    self.report.add(loc, "Оформление заголовка",
                                    "заголовок структурного элемента должен быть расположен по центру (п. 6.2.1)")
            else:
                m = CHAPTER_NUMBER_RE.match(text)
                if m and m.group(2):
                    self.report.add(loc, "Оформление заголовка",
                                    "после номера раздела/подраздела не должно быть точки (п. 6.4.1)")
                if text[:1].islower():
                    self.report.add(loc, "Оформление заголовка", "заголовок должен начинаться с прописной буквы")

            for run in runs:
                fname = res.font_name(run, p)
                if fname and fname != n["font_name"] and fname.lower() not in ALT_FONTS:
                    self.report.add(loc, "Оформление заголовка",
                                    f"шрифт заголовка «{fname}», ожидается «{n['font_name']}»")
                size = res.font_size(run, p)
                if size is not None and (size < n["font_size_min_pt"] - tol or size > n["font_size_max_pt"] + tol):
                    self.report.add(loc, "Оформление заголовка",
                                    f"размер шрифта заголовка {_fmt(size)} пт, ожидается {_fmt(n['font_size_pt'])} пт")
                color = res.color(run, p)
                if color and not run_in_hyperlink(run):
                    self.report.add(loc, "Оформление заголовка", f"цвет заголовка #{color}, ожидается чёрный")

    def check_new_page(self, items):
        """Каждый структурный элемент и раздел 1-го уровня — с новой страницы (п. 6.2.1)."""
        if not self.n["heading_new_page"]:
            return
        res = self.res
        first_seen = False
        for idx, it in enumerate(items):
            if it["kind"] != "p" or it["role"] not in ("heading", "structural"):
                if it["kind"] == "p" and it["role"] not in ("empty", "image", "skip", "toc"):
                    first_seen = True
                continue
            if it["role"] == "heading" and it["level"] != 1:
                first_seen = True
                continue
            p = it["obj"]
            if not first_seen:
                first_seen = True
                continue
            first_seen = True
            if res.page_break_before(p):
                continue
            # Word сам зафиксировал, что абзац оказался первым на странице
            if self.exact and self.page_map.get(id(p._p), (0, 0))[1] == 1:
                continue
            # разрыв страницы/раздела в предыдущих абзацах (пустые пропускаем)
            ok = False
            j = idx - 1
            while j >= 0:
                prev = items[j]
                if prev["kind"] == "tbl":
                    break
                if has_page_break(prev["obj"]):
                    ok = True
                    break
                if prev["role"] not in ("empty", "image"):
                    break
                j -= 1
            if not ok:
                self.report.add(self._loc(p, "заголовок в абзаце"), "Оформление заголовка",
                                "заголовок должен начинаться с новой страницы (п. 6.2.1) — не найден разрыв страницы перед ним")

    # ── оглавление ───────────────────────────────────────────────────────

    def check_toc(self, items):
        """
        Требование вуза (в самом ГОСТ его нет): в оглавлении жирным выделяются
        только заголовки верхнего уровня, пункты и подпункты — обычным.
        """
        res = self.res
        for it in items:
            if it["role"] != "toc":
                continue
            p = it["obj"]
            level = _toc_level(p)
            if level is None:
                continue
            runs = [r for r in self._runs(p) if not re.fullmatch(r"\d+", r.text.strip())]
            if not runs:
                continue
            is_bold = all(res.bold(r, p) for r in runs)
            loc = self._loc(p, "оглавление, абзац")
            if level == 1 and not is_bold:
                self.report.add(loc, "Оформление оглавления",
                                "заголовок раздела в оглавлении должен быть выделен жирным")
            elif level > 1 and is_bold:
                self.report.add(loc, "Оформление оглавления",
                                "пункт оглавления не должен быть жирным (жирным выделяются только заголовки разделов)")

    # ── подписи ──────────────────────────────────────────────────────────

    def check_captions(self, items):
        for role, label, rx, full in (("figure_caption", "Рисунок", FIG_RE, "Рисунок"),
                                       ("table_caption", "Таблица", TAB_RE, "Таблица")):
            expected_next = 1
            for it in items:
                if it["role"] != role:
                    continue
                p = it["obj"]
                text = p.text.strip()
                m = rx.match(text)
                if not m:
                    continue
                loc = self._loc(p)
                word, dot, num, rest = m.groups()
                if word != full or dot:
                    self.report.add(loc, "Подписи к рисункам и таблицам",
                                    f"слово должно быть полностью: «{full} {num}», без сокращения")
                rest_s = rest
                if rest_s.strip():
                    if not re.match(rf"^\s[{DASHES}]\s\S", rest_s):
                        self.report.add(loc, "Подписи к рисункам и таблицам",
                                        f"ожидается формат «{full} {num} – Наименование» "
                                        f"(пробел, тире, пробел между номером и названием)")
                    if text.endswith("."):
                        self.report.add(loc, "Подписи к рисункам и таблицам",
                                        "в конце наименования точка не ставится")
                    name = rest_s.strip().lstrip(DASHES).strip()
                    if name[:1].islower():
                        self.report.add(loc, "Подписи к рисункам и таблицам",
                                        "наименование должно начинаться с прописной буквы")
                if re.fullmatch(r"\d+", num):
                    if int(num) != expected_next:
                        self.report.add(loc, "Нумерация",
                                        f"{full.lower()} {num}: нарушена сквозная нумерация (ожидался №{expected_next})")
                    expected_next = int(num) + 1

    # ── таблицы ──────────────────────────────────────────────────────────

    def check_tables(self, items):
        n, res = self.n, self.res
        ti = 0
        for it in items:
            if it["kind"] != "tbl":
                continue
            ti += 1
            seen_cells = set()
            for ri, row in enumerate(it["obj"].rows, start=1):
                for ci, cell in enumerate(row.cells, start=1):
                    if id(cell._tc) in seen_cells:  # объединённые ячейки повторяются в row.cells
                        continue
                    seen_cells.add(id(cell._tc))
                    for p in cell.paragraphs:
                        for run in self._runs(p):
                            fname = res.font_name(run, p)
                            if (fname and fname != n["font_name"] and fname.lower() not in ALT_FONTS):
                                self.report.add(f"Таблица №{ti}, строка {ri}, столбец {ci}", "Шрифт (таблица)",
                                                f"использован шрифт «{fname}», ожидается «{n['font_name']}»")
                                break

    # ── структура ────────────────────────────────────────────────────────

    def check_structure(self, items):
        present = set()
        for it in items:
            if it["role"] in ("structural", "heading") and it["kind"] == "p":
                present.add(_norm_caps(it["obj"].text))
        total_text = sum(len(it["obj"].text) for it in items if it["kind"] == "p")
        if total_text < 1500:
            return  # слишком короткий фрагмент, обязательные разделы не ожидаются
        for title, variants in self.n["required_sections"]:
            if not any(v in present for v in variants):
                self.report.add("Структура работы", "Структура",
                                f"не найден структурный элемент «{title}» "
                                f"(или он оформлен не как заголовок)")


def check_docx(doc_or_path, report, profile):
    doc = Document(doc_or_path) if isinstance(doc_or_path, (str, bytes)) or hasattr(doc_or_path, "__fspath__") \
        else doc_or_path
    DocxChecker(doc, report, profile).run()
    return doc
