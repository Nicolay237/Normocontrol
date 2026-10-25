# -*- coding: utf-8 -*-
"""Проверка .docx на соответствие профилю норм (см. norms.py)."""

import re
from docx import Document
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph

from .docx_utils import (
    Resolver, iter_blocks, get_all_runs, run_in_hyperlink, has_image,
    is_formula, has_page_break, starts_with_page_break, preview, style_name, emu_to_cm, build_page_map,
)
from .norms import STRUCTURAL_HEADINGS
from .typography import check_typography
from .bibliography import check_bibliography, find_section as find_bib_section

HEADING_STYLE_RE = re.compile(r"^(?:heading|заголовок)\s*(\d+)$", re.IGNORECASE)
TITLE_STYLES = ("title", "название", "subtitle", "подзаголовок")
# Другая гарнитура допустима для терминов, формул и листингов (ГОСТ 7.32-2017, 6.1.1)
ALT_FONTS = {
    "cambria math", "symbol", "mt extra", "euclid math one", "courier new",
    "consolas", "lucida console", "cascadia code", "cascadia mono",
    "jetbrains mono", "fira code", "monaco", "menlo", "source code pro",
}
# Моноширинные шрифты — признак программного кода
MONO_FONTS = {
    "courier new", "courier", "consolas", "lucida console", "lucida sans typewriter", "cascadia code",
    "cascadia mono", "jetbrains mono", "fira code", "fira mono", "monaco", "menlo", "source code pro",
    "dejavu sans mono", "liberation mono", "pt mono", "roboto mono", "ubuntu mono", "inconsolata",
    "noto sans mono", "sf mono",
}
CODE_STYLE_RE = re.compile(r"code|listing|листинг|preformatted|исходн|программ|\bкод", re.IGNORECASE)
# «– Название» после номера подписи: так подпись отличается от фразы «Таблица 1 показывает…»
DASH_REST_RE = re.compile(r"^\s*[–—-]\s*\S")
LISTING_RE = re.compile(r"^\s*(Листинг)(\.?)\s*(\d+(?:\.\d+)?|[А-ЯA-Z]\.\d+)(.*)$", re.IGNORECASE | re.DOTALL)
# строка кода, набранная обычным шрифтом: ключевое слово в начале или много «программных» символов
CODE_KEYWORD_RE = re.compile(
    r"^\s*(def|class|import|from|return|elif|else|try|except|finally|with|lambda|async|await|"
    r"public|private|protected|static|void|int|float|double|char|bool|boolean|string|var|let|const|"
    r"function|using|namespace|#include|#define|package|func|fn|struct|enum|interface|new|"
    r"SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER|FROM|WHERE|print|printf|cout|cin|console\.|System\.|"
    r"if\s*\(|for\s*\(|while\s*\(|switch\s*\(|catch\s*\(|if\s+.+:$|for\s+.+\s+in\s+.+:$|while\s+.+:$)",
)
CODE_CHARS = set("{}();=<>[]+*&|!")
# библиографические записи и ссылки на сайты — не код, даже если в них много скобок и знаков
NOT_CODE_RE = re.compile(r"https?://|www\.|URL\s*:|\s//\s|дата обращения", re.IGNORECASE)
LIST_MARKERS = re.compile(r"^\s*([-–—•·*▪●○]|\d+[.)]|[а-яa-z]\))\s+", re.IGNORECASE)
BULLET_MARKERS = re.compile(r"^\s*[•·*▪●○]\s*")
TOC_TAIL_RE = re.compile(r"(?:[\t.…]{2,}|\t)\s*\d+\s*$")
STRUCT_APPENDIX_RE = re.compile(r"^ПРИЛОЖЕНИЕ(?:\s+[А-ЯA-Z])?$")
DASHES = "–—-"
FIG_RE = re.compile(r"^\s*(Рис(?:унок)?)(\.?)\s*(\d+(?:\.\d+)?|[А-ЯA-Z]\.\d+)(.*)$", re.IGNORECASE | re.DOTALL)
TAB_RE = re.compile(r"^\s*(Табл(?:ица)?)(\.?)\s*(\d+(?:\.\d+)?|[А-ЯA-Z]\.\d+)(.*)$", re.IGNORECASE | re.DOTALL)
CHAPTER_NUMBER_RE = re.compile(
    r"^(?:(?:РАЗДЕЛ|ГЛАВА)\s+)?(\d+(?:\.\d+)*)(\.)?(?=\s|$)", re.IGNORECASE)
HEADING_NUMBER_PREFIX_RE = re.compile(r"^\s*(?:(?:РАЗДЕЛ|ГЛАВА)\s+)?\d+(?:\.\d+)*\.?\s*", re.IGNORECASE)
NUMBERED_HEADING_RE = re.compile(r"^\d+(?:\.\d+){0,3}\.?\s+\S")


# Точка после сокращения (руб., гг., т.д.) — часть слова, а не точка предложения
ABBREVIATIONS = {
    "руб", "коп", "тыс", "млн", "млрд", "трлн", "гг", "г", "др", "пр", "д", "п", "см", "мм", "м",
    "км", "кг", "шт", "чел", "ч", "мин", "сек", "с", "т", "кв", "куб", "гр", "рис", "табл", "стр",
}


def ends_with_sentence_dot(text):
    """Заканчивается точкой предложения, а не точкой сокращения («тыс. руб.»)."""
    t = text.rstrip()
    if not t.endswith(".") or t.endswith(".."):
        return False
    m = re.search(r"([^\W\d_]+)\.$", t)
    return not (m and m.group(1).lower() in ABBREVIATIONS)


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
    name = style_name(p).strip().lower()
    m = re.match(r"(?:toc|оглавлени[ея]|содержани[ея])\s*(\d+)", name)
    return int(m.group(1)) if m else None


def _is_toc(p, text=None):
    name = style_name(p).lower()
    if "toc" in name or "оглавлен" in name or "содержан" in name:
        # сам заголовок «СОДЕРЖАНИЕ» может иметь стиль «TOC Heading»
        return _toc_level(p) is not None
    return bool(TOC_TAIL_RE.search(p.text if text is None else text))


def _heading_level(p):
    name = style_name(p).strip()
    m = HEADING_STYLE_RE.match(name)
    return int(m.group(1)) if m else None


def _fmt(v):
    return f"{v:g}".replace(".", ",")


def strip_gost732_refs(msg):
    """«… (п. 6.2.1)», «(ГОСТ 7.32-2017, п. 6.16)», «по ГОСТ 7.32-2017 (п. 6.3.1) — » → без ссылок на 7.32."""
    msg = re.sub(r"\s*\((?:ГОСТ 7\.32-2017,\s*)?пп?\.\s*[\d.,\s–-]+\)", "", msg)
    msg = re.sub(r",?\s*по ГОСТ 7\.32-2017\s*(?:\(п\.\s*[\d.]+\))?\s*", " ", msg)
    return re.sub(r"\s{2,}", " ", msg).strip()


def mark_front_matter(items):
    """
    Титульный лист, задание и прочее до первого структурного элемента (АННОТАЦИЯ, РЕФЕРАТ,
    СОДЕРЖАНИЕ, ВВЕДЕНИЕ…) оформляются по своим формам: центрированные строки, мелкий кегль,
    пустые строки для подписей. Правила основного текста к ним не применяются — помечаем
    такие блоки ролью "front" (исходная роль остаётся в "front_role").
    """
    first = next((k for k, it in enumerate(items) if it["role"] == "structural"), None)
    if not first:
        return
    # если перед первым найденным структурным элементом уже идут разделы или сплошной текст,
    # значит, ВВЕДЕНИЕ и др. просто не распознаны — это не титульный лист
    before = items[:first]
    if any(it["role"] == "heading" for it in before):
        return
    if sum(1 for it in before if it["role"] == "body" and len(it["obj"].text) > 400) > 2:
        return
    for it in items[:first]:
        it["front_role"], it["role"] = it["role"], "front"


class DocxChecker:
    def __init__(self, doc, report, profile, packs=()):
        self.doc, self.report, self.n = doc, report, profile
        self.packs = packs   # дополнительные проверки вуза: [(ключ, настройки JSON)]
        self.res = Resolver(doc)
        # p.text / run.text в python-docx каждый раз выполняют xpath — на ВКР это тысячи
        # вызовов и основная часть времени. Документ при проверке не меняется, кешируем.
        self._text = {}
        self._runs_cache = {}

    # ── вспомогательное ──────────────────────────────────────────────────

    def font_ok(self, fname):
        allowed = self.n.get("font_names") or [self.n["font_name"]]
        return not fname or fname in allowed or fname.lower() in ALT_FONTS

    @property
    def font_want(self):
        return " или ".join(f"«{f}»" for f in (self.n.get("font_names") or [self.n["font_name"]]))

    def text(self, p):
        key = id(p._p)
        if key not in self._text:
            self._text[key] = p.text
        return self._text[key]

    def _runs(self, p):
        key = id(p._p)
        if key not in self._runs_cache:
            self._runs_cache[key] = [r for r in get_all_runs(p) if r.text.strip()]
        return self._runs_cache[key]

    def _loc(self, p, kind="абзац"):
        page, n = self.page_map.get(id(p._p), (None, None))
        base = f"Страница {page}, {kind} {n}" if page else kind.capitalize()
        loc = f"{base} («{preview(p, text=self.text(p))}»)"
        idx = self._block_idx.get(id(p._p))
        if idx is not None:
            self._anchors[loc] = ("p", idx)
        return loc

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
                if it["kind"] == "tbl" or self.text(items[j]["obj"]).strip() or has_image(items[j]["obj"]):
                    return it
                j += step
            return None

        for it in items:
            if it["kind"] != "p":
                it["role"] = "table"
                continue
            p = it["obj"]
            text = self.text(p).strip()
            sname = style_name(p).strip().lower()

            if is_formula(p):  # текст формулы python-docx не отдаёт — абзац выглядит пустым
                it["role"] = "formula"
                continue
            if not text:
                it["role"] = "image" if has_image(p) else "empty"
                continue
            if sname in TITLE_STYLES:
                it["role"] = "skip"
                continue
            if _is_toc(p, self.text(p)):
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
                if DASH_REST_RE.match(m_tab.group(4)):
                    # «Таблица 1.1 – Название», а таблицы под ним нет: она над названием (название
                    # не на своём месте), удалена или не вставлена; таблица картинкой — всё-таки таблица
                    prv = next_nonempty(it["i"], -1)
                    it["role"] = "table_caption"
                    if prv and prv["kind"] == "tbl":
                        it["misplaced"] = True
                    else:
                        it["orphan"] = not (nxt and nxt["kind"] == "p" and has_image(nxt["obj"]))
                    continue
            if m_fig and len(text) < 300:
                prv = next_nonempty(it["i"], -1)
                if (prv and prv["kind"] == "p" and has_image(prv["obj"])) or is_caption_style:
                    it["role"] = "figure_caption"
                    continue
                if DASH_REST_RE.match(m_fig.group(4)):
                    # «Рисунок 2 – Название» без рисунка над ним; рисунок, привязанный к соседнему
                    # абзацу или стоящий в таблице, ищем на три блока выше
                    it["role"] = "figure_caption"
                    nxt = next_nonempty(it["i"], +1)
                    if nxt and nxt["kind"] == "p" and has_image(nxt["obj"]):
                        it["misplaced"] = True     # подпись над рисунком
                    else:
                        it["orphan"] = not any(b["kind"] == "tbl" or has_image(b["obj"])
                                               for b in items[max(0, it["i"] - 3):it["i"]])
                    continue

            if LISTING_RE.match(text) and len(text) < 300:
                it["role"] = "listing_caption"
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
        self.mark_code(items)
        self.mark_appendix_titles(items)
        mark_front_matter(items)
        return items

    # ── программный код ──────────────────────────────────────────────────

    def _mono(self, p):
        """Абзац набран моноширинным шрифтом (не меньше 80% символов)."""
        total = mono = 0
        for r in self._runs(p):
            n = len(r.text.strip())
            total += n
            if (self.res.font_name(r, p) or "").lower() in MONO_FONTS:
                mono += n
        return total > 0 and mono >= 0.8 * total

    @staticmethod
    def _code_like(text):
        t = text.strip()
        if not t or len(t) > 220 or NOT_CODE_RE.search(t):
            return False
        if CODE_KEYWORD_RE.match(t) or re.fullmatch(r"[{}()\[\];,]+", t):   # «{», «}», «});»
            return True
        symbols = sum(1 for ch in t if ch in CODE_CHARS)
        cyr = sum(1 for ch in t if "а" <= ch.lower() <= "я")
        letters = sum(1 for ch in t if ch.isalpha()) or 1
        return symbols >= 2 and cyr / letters < 0.3 and (t.endswith((";", "{", "}", ")", ":")) or symbols >= 4)

    def mark_code(self, items):
        """
        Листинги программ: абзацы моноширинным шрифтом или в стиле «код», а также подряд идущие
        строки, похожие на код (≥ 3), получают роль "code" — к ним не применяются правила
        основного текста. it["code_font"] — набран ли код моноширинным шрифтом.
        """
        textual = ("body", "list", "empty")
        for it in items:
            if it["kind"] == "p" and it["role"] in textual and it["role"] != "empty":
                p = it["obj"]
                if self._mono(p) or CODE_STYLE_RE.search(style_name(p) or ""):
                    it["role"], it["code_font"] = "code", True
        # код обычным шрифтом: не меньше трёх похожих на код строк подряд (пустые строки внутри — можно)
        i = 0
        while i < len(items):
            j, lines = i, 0
            while j < len(items) and items[j]["kind"] == "p" and items[j]["role"] in textual:
                text = self.text(items[j]["obj"])
                if text.strip():
                    if not self._code_like(text):
                        break
                    lines += 1
                j += 1
            if lines >= 3:
                for it in items[i:j]:
                    if it["role"] != "empty" or (i < it["i"] < j - 1):
                        it["role"], it["code_font"] = "code", False
                i = j
            else:
                i += 1
        # пустые строки внутри листинга — часть кода, а не «лишние пустые абзацы»
        for k in range(1, len(items) - 1):
            if items[k]["role"] == "empty":
                prev = next((x for x in reversed(items[:k]) if x["role"] != "empty"), None)
                nxt = next((x for x in items[k + 1:] if x["role"] != "empty"), None)
                if prev and nxt and prev["role"] == "code" and nxt["role"] == "code":
                    items[k]["role"], items[k]["code_font"] = "code", prev.get("code_font", True)
        # многие методички разрешают подписывать код как рисунок: «Рисунок N – …» под листингом
        for block in self.code_blocks(items):
            k = block[-1]["i"] + 1
            while k < len(items) and items[k]["role"] == "empty":
                k += 1
            if k < len(items) and items[k]["role"] in ("body", "figure_caption") \
                    and FIG_RE.match(self.text(items[k]["obj"]).strip())                     and len(self.text(items[k]["obj"])) < 300:
                items[k]["role"], items[k]["orphan"] = "figure_caption", False

    def code_blocks(self, items):
        """Листинги: списки подряд идущих элементов с ролью "code"."""
        blocks, cur = [], []
        for it in items:
            if it["role"] == "code":
                cur.append(it)
            elif cur:
                blocks.append(cur)
                cur = []
        if cur:
            blocks.append(cur)
        return blocks

    def check_code(self, items):
        """
        Требования методичек к листингам (в ГОСТ 7.32 отдельного пункта нет): моноширинный шрифт
        10–12 пт, интервал не больше полуторного, выравнивание по левому краю, подпись
        «Листинг N – Название» над кодом; длинный код — в приложение.
        """
        res, cat = self.res, "Листинги"
        appendix_from = next((it["i"] for it in items if it["role"] == "structural"
                              and self.text(it["obj"]).strip().upper().startswith("ПРИЛОЖЕНИ")), None)
        for block in self.code_blocks(items):
            lines = [it for it in block if self.text(it["obj"]).strip()]
            if not lines:
                continue
            first = lines[0]["obj"]
            loc = self._loc(first, "листинг, абзац")
            in_appendix = appendix_from is not None and block[0]["i"] > appendix_from
            if not any(it.get("code_font") for it in lines):
                fonts = {res.font_name(r, first) for r in self._runs(first)} - {None}
                self.report.add(loc, cat, "похоже на программный код, набранный шрифтом "
                                          f"«{', '.join(sorted(fonts)) or 'основного текста'}» — для листингов "
                                          "используют моноширинный шрифт (Courier New, Consolas)")
            sizes = {res.font_size(r, it["obj"]) for it in lines for r in self._runs(it["obj"])} - {None}
            if sizes and (min(sizes) < 9.5 or max(sizes) > 14.5):
                self.report.add(loc, cat, f"кегль листинга {_fmt(min(sizes) if min(sizes) < 9.5 else max(sizes))} пт "
                                          "— обычно 10–12 пт")
            if any(res.alignment(it["obj"]) in ("justify", "center") for it in lines):
                self.report.add(loc, cat, "листинг выравнивается по левому краю, а не по ширине или центру")
            if any(res.first_line_indent_cm(it["obj"], 12) > self.n["first_line_indent_tolerance_cm"] for it in lines):
                self.report.add(loc, cat, "у строк листинга не должно быть абзацного отступа — "
                                          "вложенность в коде показывают пробелами")
            spacing = [res.line_spacing(it["obj"]) for it in lines]
            if any(kind == "ratio" and v > 1.5 + self.n["line_spacing_tolerance"] for kind, v in spacing):
                self.report.add(loc, cat, "межстрочный интервал листинга — одинарный (допускается полуторный)")
            # подпись: ближайший непустой абзац над кодом
            k = block[0]["i"] - 1
            while k >= 0 and items[k]["role"] == "empty":
                k -= 1
            has_caption = k >= 0 and items[k]["role"] == "listing_caption"
            k = block[-1]["i"] + 1
            while k < len(items) and items[k]["role"] == "empty":
                k += 1
            caption_below = k < len(items) and items[k]["role"] == "listing_caption"
            figure_below = k < len(items) and items[k]["role"] == "figure_caption"
            if caption_below and not has_caption:
                self.report.add(self._loc(items[k]["obj"]), cat, "подпись «Листинг N – Название» ставится над кодом, а не под ним")
            elif not (has_caption or figure_below) and len(lines) >= 3 and not in_appendix:
                self.report.add(loc, cat, "у листинга нет подписи: «Листинг N – Название» над кодом "
                                          "(или «Рисунок N – Название» под ним, если так требует методичка)")
            if len(lines) >= 60 and not in_appendix:
                self.report.add(loc, cat, f"длинный листинг ({len(lines)} строк) лучше вынести в приложение, "
                                          "а в тексте оставить ключевой фрагмент")

    # ── запуск ───────────────────────────────────────────────────────────

    def prepare(self):
        """Классификация блоков и карта страниц; возвращает items (используется и исправителем)."""
        items = self.classify()
        paragraphs = [it["obj"] for it in items if it["kind"] == "p"]
        self.page_map, self.exact = build_page_map(self.doc, paragraphs)
        self._block_idx = {id(it["obj"]._element): it["i"] for it in items}
        self._anchors = {}   # текст места → место в документе (для отметок в файле)
        return items

    def run(self):
        items = self.prepare()
        layout = self.n["check_layout"]
        if layout:
            self.check_page_setup()
            self.check_page_numbers()
            self.check_body(items)
            self.check_headings(items)
            self.check_appendix_titles(items)
            self.check_toc(items)
            self.check_captions(items)
            self.check_code(items)
            self.check_tables(items)
            self.check_structure(items)
            self.check_new_page(items)
        check_bibliography(self, items)
        if self.packs:
            from .packs import run_packs
            run_packs(self, items, self.packs)
        if layout:
            # записи списка источников: по ГОСТ Р 7.0.100 в них « : », « / », « ; » — с пробелами
            bib_ids = {id(p._p) for p in find_bib_section(self, items)[1]}
            check_typography(
                [(self._loc(it["obj"]), self.text(it["obj"]),
                  "bib" if id(it["obj"]._p) in bib_ids else it["role"], has_page_break(it["obj"]))
                 for it in items if it["kind"] == "p" and it["role"] not in ("toc", "skip", "front", "code")],
                self.report,
            )
        for issue in self.report.issues:
            issue.anchor = self._anchors.get(issue.location)
            m = re.match(r"Раздел документа №(\d+)", issue.location)
            if issue.anchor is None and m:
                issue.anchor = ("section", int(m.group(1)) - 1)
        if self.report.issues:  # заметка о точности номеров страниц нужна, только если есть замечания
            self.report.note(
                "Номера страниц в замечаниях взяты из разметки Word и точны." if self.exact else
                "Номера страниц в замечаниях — приблизительная оценка по объёму текста "
                "(файл не содержит разметки Word), реальная разбивка может отличаться."
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
            if landscape or not n["check_margins"]:
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

    @staticmethod
    def _page_paragraphs(part):
        """Абзацы колонтитула с полем PAGE (обходим весь XML: Word кладёт номер в <w:sdt>)."""
        return [p_el for p_el in part._element.iter(qn('w:p'))
                if "PAGE" in p_el.xml and ("instrText" in p_el.xml or "fldSimple" in p_el.xml)]

    def check_page_numbers(self):
        if not self.n["check_page_numbers"]:
            return
        bad_align = None
        footer_has, header_has = [], []
        prev_f = prev_h = False
        for s in self.doc.sections:
            # связанный с предыдущим колонтитул наследует его содержимое (и номер)
            f_has = prev_f if s.footer.is_linked_to_previous else bool(self._page_paragraphs(s.footer))
            h_has = prev_h if s.header.is_linked_to_previous else bool(self._page_paragraphs(s.header))
            footer_has.append(f_has)
            header_has.append(h_has)
            prev_f, prev_h = f_has, h_has
            if not s.footer.is_linked_to_previous:
                for p_el in self._page_paragraphs(s.footer):
                    al = self.res.alignment(Paragraph(p_el, s.footer))
                    if al in ("left", "right", "justify") and "<w:tab/>" not in p_el.xml:
                        bad_align = al

        pos = self.n["page_number_pos"]
        where = {"bottom": "внизу страницы по центру", "top": "вверху страницы по центру",
                 "any": "сквозная, арабскими цифрами"}[pos]
        if not any(footer_has) and not any(header_has):
            self.report.add("Документ", "Нумерация страниц",
                            f"номера страниц не найдены: нужна нумерация арабскими цифрами, {where} "
                            "(Вставка → Номер страницы)")
            return
        if pos == "bottom" and not any(footer_has):
            self.report.add("Документ", "Нумерация страниц",
                            "номер страницы стоит в верхнем колонтитуле, по ГОСТ 7.32-2017 (п. 6.3.1) — "
                            "внизу страницы по центру")
            return
        if pos == "top" and not any(header_has):
            self.report.add("Документ", "Нумерация страниц",
                            "номер страницы стоит внизу, а печатается на середине верхнего поля страницы")
            return
        if pos == "top":
            return   # выравнивание проверяем только у номера внизу
        for i, (f_has, h_has) in enumerate(zip(footer_has, header_has), start=1):
            if not f_has and not h_has:
                orient = " (альбомные листы)" if self.doc.sections[i - 1].page_width > self.doc.sections[i - 1].page_height else ""
                self.report.add(f"Раздел документа №{i}{orient}", "Нумерация страниц",
                                "на страницах этого раздела нет номеров — нумерация должна быть сквозной "
                                "по всей работе (п. 6.3.1)")
        if bad_align:
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
            if not self.font_ok(fname) and not formula:
                self.report.add(loc, "Шрифт", f"использован шрифт «{fname}», ожидается {self.font_want}")
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
            text = self.text(p).strip()
            loc = self._loc(p)
            caption = role in ("figure_caption", "table_caption")
            self._check_runs(p, loc, False, size_floor_only=caption)
            self._check_spacing(p, loc, caption=caption)

            if role == "list":
                if BULLET_MARKERS.match(self.text(p)):
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
                if align not in n["body_align"]:
                    want = " или ".join({"justify": "по ширине", "left": "по левому краю"}[a] for a in n["body_align"])
                    self.report.add(loc, "Выравнивание",
                                    f"выравнивание {self._ru_align(align)}, ожидается {want}")
                if not continued and abs(indent - n["first_line_indent_cm"]) > tol_i:
                    self.report.add(loc, "Красная строка",
                                    f"отступ первой строки {_fmt(indent)} см, ожидается {_fmt(n['first_line_indent_cm'])} см")
            prev_formula = False

    @staticmethod
    def _ru_align(a):
        return {"left": "по левому краю", "right": "по правому краю",
                "center": "по центру", "justify": "по ширине"}.get(a, a)

    # ── заголовки ────────────────────────────────────────────────────────

    def mark_appendix_titles(self, items):
        """
        Под «ПРИЛОЖЕНИЕ А» — заголовок приложения: по центру, с прописной, полужирным, без точки
        (ГОСТ 7.32-2017, раздел 6.17). Это не абзац основного текста — роль "appendix_title".
        """
        for k, it in enumerate(items):
            if it["role"] != "structural" or not self.text(it["obj"]).strip().upper().startswith("ПРИЛОЖЕНИ"):
                continue
            j = k + 1
            while j < len(items) and items[j]["role"] == "empty":
                j += 1
            if j < len(items) and items[j]["role"] == "body" and len(self.text(items[j]["obj"]).strip()) < 200:
                items[j]["role"] = "appendix_title"

    def check_appendix_titles(self, items):
        res = self.res
        for it in items:
            if it["role"] != "appendix_title":
                continue
            p = it["obj"]
            text = self.text(p).strip()
            loc = self._loc(p, "заголовок приложения")
            if res.alignment(p) != "center":
                self.report.add(loc, "Оформление заголовка", "заголовок приложения располагается по центру")
            if ends_with_sentence_dot(text):
                self.report.add(loc, "Оформление заголовка", "в конце заголовка не должно быть точки")
            if text[:1].islower():
                self.report.add(loc, "Оформление заголовка", "заголовок приложения пишется с прописной буквы")

    def check_headings(self, items):
        n, res = self.n, self.res
        tol = n["font_size_tolerance_pt"]
        for it in items:
            if it["role"] not in ("heading", "structural"):
                continue
            p = it["obj"]
            text = self.text(p).strip()
            loc = self._loc(p, "заголовок в абзаце")
            runs = self._runs(p)
            structural = it["role"] == "structural"

            if n["heading_bold"] and not structural and runs and not all(res.bold(r, p) for r in runs):
                self.report.add(loc, "Оформление заголовка", "заголовок раздела должен быть выделен жирным (п. 6.2.3)")
            if ends_with_sentence_dot(text):
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
                # первая буква — после номера: «2.1 структура данных» тоже ошибка
                first = HEADING_NUMBER_PREFIX_RE.sub("", text)[:1]
                if first.islower():
                    self.report.add(loc, "Оформление заголовка", "заголовок должен начинаться с прописной буквы")
                if n["heading_align"] == "center" and res.alignment(p) != "center":
                    self.report.add(loc, "Оформление заголовка", "заголовок располагается посередине страницы")

            for run in runs:
                fname = res.font_name(run, p)
                if not self.font_ok(fname):
                    self.report.add(loc, "Оформление заголовка",
                                    f"шрифт заголовка «{fname}», ожидается {self.font_want}")
                size = res.font_size(run, p)
                if size is not None and (size < n["font_size_min_pt"] - tol or size > n["font_size_max_pt"] + tol):
                    self.report.add(loc, "Оформление заголовка",
                                    f"размер шрифта заголовка {_fmt(size)} пт, ожидается {_fmt(n['font_size_pt'])} пт")
                color = res.color(run, p)
                if color and not run_in_hyperlink(run):
                    self.report.add(loc, "Оформление заголовка", f"цвет заголовка #{color}, ожидается чёрный")

    def check_new_page(self, items):
        for it in self.headings_missing_new_page(items):
            self.report.add(self._loc(it["obj"], "заголовок в абзаце"), "Оформление заголовка",
                            "заголовок должен начинаться с новой страницы (п. 6.2.1) — не найден разрыв страницы перед ним")

    def headings_missing_new_page(self, items):
        """Структурные элементы и разделы 1-го уровня без разрыва страницы перед ними (п. 6.2.1)."""
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
            if res.page_break_before(p) or starts_with_page_break(p):
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
                yield it

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
                                       ("table_caption", "Таблица", TAB_RE, "Таблица"),
                                       ("listing_caption", "Листинг", LISTING_RE, "Листинг")):
            expected_next = 1
            for it in items:
                if it["role"] != role:
                    continue
                p = it["obj"]
                text = self.text(p).strip()
                m = rx.match(text)
                if not m:
                    continue
                loc = self._loc(p)
                if it.get("misplaced") and role == "table_caption":
                    self.report.add(loc, "Подписи к рисункам и таблицам",
                                    "название таблицы стоит под таблицей, а ставится над ней (п. 6.6.3)")
                elif it.get("misplaced"):
                    self.report.add(loc, "Подписи к рисункам и таблицам",
                                    "подпись стоит над рисунком, а ставится под ним (п. 6.5.7)")
                elif it.get("orphan") and role == "table_caption":
                    self.report.add(loc, "Подписи к рисункам и таблицам",
                                    "под названием таблицы нет самой таблицы — она удалена или не вставлена")
                elif it.get("orphan"):
                    self.report.add(loc, "Подписи к рисункам и таблицам",
                                    "над подписью нет рисунка — он удалён или вставлен так, что Word не видит его "
                                    "как рисунок (например, фигурами без группировки)")
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
                    if ends_with_sentence_dot(text):
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
            if it["kind"] != "tbl" or it["role"] == "front":
                continue
            ti += 1
            seen_cells = set()
            for ri, row in enumerate(it["obj"].rows, start=1):
                for ci, cell in enumerate(row.cells, start=1):
                    if cell._tc in seen_cells:  # объединённые ячейки повторяются в row.cells
                        continue
                    seen_cells.add(cell._tc)
                    for p in cell.paragraphs:
                        for run in self._runs(p):
                            fname = res.font_name(run, p)
                            if not self.font_ok(fname):
                                loc = f"Таблица №{ti}, строка {ri}, столбец {ci}"
                                self._anchors[loc] = ("cell", it["i"], ri - 1, ci - 1)
                                self.report.add(loc, "Шрифт (таблица)",
                                                f"использован шрифт «{fname}», ожидается {self.font_want}")
                                break

    # ── структура ────────────────────────────────────────────────────────

    def check_structure(self, items):
        present = set()
        for it in items:
            if it["role"] in ("structural", "heading") and it["kind"] == "p":
                present.add(_norm_caps(self.text(it["obj"])))
        total_text = sum(len(self.text(it["obj"])) for it in items if it["kind"] == "p")
        if total_text < 1500:
            return  # слишком короткий фрагмент, обязательные разделы не ожидаются
        for title, variants in self.n["required_sections"]:
            if not any(v in present for v in variants):
                self.report.add("Структура работы", "Структура",
                                f"не найден структурный элемент «{title}» "
                                f"(или он оформлен не как заголовок)")


def check_docx(doc_or_path, report, profile, packs=()):
    doc = Document(doc_or_path) if isinstance(doc_or_path, (str, bytes)) or hasattr(doc_or_path, "__fspath__") \
        else doc_or_path
    DocxChecker(doc, report, profile, packs).run()
    return doc
