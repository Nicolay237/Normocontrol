# -*- coding: utf-8 -*-
"""
Проверка .pdf. В PDF нет абзацев и стилей, поэтому всё считается по
координатам текста, а результаты помечаются как оценочные. Чтобы не плодить
ложных срабатываний, замечания агрегируются по документу/страницам, а
номера страниц (одиночные числа у верхнего/нижнего края) в измерениях
полей и интервалов не участвуют.
"""

import re
import statistics
from collections import Counter

from .typography import check_typography
from .norms import STRUCTURAL_HEADINGS

PT_TO_CM = 2.54 / 72.0
CM_TO_PT = 72.0 / 2.54
ALT_FONT_HINTS = ("math", "symbol", "mono", "courier", "consolas", "cambria", "mt-extra", "mtextra")


def _fmt(v):
    return f"{v:g}".replace(".", ",")


def _cluster_lines(words, y_tol=2.5):
    lines, cur, top = [], [], None
    for w in sorted(words, key=lambda w: (round(w["top"], 1), w["x0"])):
        if top is None or abs(w["top"] - top) <= y_tol:
            cur.append(w)
            top = w["top"] if top is None else top
        else:
            lines.append(cur)
            cur, top = [w], w["top"]
    if cur:
        lines.append(cur)
    return lines


def _pages_label(pages, limit=6):
    pages = sorted(set(pages))
    shown = ", ".join(str(p) for p in pages[:limit])
    return f"Страницы {shown}" + (f" и ещё {len(pages) - limit}" if len(pages) > limit else "") \
        if len(pages) > 1 else f"Страница {pages[0]}"


def _family(fontname):
    name = re.sub(r"^[A-Z]{6}\+", "", fontname or "")
    return name


MONO_HINTS = ("courier", "consolas", "mono", "menlo", "monaco")
BIB_HEADINGS = ("СПИСОК ИСПОЛЬЗОВАННЫХ", "СПИСОК ЛИТЕРАТУРЫ", "СПИСОК ИСТОЧНИКОВ", "СПИСОК ИСПОЛЬЗОВАННОЙ",
                "БИБЛИОГРАФИЧЕСКИЙ СПИСОК")


def _heading_key(text):
    return re.sub(r"^\d+(?:\.\d+)*\.?\s+", "", (text or "").strip()).rstrip(".:").upper()


def _front_pages(pdf):
    """
    Титульный лист и задание — страницы до первого структурного элемента (СОДЕРЖАНИЕ, ВВЕДЕНИЕ…),
    если он нашёлся на первых шести страницах. Они оформляются по своим формам и не измеряются.
    """
    for i, page in enumerate(pdf.pages[:6], start=1):
        for line in (page.extract_text() or "").splitlines():
            if _heading_key(line) in STRUCTURAL_HEADINGS:
                return set(range(1, i))
    return set()


def _is_tnr(fontname):
    n = (fontname or "").lower().replace(" ", "").replace("-", "")
    return "timesnewroman" in n or n.startswith("times") or "liberationserif" in n


def check_pdf(path, report, n):
    import pdfplumber

    if not n["check_layout"]:
        report.note("В PDF проверяется только оформление текста. Список источников и ссылки "
                    "проверяются в файле Word (.docx).")
        return

    report.note(
        "PDF не хранит структуру абзацев и стилей — показатели вычислены по координатам "
        "текста и являются оценочными. Для точной проверки загрузите .docx."
    )
    tol = n["margins_tolerance_cm_pdf"]
    margin_hits = {"left": [], "right": [], "top": [], "bottom": []}
    spacing_hits, char_fonts = [], Counter()
    all_lines_by_page = {}
    page_numbers = {}  # страница → (центр x, у верхнего края?)

    with pdfplumber.open(path) as pdf:
        if not pdf.pages:
            report.add("Документ", "Общее", "в PDF не найдено ни одной страницы")
            return
        n_pages = len(pdf.pages)
        front = _front_pages(pdf)
        if front:
            report.note("Титульный лист и задание оформляются по своим формам — в PDF они не проверялись."
                        if len(front) > 1 else
                        "Титульный лист оформляется по своей форме — в PDF он не проверялся.")
        sizes_seen = Counter()
        page_dims = None

        for p_idx, page in enumerate(pdf.pages, start=1):
            page_w, page_h = page.width, page.height
            page_dims = page_dims or (page_w, page_h)
            if p_idx in front:
                continue
            words = page.extract_words(extra_attrs=["fontname", "size"])
            if not words:
                report.note(f"Страница {p_idx}: текстового слоя нет (возможно, скан) — пропущена.")
                continue

            lines = []
            for ln in _cluster_lines(words):
                lw = sorted(ln, key=lambda w: w["x0"])
                sizes = [w["size"] for w in lw if w.get("size")]
                lines.append({
                    "x0": min(w["x0"] for w in lw), "x1": max(w["x1"] for w in lw),
                    "top": min(w["top"] for w in lw), "bottom": max(w["bottom"] for w in lw),
                    "text": " ".join(w["text"] for w in lw),
                    "size": round(statistics.median(sizes), 1) if sizes else None,
                    "words": lw,
                    # строка листинга (моноширинный шрифт) — в измерениях основного текста не участвует
                    "code": sum(any(h in (w.get("fontname") or "").lower() for h in MONO_HINTS) for w in lw)
                            > len(lw) / 2,
                })

            # номер страницы — одиночное число у края; в измерениях не участвует
            body = []
            for l in lines:
                is_num = re.fullmatch(r"[-–—\s]*\d{1,4}[-–—\s]*", l["text"]) is not None
                edge = l["top"] < 2.0 * CM_TO_PT or l["bottom"] > page_h - 1.9 * CM_TO_PT
                if is_num and edge:
                    page_numbers[p_idx] = ((l["x0"] + l["x1"]) / 2, l["top"] < page_h / 2)
                elif not l["code"]:
                    body.append(l)
            if not body:
                continue
            all_lines_by_page[p_idx] = (body, page_w, page_h)

            for w in words:
                sizes_seen[round(w.get("size", 0), 1)] += len(w["text"])
                char_fonts[(_family(w.get("fontname")), round(w.get("size", 0), 1))] += len(w["text"])

            # поля: верхнее/нижнее — только «вторжение» текста в поле
            top_m = min(l["top"] for l in body) * PT_TO_CM
            bot_m = (page_h - max(l["bottom"] for l in body)) * PT_TO_CM
            if top_m < n["margins_cm"]["top"][0] - tol:
                margin_hits["top"].append((p_idx, round(top_m, 2)))
            if bot_m < n["margins_cm"]["bottom"][0] - tol:
                margin_hits["bottom"].append((p_idx, round(bot_m, 2)))
            # левое/правое — по «телу» текста, но только на плотных страницах
            if len(body) >= 12:
                # левый край текста — самый левый из частых x0 (а не самый частый: на странице
                # с короткими абзацами строк с красной строкой может быть больше, чем без неё)
                xs0 = Counter(round(l["x0"]) for l in body)
                frequent = [x for x, c in xs0.items() if c >= max(3, 0.15 * len(body))]
                left_m = (min(frequent) if frequent else xs0.most_common(1)[0][0]) * PT_TO_CM
                x1s = sorted(l["x1"] for l in body)
                mode_x1, cnt = Counter(round(l["x1"]) for l in body).most_common(1)[0]
                justified = cnt >= 0.25 * len(body)
                right_edge = mode_x1 if justified else x1s[-1]
                right_m = (page_w - right_edge) * PT_TO_CM
                lo, hi = n["margins_cm"]["left"]
                if left_m < lo - tol or left_m > hi + tol:
                    margin_hits["left"].append((p_idx, round(left_m, 2)))
                lo, hi = n["margins_cm"]["right"]
                # у текста «по левому краю» правая граница рваная: проверяем только вылезание в поле
                if right_m < lo - tol or (justified and right_m > hi + tol):
                    margin_hits["right"].append((p_idx, round(right_m, 2)))

        # ── поля
        names = {"left": "левое", "right": "правое", "top": "верхнее", "bottom": "нижнее"}
        for side, hits in margin_hits.items():
            if not hits or not n["check_margins"]:
                continue
            lo, hi = n["margins_cm"][side]
            want = f"{_fmt(lo)} см" if lo == hi else f"от {_fmt(lo)} до {_fmt(hi)} см"
            med = round(statistics.median(v for _, v in hits), 2)
            report.add(_pages_label([p for p, _ in hits]), "Поля страницы",
                       f"оценочное {names[side]} поле ≈ {_fmt(med)} см, ожидается {want} "
                       f"(допуск ±{_fmt(tol)} см на погрешность измерения)")

        # ── формат листа
        if page_dims:
            w, h = (round(x * PT_TO_CM, 1) for x in page_dims)
            a, b = sorted((w, h))
            if not (abs(a - 21.0) <= 0.4 and abs(b - 29.7) <= 0.4) and not (abs(a - 29.7) <= 0.6 and abs(b - 42.0) <= 0.6):
                report.add("Документ", "Формат листа", f"размер страницы {_fmt(w)}×{_fmt(h)} см, ожидается A4")

        # ── шрифт и кегль
        total_chars = sum(char_fonts.values()) or 1
        by_family = Counter()
        for (fam, _), c in char_fonts.items():
            by_family[fam] += c
        for fam, c in by_family.items():
            share = c / total_chars
            low = fam.lower()
            if share < 0.03 or _is_tnr(fam) or any(h in low for h in ALT_FONT_HINTS):
                continue
            report.add("Документ", "Шрифт",
                       f"использован шрифт «{fam}» (≈ {round(share * 100)}% текста), ожидается «{n['font_name']}»")
        if sizes_seen:
            body_size = sizes_seen.most_common(1)[0][0]
            if body_size and not (n["font_size_min_pt"] - n["font_size_tolerance_pt"] <= body_size
                                  <= n["font_size_max_pt"] + n["font_size_tolerance_pt"]):
                want = (f"{_fmt(n['font_size_pt'])} пт" if n["font_size_min_pt"] == n["font_size_max_pt"]
                        else f"{_fmt(n['font_size_min_pt'])}–{_fmt(n['font_size_max_pt'])} пт")
                report.add("Документ", "Кегль шрифта",
                           f"основной размер шрифта {_fmt(body_size)} пт, ожидается {want}")
            tiny = sum(c for s, c in sizes_seen.items() if 0 < s < n["font_size_floor_pt"] - n["font_size_tolerance_pt"])
            if tiny / total_chars >= 0.02:
                report.add("Документ", "Кегль шрифта",
                           f"≈ {round(tiny / total_chars * 100)}% текста набрано кеглем меньше "
                           f"{_fmt(n['font_size_floor_pt'])} пт")
        body_size = sizes_seen.most_common(1)[0][0] if sizes_seen else n["font_size_pt"]

        # ── интервал, красная строка, выравнивание — по странице
        expected_gap = n["line_spacing"] * body_size * n["line_height_factor"]
        indents, cont_flags = [], []
        for p_idx, (body, page_w, page_h) in all_lines_by_page.items():
            body_x0 = Counter(round(l["x0"]) for l in body).most_common(1)[0][0]
            gaps = []
            for a, b in zip(body, body[1:]):
                if not a["size"] or not b["size"]:
                    continue
                same = abs(a["size"] - body_size) < 0.8 and abs(b["size"] - body_size) < 0.8
                gap = b["top"] - a["top"]
                single = body_size * n["line_height_factor"]
                if same and 0.8 * single < gap < 2.4 * single:
                    gaps.append(gap)
            if len(gaps) >= 8:
                med = statistics.median(gaps)
                if abs(med - expected_gap) / expected_gap > n["line_spacing_tolerance_pdf"] * 0.75:
                    spacing_hits.append((p_idx, round(med / (body_size * n["line_height_factor"]), 2)))

            xs = sorted(l["x1"] for l in body)
            right_edge = xs[int(len(xs) * 0.95)]
            for prev, cur in zip(body, body[1:]):
                if not prev["size"] or not cur["size"] or abs(cur["size"] - body_size) >= 0.8:
                    continue
                if prev["x1"] < right_edge - 25:
                    indents.append(cur["x0"] - body_x0)      # cur начинает новый абзац
                elif abs(prev["size"] - body_size) < 0.8 and abs(cur["x0"] - body_x0) <= 3                         and abs(prev["x0"] - body_x0) <= 25:
                    cont_flags.append(prev["x1"] >= right_edge - 5)  # prev — не последняя строка абзаца

        if spacing_hits:
            med = round(statistics.median(v for _, v in spacing_hits), 2)
            report.add(_pages_label([p for p, _ in spacing_hits]), "Межстрочный интервал (оценка)",
                       f"межстрочный интервал ≈ {_fmt(med)}, ожидается {_fmt(n['line_spacing'])}")

        if len(indents) >= 15:
            no_indent = sum(1 for x in indents if abs(x) <= 3) / len(indents)
            real = [x for x in indents if 5 < x < 60]
            if no_indent > 0.6:
                report.add("Документ (оценка по всем страницам)", "Красная строка (оценка)",
                           f"абзацный отступ не обнаружен, ожидается {_fmt(n['first_line_indent_cm'])} см")
            elif real:
                typical = statistics.median(real) * PT_TO_CM
                if abs(typical - n["first_line_indent_cm"]) > n["first_line_indent_tolerance_cm_pdf"]:
                    report.add("Документ (оценка по всем страницам)", "Красная строка (оценка)",
                               f"типичный отступ первой строки ≈ {_fmt(round(typical, 2))} см, "
                               f"ожидается {_fmt(n['first_line_indent_cm'])} см")
        if len(cont_flags) >= 30:
            ratio = sum(cont_flags) / len(cont_flags)
            if ratio < n["justify_min_ratio"] and "left" not in n["body_align"]:
                report.add("Документ (оценка по всем страницам)", "Выравнивание (оценка)",
                           f"только {round(ratio * 100)}% строк доходят до правого края — "
                           f"похоже на выравнивание по левому краю (ожидается по ширине)")

        # ── нумерация страниц
        pos = n["page_number_pos"]
        if n["check_page_numbers"] and n_pages > 2:
            if len(page_numbers) < 0.5 * (n_pages - 1):
                where = {"bottom": "внизу страницы по центру", "top": "вверху страницы по центру"}.get(pos)
                report.add("Документ", "Нумерация страниц",
                           "номера страниц не найдены" + (f" (ожидаются {where})" if where else ""))
            elif pos != "any":
                want_top = pos == "top"
                wrong_side = sum(1 for _, top in page_numbers.values() if top != want_top)
                off_center = sum(1 for cx, top in page_numbers.values()
                                 if top == want_top and abs(cx - page_dims[0] / 2) > 2.5 * CM_TO_PT)
                if wrong_side > 0.5 * len(page_numbers):
                    report.add("Документ", "Нумерация страниц",
                               "номера страниц стоят внизу, а печатаются на середине верхнего поля" if want_top else
                               "номера страниц стоят вверху, по ГОСТ 7.32-2017 (п. 6.3.1) — внизу по центру")
                elif off_center > 0.5 * len(page_numbers):
                    report.add("Документ", "Нумерация страниц",
                               "номера страниц стоят не по центру " + ("верхней" if want_top else "нижней") +
                               " части страницы")

        # ── структура
        text_len = sum(len(l["text"]) for body, _, _ in all_lines_by_page.values() for l in body)
        if text_len >= 1500:
            found = set()
            for body, _, _ in all_lines_by_page.values():
                for l in body:
                    t = re.sub(r"^\d+(?:\.\d+)*\.?\s+", "", l["text"].strip()).rstrip(".:").upper()
                    if t in STRUCTURAL_HEADINGS:
                        found.add(t)
            for title, variants in n["required_sections"]:
                if not any(v in found for v in variants):
                    report.add("Структура работы", "Структура",
                               f"не найден структурный элемент «{title}»")

        # строки списка источников: « : », « / », « ; » в них по ГОСТ Р 7.0.100 — с пробелами
        page_texts, in_bib = [], False
        for p, (body, _, _) in all_lines_by_page.items():
            for l in body:
                key = _heading_key(l["text"])
                if key in STRUCTURAL_HEADINGS or key.startswith("ПРИЛОЖЕНИЕ"):
                    in_bib = key.startswith(BIB_HEADINGS)
                page_texts.append((f"Страница {p}, строка «{l['text'][:50]}»", l["text"], "bib" if in_bib else None))
    check_typography(page_texts, report)
