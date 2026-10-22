# -*- coding: utf-8 -*-
"""
ПГУПС (Петербургский государственный университет путей сообщения Императора Александра I):
всё, что идёт до основного текста ВКР, по СМК РД 02.01.18-2021 «Порядок проведения ГИА».

  10.11  состав пояснительной записки: титульный лист, задание на ВКР, аннотация, содержание,
         введение, … — именно в этом порядке
  10.13  титульный лист — по форме Приложения Ж; ФИО обучающегося полностью; у заведующего
         кафедрой, руководителя, консультантов и нормоконтролёра — учёные степени, звания,
         фамилии и инициалы
  10.14  задание — по форме Приложения К, заполнены все поля; специальность с шифром;
         в п. 1 — дата и номер распоряжения об утверждении темы; календарный план

Подписи и даты, которые ставятся от руки, по файлу не проверить — о них только напоминаем.
"""

import re
from datetime import date

DEFAULTS = {
    "document": "СМК РД 02.01.18-2021",
    # шапка формы (Приложения Ж и К): строки должны быть на титульном листе и в задании
    "header": [
        "ФЕДЕРАЛЬНОЕ АГЕНТСТВО ЖЕЛЕЗНОДОРОЖНОГО ТРАНСПОРТА",
        "Федеральное государственное бюджетное образовательное учреждение высшего образования",
        "«Петербургский государственный университет путей сообщения Императора Александра I»",
        "(ФГБОУ ВО ПГУПС)",
    ],
    "city": "Санкт-Петербург",
    # строки подписей титульного листа; у всех, кроме обучающегося, нужны степень/звание
    "signatures": ["Обучающийся", "Заведующий кафедрой", "Руководитель ВКР", "Нормоконтролер"],
    "require_task": True,
    # структурные элементы, которые идут после задания, — в этом порядке
    "front_order": ["АННОТАЦИЯ", "СОДЕРЖАНИЕ", "ВВЕДЕНИЕ"],
    "font_name": "Times New Roman",
}

CAT_TITLE = "Титульный лист (ПГУПС)"
CAT_TASK = "Задание на ВКР (ПГУПС)"
CAT_STRUCT = "Структура работы (ПГУПС)"

# подсказки под строками формы — не данные
HINTS = re.compile(
    r"(учёное|ученое)\s+звание,?\s*фамилия\s+и\.\s*о\.?|фамилия\s+и\.\s*о\.?|подпись,?\s*дата|"
    r"расшифровка\s+подписи|подпись|фамилия,\s*имя,\s*отчество(\s+обучающегося)?",
    re.IGNORECASE,
)
NAME_INITIALS = re.compile(
    r"[А-ЯЁ][а-яё]+(?:-[А-ЯЁ][а-яё]+)?\s*[А-ЯЁ]\.\s?[А-ЯЁ]\.|[А-ЯЁ]\.\s?[А-ЯЁ]\.\s?[А-ЯЁ][а-яё]+")
DEGREE = re.compile(
    r"(?<![а-яё])[кд]\.\s?(?:[а-яё]{1,3}\.\s?-?\s?){1,3}н\.|профессор|доцент|(?<![а-яё])проф\.|(?<![а-яё])доц\.|"
    r"преподаватель|(?<![а-яё])преп\.|ассистент|академик|член-корр",
    re.IGNORECASE,
)
SPECIALITY_CODE = re.compile(r"\d{2}\.\d{2}\.\d{2}")
CLAUSE = "СМК РД, п."


def norm(s):
    s = (s or "").replace("ё", "е").replace("Ё", "Е").replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).strip()


def key(s):
    """Для сравнения строк формы: без кавычек, регистра и лишних пробелов."""
    return re.sub(r"[«»\"“”„]", "", norm(s)).lower()


def filled(s):
    """В поле есть данные, а не только подчёркивания, пробелы и знаки препинания."""
    return len(re.sub(r"[\W_]", "", HINTS.sub("", s or ""))) >= 2


# ── сбор строк начала работы ──────────────────────────────────────────────

class Line:
    """Строка начала работы: абзац или строка таблицы (текст ячеек через « | »)."""

    def __init__(self, chk, it, text, row=None, cells=None):
        self.chk, self.it, self.text, self.row, self.cells = chk, it, norm(text), row, cells or []

    @property
    def para(self):
        return self.it["obj"] if self.it["kind"] == "p" else None

    def loc(self, label):
        if self.para is not None:
            return self.chk._loc(self.para)
        loc = f"{label}, строка «{norm(self.cells[0]) or '…'}»"
        self.chk._anchors[loc] = ("cell", self.it["i"], self.row, max(0, len(self.cells) - 1))
        return loc


def _lines(chk, items):
    out = []
    for it in items:
        if it["kind"] == "p":
            out.append(Line(chk, it, chk.text(it["obj"])))
            continue
        for ri, row in enumerate(it["obj"].rows):
            cells, seen = [], set()
            for c in row.cells:
                if c._tc in seen:
                    continue
                seen.add(c._tc)
                cells.append(" ".join(p.text for p in c.paragraphs))
            out.append(Line(chk, it, " | ".join(cells), row=ri, cells=cells))
    return out


def _find(lines, pattern, start=0):
    rx = re.compile(pattern, re.IGNORECASE)
    for k in range(start, len(lines)):
        if rx.search(lines[k].text):
            return k
    return None


def _split_title_task(lines, settings):
    """Титульный лист — до второго повторения шапки (с неё начинается задание) или до «ЗАДАНИЕ»."""
    first_header = key(settings["header"][0]) if settings["header"] else None
    seen = 0
    if first_header:
        for k, ln in enumerate(lines):
            if key(ln.text).startswith(first_header):
                seen += 1
                if seen == 2:
                    return lines[:k], lines[k:]
    k = _find(lines, r"^ЗАДАНИЕ$")
    if k is not None:
        return lines[:k], lines[k:]
    return lines, []


# ── проверки ──────────────────────────────────────────────────────────────

def _check_header(report, lines, settings, cat, where, first_loc):
    joined = key(" ".join(ln.text for ln in lines))
    for h in settings["header"]:
        if key(h) not in joined:
            report.add(first_loc, cat, f"нет строки «{norm(h)}» — шапка {where} должна быть как в форме")


def _field_after(text, label_rx):
    m = re.search(label_rx, text, re.IGNORECASE)
    return text[m.end():] if m else None


def _check_person(report, line, label, cat, need_degree):
    value = HINTS.sub(" ", " ".join(line.cells[1:]) if line.cells else line.text[len(label):])
    loc = line.loc(cat.split(" (")[0])
    if not NAME_INITIALS.search(value):
        report.add(loc, cat, f"«{label}»: не указаны фамилия и инициалы ({CLAUSE} 10.13)")
    elif need_degree and not DEGREE.search(value):
        report.add(loc, cat, f"«{label}»: не указаны учёная степень или звание — например, «к.т.н., доцент» "
                             f"({CLAUSE} 10.13)")


def check_title(chk, lines, settings, first_loc):
    report = chk.report
    if not lines:
        report.add("Титульный лист", CAT_TITLE,
                   "не найден титульный лист по форме Приложения Ж — он должен быть первой страницей работы")
        return
    _check_header(report, lines, settings, CAT_TITLE, "титульного листа", first_loc)

    for label in ("Факультет", "Кафедра"):
        k = _find(lines, rf"^{label}")
        if k is None:
            report.add(first_loc, CAT_TITLE, f"нет строки «{label} …»")
        elif not filled(_field_after(lines[k].text, rf"^{label}")):
            report.add(lines[k].loc("Титульный лист"), CAT_TITLE, f"не указано название: «{label.lower()} …»")

    joined = key(" ".join(ln.text for ln in lines))
    for must in ("ПОЯСНИТЕЛЬНАЯ ЗАПИСКА", "К ВЫПУСКНОЙ КВАЛИФИКАЦИОННОЙ РАБОТЕ"):
        if key(must) not in joined:
            report.add(first_loc, CAT_TITLE, f"нет строки «{must}»")

    # ФИО обучающегося — строка над подсказкой «Фамилия, имя, отчество обучающегося»
    k_hint = _find(lines, r"^фамилия,\s*имя,\s*отчество")
    k_kvr = _find(lines, r"квалификационной\s+работе")
    k_name = None
    if k_hint is not None:
        k_name = next((j for j in range(k_hint - 1, -1, -1) if filled(lines[j].text)), None)
        if k_name is not None and k_kvr is not None and k_name <= k_kvr:
            k_name = None   # над подсказкой сразу шапка — ФИО не вписано
    elif k_kvr is not None:
        k_topic = _find(lines, r"^на\s+тему", k_kvr)
        k_name = next((j for j in range(k_kvr + 1, k_topic or len(lines)) if filled(lines[j].text)), None)
    if k_name is None:
        report.add(lines[k_hint].loc("Титульный лист") if k_hint is not None else first_loc, CAT_TITLE,
                   f"не указаны фамилия, имя и отчество обучающегося ({CLAUSE} 10.13)")
    else:
        name = HINTS.sub(" ", lines[k_name].text)
        words = re.findall(r"[А-ЯЁA-Z][а-яёa-z]+(?:-[А-ЯЁ][а-яё]+)?", name)
        if re.search(r"(?<![А-ЯЁа-яё])[А-ЯЁ]\.", name):
            report.add(lines[k_name].loc("Титульный лист"), CAT_TITLE,
                       f"ФИО обучающегося пишется полностью, без инициалов ({CLAUSE} 10.13)")
        elif len(words) < 3:
            report.add(lines[k_name].loc("Титульный лист"), CAT_TITLE,
                       f"ФИО обучающегося — полностью: фамилия, имя и отчество ({CLAUSE} 10.13); "
                       f"если отчества нет, замечание можно не учитывать")

    k = _find(lines, r"^на\s+тему")
    if k is None:
        report.add(first_loc, CAT_TITLE, "нет строки «на тему …» с темой ВКР")
    else:
        topic = _field_after(lines[k].text, r"^на\s+тему")
        nxt = k + 1
        while not filled(topic) and nxt < len(lines) and lines[nxt].cells == [] and not filled(lines[nxt].text):
            nxt += 1
        if not filled(topic) and nxt < len(lines) and not lines[nxt].cells:
            topic = lines[nxt].text
        if not filled(topic):
            report.add(lines[k].loc("Титульный лист"), CAT_TITLE,
                       f"не указана тема ВКР — она должна точно совпадать с утверждённой ({CLAUSE} 10.13)")

    # подписи: «Обучающийся», «Заведующий кафедрой», «Руководитель ВКР», консультанты, «Нормоконтролер»
    for label in settings["signatures"]:
        rx = re.escape(label).replace("е", "[её]")
        k = _find(lines, rf"^{rx}")
        if k is None:
            report.add(first_loc, CAT_TITLE, f"нет строки подписи «{label}» (форма — Приложение Ж)")
            continue
        _check_person(report, lines[k], label, CAT_TITLE, need_degree=label != settings["signatures"][0])
    k = _find(lines, r"^консультант")
    if k is not None:   # консультанты — строки таблицы ниже, пока в первой ячейке пусто
        j = k
        while j < len(lines) and lines[j].cells and (j == k or not filled(lines[j].cells[0])):
            if filled(" ".join(lines[j].cells[1:])):
                _check_person(report, lines[j], "Консультант", CAT_TITLE, need_degree=True)
            j += 1

    k = _find(lines, rf"^{re.escape(settings['city'])}")
    if k is None:
        report.add(first_loc, CAT_TITLE, f"внизу титульного листа нет строки «{settings['city']} {date.today().year}»")
    else:
        m = re.search(r"(\d{4})", lines[k].text)
        if not m:
            report.add(lines[k].loc("Титульный лист"), CAT_TITLE, "не указан год")
        elif abs(int(m.group(1)) - date.today().year) > 1:
            report.add(lines[k].loc("Титульный лист"), CAT_TITLE,
                       f"год {m.group(1)} — проверьте, указывается год защиты")

    fonts = set()
    for ln in lines:
        paras = [ln.para] if ln.para is not None else \
            [p for c in ln.it["obj"].rows[ln.row].cells for p in c.paragraphs]
        for p in paras:
            for r in chk._runs(p):
                f = chk.res.font_name(r, p)
                if f and f != settings["font_name"]:
                    fonts.add(f)
    if fonts:
        report.add(first_loc, CAT_TITLE, f"шрифт {', '.join(sorted(fonts))} — на титульном листе, как и во всей "
                                         f"работе, используется {settings['font_name']} ({CLAUSE} 10.27)")


TASK_FIELDS = [
    # (как найти строку, как отрезать подпись поля, название поля в замечании, ставится ли от руки)
    (r"^1\.\s*Тема", r"^1\.\s*Тема\s*(ВКР)?", "1. Тема ВКР", False),
    (r"^утверждена\s+распоряжением", None, None, False),
    (r"^2\.\s*Срок\s+сдачи", r"^2\.\s*Срок\s+сдачи.*?ВКР", "2. Срок сдачи законченной ВКР", False),
    (r"^3\.\s*Исходные\s+данные", r"^3\.\s*Исходные\s+данные(\s*к\s*ВКР)?", "3. Исходные данные к ВКР", False),
    (r"^4\.\s*Содержание", r"^4\.\s*Содержание[^()]*(\([^)]*\))?", "4. Содержание пояснительной записки", False),
    (r"^5\.\s*Перечень\s+графическ", r"^5\.\s*Перечень\s+графическ[^()]*(\([^)]*\))?",
     "5. Перечень графического материала", False),
    (r"^Консультанты\s+с\s+указанием", None, None, False),
    (r"^6\.\s*Дата\s+выдачи", r"^6\.\s*Дата\s+выдачи\s+задания", "6. Дата выдачи задания", True),
    (r"^Руководитель\s+ВКР", None, None, False),
    (r"^Задание\s+принял", None, None, False),
    (r"^КАЛЕНДАРНЫЙ\s+ПЛАН", None, None, False),
]


def check_task(chk, lines, settings, first_loc):
    report = chk.report
    if not lines or _find(lines, r"^ЗАДАНИЕ$") is None:
        if settings["require_task"]:
            report.add(first_loc, CAT_TASK,
                       f"не найдено задание на ВКР — по {CLAUSE} 10.11 оно идёт сразу после титульного листа "
                       f"(форма — Приложение К). Если задание вшивается отдельным документом, "
                       f"замечание можно не учитывать")
        return
    task_loc = lines[_find(lines, r"^ЗАДАНИЕ$")].loc("Задание")
    _check_header(report, lines, settings, CAT_TASK, "задания", lines[0].loc("Задание"))

    def at(k):
        return lines[k].loc("Задание")

    k = _find(lines, r"Факультет")
    if k is None:
        report.add(task_loc, CAT_TASK, "нет строк «Факультет» и «Кафедра»")
    else:
        text = lines[k].text
        fac = re.search(r"Факультет(.*?)(Кафедра|$)", text, re.IGNORECASE)
        caf = _field_after(text, r"Кафедра")
        if caf is None and k + 1 < len(lines):
            caf = _field_after(lines[k + 1].text, r"Кафедра")
        if not fac or not filled(fac.group(1)):
            report.add(at(k), CAT_TASK, "не указан факультет")
        if caf is None or not filled(caf):
            report.add(at(k), CAT_TASK, "не указана кафедра")

    k = _find(lines, r"^Специальность")
    if k is None:
        report.add(task_loc, CAT_TASK, "нет строки «Специальность (направление)»")
    else:
        value = _field_after(lines[k].text, r"^Специальность\s*(\(направление\))?")
        if not filled(value):
            report.add(at(k), CAT_TASK, f"не указана специальность (направление) ({CLAUSE} 10.14)")
        elif not SPECIALITY_CODE.search(value):
            report.add(at(k), CAT_TASK, f"у специальности (направления) нет шифра по ФГОС, например «09.03.01» "
                                        f"({CLAUSE} 10.14)")
    k = _find(lines, r"^Специализация")
    if k is None:
        report.add(task_loc, CAT_TASK, "нет строки «Специализация (профиль)»")
    elif not filled(_field_after(lines[k].text, r"^Специализация\s*(\(профиль\))?")):
        report.add(at(k), CAT_TASK, "не указана специализация (профиль)")

    if _find(lines, r"^УТВЕРЖДАЮ") is None:
        report.add(task_loc, CAT_TASK, f"нет грифа «УТВЕРЖДАЮ / Зав. кафедрой» с датой утверждения ({CLAUSE} 10.14)")

    # ФИО — строка над подсказкой «фамилия, имя, отчество»
    k_hint = _find(lines, r"^фамилия,\s*имя,\s*отчество$")
    if k_hint is not None:
        k_name = next((j for j in range(k_hint - 1, -1, -1) if lines[j].text), None)
        if k_name is None or not filled(lines[k_name].text) or re.match(r"^на\s+выпускную", lines[k_name].text, re.I):
            report.add(at(k_hint), CAT_TASK, "не указаны фамилия, имя и отчество обучающегося")

    # пронумерованные поля: значение — до следующего поля формы
    found = [(_find(lines, rx), rx, cut, title, by_hand) for rx, cut, title, by_hand in TASK_FIELDS]
    starts = sorted(k for k, *_ in found if k is not None)
    for k, rx, cut, title, by_hand in found:
        if k is None:
            if title:
                report.add(task_loc, CAT_TASK, f"нет пункта «{title}» (форма — Приложение К)")
            continue
        end = next((s for s in starts if s > k), len(lines))
        if rx.startswith("^утверждена"):
            text = " ".join(ln.text for ln in lines[k:end])
            after_from = _field_after(text, r"\sот")
            after_no = _field_after(text, r"№")
            if not (after_from and re.search(r"\d", after_from.split("№")[0])) or not (after_no and re.search(r"\d", after_no)):
                report.add(at(k), CAT_TASK, f"в п. 1 не указаны дата и номер распоряжения об утверждении темы "
                                            f"({CLAUSE} 10.14)")
            continue
        if rx.startswith("^КАЛЕНДАРНЫЙ"):
            rows = [ln for ln in lines[k + 1:end] if ln.cells and len(ln.cells) > 1]
            data = [ln for ln in rows[1:] if filled(" ".join(ln.cells[1:]))]
            if not data:
                report.add(at(k), CAT_TASK, f"календарный план не заполнен — этапы и сроки выполнения ВКР "
                                            f"({CLAUSE} 10.14)")
            continue
        if not cut:
            continue
        value = re.sub(cut, "", lines[k].text, flags=re.IGNORECASE) + " " + \
            " ".join(ln.text for ln in lines[k + 1:end] if not ln.cells)
        if not filled(value):
            msg = f"не заполнен пункт «{title}» ({CLAUSE} 10.14: заполняются все поля задания)"
            if by_hand:
                msg += ". Если дату ставят от руки, замечание можно не учитывать"
            report.add(at(k), CAT_TASK, msg)


def check_order(chk, items, settings):
    """Аннотация → содержание → введение, сразу после задания (п. 10.11)."""
    report = chk.report
    pos = {}
    for it in items:
        if it["role"] == "structural" and it["kind"] == "p":
            t = norm(chk.text(it["obj"])).upper()
            pos.setdefault("СОДЕРЖАНИЕ" if t == "ОГЛАВЛЕНИЕ" else t, (it, t))
    order = []
    for name in settings["front_order"]:
        if name not in pos:
            alt = {"АННОТАЦИЯ": "РЕФЕРАТ"}.get(name)
            if alt and alt in pos:
                report.add(chk._loc(pos[alt][0]["obj"]), CAT_STRUCT,
                           f"в ВКР ПГУПС вместо реферата — «{name}» ({CLAUSE} 10.11, 10.15)")
                order.append(pos[alt][0]["i"])
            else:
                report.add("Структура работы", CAT_STRUCT, f"не найден элемент «{name}» ({CLAUSE} 10.11)")
            continue
        it, actual = pos[name]
        if actual != name:
            report.add(chk._loc(it["obj"]), CAT_STRUCT, f"элемент называется «{name}» ({CLAUSE} 10.11, 10.16)")
        order.append(it["i"])
    if order != sorted(order):
        report.add("Структура работы", CAT_STRUCT,
                   "порядок начала работы: титульный лист, задание, " +
                   ", ".join(n.lower() for n in settings["front_order"]) + f" ({CLAUSE} 10.11)")


def check(chk, items, settings):
    front = [it for it in items if it["role"] == "front"]
    lines = _lines(chk, front)
    first_loc = "Титульный лист"
    if front and front[0]["kind"] == "p":
        first_loc = chk._loc(front[0]["obj"])
    title, task = _split_title_task(lines, settings)
    check_title(chk, title, settings, first_loc)
    check_task(chk, task, settings, first_loc)
    check_order(chk, items, settings)
    chk.report.note(f"Дополнительно проверено по {settings['document']} (ПГУПС): титульный лист, задание на ВКР "
                    f"и порядок начальных разделов. Подписи и даты, которые ставятся от руки, по файлу не проверить.")
