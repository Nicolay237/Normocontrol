# -*- coding: utf-8 -*-
"""
Список использованных источников.

Нормы:
  * ГОСТ 7.32-2017, п. 6.16 — источники в порядке появления ссылок в тексте,
    нумерация арабскими цифрами с точкой;
  * ГОСТ Р 7.0.100-2018 — библиографическое описание: «Фамилия, И. О.» в заголовке,
    области разделяются точкой и тире «. – », место издания полностью («Москва», а не «М.»),
    место и издательство разделяются « : », для электронных ресурсов — «URL:» и
    «(дата обращения: ДД.ММ.ГГГГ)», вместо «[Электронный ресурс]» — «Текст : электронный»
    (этот элемент в списках допускается не приводить, поэтому его отсутствие не ошибка);
  * ГОСТ Р 7.0.5-2008 — ссылки в тексте в квадратных скобках: [3], [3, с. 25], [1–4].

Проверки намеренно консервативные: замечание появляется, только когда признак
однозначен, — иначе запись пропускается.
"""

import re

from .norms import STRUCTURAL_HEADINGS

CATEGORY = "Список источников"
SOURCE_HEADINGS = {
    "СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ", "СПИСОК ИСПОЛЬЗОВАННОЙ ЛИТЕРАТУРЫ", "СПИСОК ЛИТЕРАТУРЫ",
    "БИБЛИОГРАФИЧЕСКИЙ СПИСОК", "СПИСОК ИСТОЧНИКОВ", "ЛИТЕРАТУРА", "ИСПОЛЬЗОВАННЫЕ ИСТОЧНИКИ",
}

# ── шаблоны ───────────────────────────────────────────────────────────────

NUM_PREFIX = re.compile(r"^\s*(\[?\d{1,3}\]?)([.)]?)\s+")
UPPER = "А-ЯЁA-Z"
LOWER = "а-яёa-z"
SURNAME = rf"[{UPPER}][{LOWER}]+(?:-[{UPPER}][{LOWER}]+)?"
# «Иванов И. И.» / «Иванов И.И.» — фамилия и инициалы без запятой
HEAD_NO_COMMA = re.compile(rf"^({SURNAME})\s+([{UPPER}]\.\s?[{UPPER}]\.|[{UPPER}]\.)(?=\s|$)")
# «Иванов, И.И.» — инициалы без пробела
HEAD_TIGHT_INITIALS = re.compile(rf"^{SURNAME},\s+[{UPPER}]\.[{UPPER}]\.")
YEAR = re.compile(r"(?<!\d)(1[89]\d{2}|20\d{2})(?!\d)")
URL = re.compile(r"(https?://|www\.)\S+", re.I)
URL_LABEL = re.compile(r"URL\s*:", re.I)
ACCESS_DATE = re.compile(r"\(\s*дата обращения\s*:\s*\d{1,2}\.\d{1,2}\.\d{4}\s*\)", re.I)
OLD_ER = re.compile(r"\[\s*Электронный ресурс\s*\]", re.I)
CITY_ABBR = re.compile(r"(?<![\w.])(М|СПб|Л|Мн|К|Н\.\s?Новгород)\.\s*:")
CITY_FULL = {"М": "Москва", "СПб": "Санкт-Петербург", "Л": "Ленинград", "Мн": "Минск", "К": "Киев"}
# «Москва:Наука», «Москва: Наука» — между местом и издательством « : »
PLACE_COLON = re.compile(rf"(?<=[{LOWER}])(\s?):(\s?)(?=[«\"{UPPER}])")
HYPHEN_SEP = re.compile(r"(?<=\S)\s-\s(?=\S)")
NO_SPACE_NUMBER = re.compile(r"№(?=\d)")
VOLUME = re.compile(r"\d+\s*с\.|[СC]\.\s*\d+|\bСт\.\s*\d+|\b\d+\s*p\.|\bpp?\.\s*\d+", re.I)
NON_BOOK = re.compile(r"ГОСТ|\bСП\s|СНиП|СанПиН|закон|кодекс|постановлени|указ\b|приказ|распоряжени|патент|"
                      r"\bсайт\b|официальн", re.I)
CITE = re.compile(r"\[([^\[\]]{1,60})\]")


def _strip_number(text):
    m = NUM_PREFIX.match(text)
    return (text[m.end():], m) if m else (text, None)


def _parse_cite(inner):
    """«3, с. 25» → {3}; «1–4» → {1,2,3,4}; «1, 5; 7» → {1,5,7}; не ссылка → None."""
    nums, ok = set(), False
    for tok in re.split(r"[;,]", inner):
        tok = tok.strip()
        if not tok:
            continue
        m = re.fullmatch(r"(\d{1,3})\s*[–—-]\s*(\d{1,3})", tok)
        if m and int(m.group(1)) < int(m.group(2)) <= int(m.group(1)) + 50:
            nums.update(range(int(m.group(1)), int(m.group(2)) + 1))
            ok = True
        elif re.fullmatch(r"\d{1,3}", tok):
            nums.add(int(tok))
            ok = True
        elif re.fullmatch(r"(?:[сcСC]|p|pp|л|т|стр)\.\s*[\d–—-]+.*", tok, re.I):
            continue        # страницы, тома и т. п. внутри ссылки
        else:
            return None     # «[принят Государственной думой …]» и прочее — не ссылка
    return nums if ok else None


# ── проверка ──────────────────────────────────────────────────────────────

def find_section(chk, items):
    """(индекс заголовка списка, [записи-абзацы]) или (None, [])."""
    start = None
    for idx, it in enumerate(items):
        if it["kind"] == "p" and it["role"] in ("structural", "heading"):
            name = re.sub(r"^\s*\d+(?:\.\d+)*\.?\s+", "", chk.text(it["obj"])).strip().rstrip(".:").upper()
            if name in SOURCE_HEADINGS:
                start = idx
    if start is None:
        return None, []
    entries = []
    for it in items[start + 1:]:
        if it["kind"] != "p":
            continue
        if it["role"] in ("structural", "heading"):
            break        # следующий раздел, обычно ПРИЛОЖЕНИЕ
        if it["role"] in ("empty", "image", "formula", "toc", "skip", "figure_caption", "table_caption"):
            continue
        text = chk.text(it["obj"]).strip()
        if text and (chk.res.is_numbered(it["obj"]) or looks_like_entry(text)):
            entries.append(it["obj"])
    return start, entries


def looks_like_entry(text):
    """Абзац похож на библиографическую запись (а не на случайный текст после списка)."""
    return bool(NUM_PREFIX.match(text) or URL.search(text) or "//" in text or YEAR.search(text)
                or re.search(r"\s[–—-]\s|\s:\s|\s/\s", text))


def _numbering_format(chk, p):
    """Текст номера автосписка Word: «%1.», «%1)», «[%1]»… или None."""
    try:
        num_pr = p._p.pPr.numPr
        num_id, ilvl = num_pr.numId.val, (num_pr.ilvl.val if num_pr.ilvl is not None else 0)
        numbering = chk.doc.part.numbering_part.element
        from docx.oxml.ns import qn
        num = next(n for n in numbering.findall(qn("w:num")) if n.get(qn("w:numId")) == str(num_id))
        abs_id = num.find(qn("w:abstractNumId")).get(qn("w:val"))
        absn = next(a for a in numbering.findall(qn("w:abstractNum")) if a.get(qn("w:abstractNumId")) == abs_id)
        lvl = next(l for l in absn.findall(qn("w:lvl")) if l.get(qn("w:ilvl")) == str(ilvl))
        fmt = lvl.find(qn("w:numFmt")).get(qn("w:val"))
        text = lvl.find(qn("w:lvlText")).get(qn("w:val"))
        return fmt, text
    except Exception:
        return None


def check_entry(text):
    """Замечания к одной записи (без номера в начале). Возвращает список сообщений."""
    msgs = []
    has_url = bool(URL.search(text))

    m = HEAD_NO_COMMA.match(text)
    if m:
        msgs.append(f"после фамилии автора ставится запятая: «{m.group(1)}, {_spaced(m.group(2))}» "
                    "(ГОСТ Р 7.0.100-2018)")
    elif HEAD_TIGHT_INITIALS.match(text):
        msgs.append("инициалы пишутся через пробел: «И. О.»")

    if OLD_ER.search(text):
        msgs.append("«[Электронный ресурс]» по ГОСТ Р 7.0.100-2018 не применяется — "
                    "вместо него «Текст : электронный» (можно не указывать)")
    if has_url:
        if not URL_LABEL.search(text):
            msgs.append("перед электронным адресом пишется «URL:»")
        else:
            before = text[:URL_LABEL.search(text).start()].rstrip()
            if before and not re.search(r"[–—]$", before):
                msgs.append("перед «URL:» ставятся точка и тире: «. – URL: …»")
        if not ACCESS_DATE.search(text):
            msgs.append("для электронного ресурса указывается дата обращения: «(дата обращения: 15.05.2025)»")
    elif not YEAR.search(text):
        msgs.append("не указан год издания")

    for mm in CITY_ABBR.finditer(text):
        full = CITY_FULL.get(mm.group(1).replace(" ", ""), "полное название")
        msgs.append(f"место издания пишется полностью: «{full}», а не «{mm.group(1)}.» (ГОСТ Р 7.0.100-2018)")
        break
    if not CITY_ABBR.search(text):
        for mm in PLACE_COLON.finditer(text):
            # двоеточие после места издания: перед ним «. – Город»
            head = text[:mm.start()]
            if re.search(r"[–—-]\s*[А-ЯЁ][а-яё-]+$", head) and (mm.group(1) != " " or mm.group(2) != " "):
                msgs.append("место издания и издательство разделяются пробелом, двоеточием и пробелом: «Москва : Наука»")
                break
    if HYPHEN_SEP.search(text):
        msgs.append("вместо дефиса с пробелами «-» ставится тире «–»")
    if NO_SPACE_NUMBER.search(text):
        msgs.append("после знака «№» ставится пробел: «№ 5»")

    if not has_url and not NON_BOOK.search(text) and YEAR.search(text) and not VOLUME.search(text):
        msgs.append("не указан объём: для книги — «– 240 с.», для статьи — «– С. 12–15»")
    return msgs


def _spaced(initials):
    return re.sub(r"\.(?=[А-ЯЁA-Z])", ". ", initials)


def check_bibliography(chk, items):
    start, entries = find_section(chk, items)
    if start is None or not entries:
        return
    report = chk.report

    # нумерация
    manual = [_strip_number(chk.text(p)) for p in entries]
    numbered_by_word = [chk.res.is_numbered(p) for p in entries]
    expected = 1
    bad_format_reported = False
    for p, (rest, m), auto in zip(entries, manual, numbered_by_word):
        loc = chk._loc(p)
        if auto:
            fmt = _numbering_format(chk, p)
            if fmt and not bad_format_reported and (fmt[0] != "decimal" or fmt[1].strip() != "%1."):
                report.add(loc, CATEGORY, f"номер источника в автосписке Word оформлен как «{fmt[1].replace('%1', '1')}», "
                                          "а нужно арабская цифра с точкой: «1.» (ГОСТ 7.32-2017, п. 6.16)")
                bad_format_reported = True
        elif m:
            num, punct = m.group(1), m.group(2)
            if num.startswith("[") or punct != ".":
                report.add(loc, CATEGORY, f"номер источника «{m.group(0).strip()}» — нужно арабская цифра с точкой: "
                                          f"«{num.strip('[]')}.» (ГОСТ 7.32-2017, п. 6.16)")
            n = int(num.strip("[]"))
            if n != expected:
                report.add(loc, CATEGORY, f"нарушена нумерация списка: источник № {n}, ожидался № {expected}")
            expected = n + 1
        else:
            report.add(loc, CATEGORY, "источник не пронумерован (ГОСТ 7.32-2017, п. 6.16)")

        for msg in check_entry(rest):
            report.add(loc, CATEGORY, msg)

    # повторы
    seen = {}
    for p, (rest, _) in zip(entries, manual):
        key = re.sub(r"\W+", "", rest.lower())
        if len(key) > 20 and key in seen:
            report.add(chk._loc(p), CATEGORY, f"источник повторяется (совпадает с записью № {seen[key]})")
        seen.setdefault(key, len(seen) + 1)

    _check_citations(chk, items, start, entries)


def _check_citations(chk, items, start, entries):
    """Ссылки [N] в тексте до списка: существуют, на все источники есть ссылки, порядок упоминания."""
    report = chk.report
    total = len(entries)
    first_seen = []          # номера в порядке первого упоминания
    any_cite = False
    for it in items[:start]:
        if it["kind"] != "p" or it["role"] in ("toc", "skip"):
            continue
        p = it["obj"]
        for m in CITE.finditer(chk.text(p)):
            nums = _parse_cite(m.group(1))
            if nums is None:
                continue
            any_cite = True
            for n in sorted(nums):
                if n < 1 or n > total:
                    report.add(chk._loc(p), CATEGORY,
                               f"ссылка [{n}] указывает на несуществующий источник: в списке {total} "
                               f"{'источник' if total % 10 == 1 and total % 100 != 11 else 'источников'}")
                elif n not in first_seen:
                    first_seen.append(n)
    if not any_cite:
        return   # ссылок в квадратных скобках нет (например, подстрочные сноски) — не проверяем
    for n, p in enumerate(entries, start=1):
        if n not in first_seen:
            report.add(chk._loc(p), CATEGORY, "на этот источник нет ссылки в тексте работы")
    # порядок: первые упоминания должны идти 1, 2, 3…
    for prev, cur in zip(first_seen, first_seen[1:]):
        if cur < prev:
            report.add(chk._loc(entries[cur - 1]), CATEGORY,
                       f"источники должны идти в порядке упоминания в тексте (ГОСТ 7.32-2017, п. 6.16): "
                       f"[{cur}] впервые упоминается после [{prev}]")
            break
