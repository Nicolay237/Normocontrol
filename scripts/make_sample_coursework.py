#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Образцовая курсовая работа, оформленная строго по ГОСТ 7.32-2017 и ГОСТ Р 7.0.100-2018:
на ней проверка должна находить 0 замечаний (и показывать салют).

    python scripts/make_sample_coursework.py "Идеальная курсовая.docx"

В ней есть всё, что проверяет сервис: титульный лист, содержание, введение, разделы
и подразделы, перечисление, рисунок, таблица, листинг кода, заключение, список источников
со ссылками в тексте, приложение с листингом. Тот же документ использует тест
tests/test_sample.py — если проверка начнёт ругаться на эталон, тест упадёт.
"""

import io
import sys

from docx import Document
from docx.enum.section import WD_SECTION_START
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_TAB_ALIGNMENT, WD_TAB_LEADER
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

FONT = "Times New Roman"
CODE_FONT = "Courier New"

TITLE = "Разработка программы поиска кратчайших путей в графе дорожной сети"
STUDENT = "Иванов Иван Иванович"

SOURCES = [
    "Кормен, Т. Алгоритмы: построение и анализ / Т. Кормен, Ч. Лейзерсон, Р. Ривест, К. Штайн. – 3-е изд. – "
    "Москва : Вильямс, 2013. – 1328 с.",
    "Седжвик, Р. Алгоритмы на C++ / Р. Седжвик. – Москва : Вильямс, 2011. – 1056 с.",
    "Макконнелл, Дж. Основы современных алгоритмов / Дж. Макконнелл. – 2-е изд. – Москва : Техносфера, "
    "2004. – 368 с.",
    "Петров, А. В. Сравнение алгоритмов поиска кратчайшего пути на дорожных графах / А. В. Петров, "
    "С. Н. Смирнова // Информационные технологии. – 2022. – № 4. – С. 31–38.",
    "Страуструп, Б. Программирование. Принципы и практика с использованием C++ / Б. Страуструп. – 2-е изд. – "
    "Москва : Вильямс, 2016. – 1328 с.",
    "Документация по стандартной библиотеке C++. – URL: https://en.cppreference.com/w/cpp/container "
    "(дата обращения: 10.03.2026).",
]


# ── стили ─────────────────────────────────────────────────────────────────

def _fonts(style, name=FONT, size=14):
    style.font.name = name
    style.font.size = Pt(size)
    style.font.color.rgb = RGBColor(0, 0, 0)
    rpr = style.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    for a in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rfonts.set(qn(a), name)


def _page_number(paragraph):
    run = paragraph.add_run()
    for kind, text in (("begin", None), (None, " PAGE "), ("end", None)):
        el = OxmlElement("w:fldChar" if kind else "w:instrText")
        if kind:
            el.set(qn("w:fldCharType"), kind)
        else:
            el.set(qn("xml:space"), "preserve")
            el.text = text
        run._r.append(el)


def new_document():
    doc = Document()
    s = doc.sections[0]
    s.page_width, s.page_height = Cm(21), Cm(29.7)
    s.left_margin, s.right_margin, s.top_margin, s.bottom_margin = Cm(3), Cm(1.5), Cm(2), Cm(2)
    s.different_first_page_header_footer = True     # на титульном листе номер не ставится (п. 6.3.1)
    footer = s.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _page_number(footer)

    normal = doc.styles["Normal"]
    _fonts(normal)
    pf = normal.paragraph_format
    pf.line_spacing, pf.alignment, pf.first_line_indent = 1.5, WD_ALIGN_PARAGRAPH.JUSTIFY, Cm(1.25)
    pf.space_before = pf.space_after = Pt(0)

    for name in ("Heading 1", "Heading 2"):
        st = doc.styles[name]
        _fonts(st)
        st.font.bold, st.font.italic = True, False
        f = st.paragraph_format
        f.alignment, f.first_line_indent, f.line_spacing = WD_ALIGN_PARAGRAPH.LEFT, Cm(1.25), 1.5
        f.space_before, f.space_after = Pt(0), Pt(0)
        f.keep_with_next = True
    doc.styles["Heading 1"].paragraph_format.page_break_before = True   # раздел — с новой страницы

    for level in (1, 2):   # стили строк содержания: Word называет их «toc 1», «toc 2»
        st = doc.styles.add_style(f"toc {level}", WD_STYLE_TYPE.PARAGRAPH)
        st.base_style = normal
        st.paragraph_format.first_line_indent = Cm(0)
        st.paragraph_format.left_indent = Cm(0 if level == 1 else 0.5)
        st.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
    return doc


# ── блоки ─────────────────────────────────────────────────────────────────

def para(doc, text="", align=None, indent=None, spacing=None, bold=False, size=None):
    p = doc.add_paragraph()
    if text:
        r = p.add_run(text)
        r.bold = bold or None
        if size:
            r.font.size = Pt(size)
    if align is not None:
        p.alignment = align
    if indent is not None:
        p.paragraph_format.first_line_indent = Cm(indent)
    if spacing is not None:
        p.paragraph_format.line_spacing = spacing
    return p


def body(doc, *texts):
    for t in texts:
        doc.add_paragraph(t)


def structural(doc, text, new_page=True):
    """ВВЕДЕНИЕ, ЗАКЛЮЧЕНИЕ… — по центру, прописными, полужирным, с новой страницы (п. 6.2.1)."""
    p = para(doc, text, align=WD_ALIGN_PARAGRAPH.CENTER, indent=0, bold=True)
    p.paragraph_format.page_break_before = new_page
    p.paragraph_format.keep_with_next = True
    return p


def page_break(doc):
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


def title_page(doc):
    c = WD_ALIGN_PARAGRAPH.CENTER
    for line in ("Министерство науки и высшего образования Российской Федерации",
                 "Федеральное государственное бюджетное образовательное учреждение высшего образования",
                 "«Северный государственный технический университет»"):
        para(doc, line, align=c, indent=0, spacing=1.0)
    para(doc, "Кафедра информационных систем", align=c, indent=0, spacing=1.0)
    for _ in range(6):
        para(doc, spacing=1.0)
    para(doc, "КУРСОВАЯ РАБОТА", align=c, indent=0, spacing=1.0, bold=True)
    para(doc, "по дисциплине «Структуры и алгоритмы обработки данных»", align=c, indent=0, spacing=1.0)
    para(doc, f"на тему «{TITLE}»", align=c, indent=0, spacing=1.0)
    for _ in range(5):
        para(doc, spacing=1.0)
    right = WD_ALIGN_PARAGRAPH.RIGHT
    para(doc, f"Выполнил студент группы ИС-21: {STUDENT}", align=right, indent=0, spacing=1.0)
    para(doc, "Руководитель: к.т.н., доцент Петров П. П.", align=right, indent=0, spacing=1.0)
    for _ in range(7):
        para(doc, spacing=1.0)
    para(doc, "Санкт-Петербург 2026", align=c, indent=0, spacing=1.0)


TOC = [   # номера страниц — как в Word (проверено экспортом в PDF)
    (1, "Введение", 3),
    (1, "1 Анализ предметной области", 4),
    (2, "1.1 Задача поиска кратчайшего пути", 4),
    (2, "1.2 Обзор алгоритмов", 4),
    (1, "2 Разработка программы", 6),
    (2, "2.1 Структура данных", 6),
    (2, "2.2 Реализация алгоритма Дейкстры", 6),
    (1, "3 Тестирование", 8),
    (1, "Заключение", 9),
    (1, "Список использованных источников", 10),
    (1, "Приложение А Полный текст программы", 11),
]


def toc(doc):
    structural(doc, "СОДЕРЖАНИЕ")
    for level, text, page in TOC:
        p = doc.add_paragraph(style=f"toc {level}")
        p.paragraph_format.tab_stops.add_tab_stop(Cm(16.5), WD_TAB_ALIGNMENT.RIGHT, WD_TAB_LEADER.DOTS)
        r = p.add_run(text)
        r.bold = level == 1      # в содержании жирные только разделы верхнего уровня
        p.add_run(f"\t{page}")


def figure(doc):
    """Схема графа — рисунок по центру, подпись под ним (п. 6.5.7)."""
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGB", (900, 420), "white")
    d = ImageDraw.Draw(img)
    big, small = ImageFont.load_default(size=34), ImageFont.load_default(size=26)
    nodes = {"A": (90, 210), "B": (330, 80), "C": (330, 340), "D": (590, 120), "E": (590, 320), "F": (810, 210)}
    edges = [("A", "B", 4), ("A", "C", 2), ("B", "C", 1), ("B", "D", 5), ("C", "E", 8), ("D", "E", 3),
             ("D", "F", 6), ("E", "F", 2)]
    for a, b, w in edges:
        (x1, y1), (x2, y2) = nodes[a], nodes[b]
        d.line((x1, y1, x2, y2), fill="black", width=4)
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        d.rectangle((mx - 20, my - 20, mx + 20, my + 20), fill="white", outline="black", width=2)
        d.text((mx, my), str(w), fill="black", font=small, anchor="mm")
    for name, (x, y) in nodes.items():
        d.ellipse((x - 34, y - 34, x + 34, y + 34), fill="white", outline="black", width=4)
        d.text((x, y), name, fill="black", font=big, anchor="mm")
    buf = io.BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    p = para(doc, align=WD_ALIGN_PARAGRAPH.CENTER, indent=0)
    p.add_run().add_picture(buf, width=Cm(14))
    para(doc, "Рисунок 1 – Взвешенный граф дорожной сети", align=WD_ALIGN_PARAGRAPH.CENTER, indent=0)


def table(doc):
    """Название — над таблицей слева, без абзацного отступа (п. 6.6.3)."""
    para(doc, "Таблица 1 – Сравнение алгоритмов поиска кратчайших путей", align=WD_ALIGN_PARAGRAPH.LEFT, indent=0)
    rows = [("Алгоритм", "Сложность", "Отрицательные веса"),
            ("Дейкстры", "O((V + E) log V)", "нет"),
            ("Беллмана – Форда", "O(V · E)", "да"),
            ("Флойда – Уоршелла", "O(V³)", "да")]
    t = doc.add_table(rows=len(rows), cols=3)
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for r, values in enumerate(rows):
        for c, value in enumerate(values):
            cell = t.cell(r, c)
            p = cell.paragraphs[0]
            p.paragraph_format.first_line_indent = Cm(0)
            p.paragraph_format.line_spacing = 1.0
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER if r == 0 else WD_ALIGN_PARAGRAPH.LEFT
            run = p.add_run(value)
            run.bold = r == 0 or None
            run.font.size = Pt(12)


DIJKSTRA = [
    "vector<long long> Dijkstra(const Graph& g, int start)",
    "{",
    "    vector<long long> dist(g.size(), INF);",
    "    priority_queue<pair<long long, int>,",
    "                   vector<pair<long long, int>>,",
    "                   greater<>> queue;",
    "    dist[start] = 0;",
    "    queue.push({0, start});",
    "    while (!queue.empty())",
    "    {",
    "        auto [d, v] = queue.top();",
    "        queue.pop();",
    "        if (d > dist[v])",
    "            continue;",
    "        for (const Edge& e : g[v])",
    "        {",
    "            if (dist[v] + e.weight < dist[e.to])",
    "            {",
    "                dist[e.to] = dist[v] + e.weight;",
    "                queue.push({dist[e.to], e.to});",
    "            }",
    "        }",
    "    }",
    "    return dist;",
    "}",
]

MAIN = [
    "#include <iostream>",
    "#include <queue>",
    "#include <vector>",
    "",
    "using namespace std;",
    "",
    "const long long INF = 1e18;",
    "",
    "struct Edge",
    "{",
    "    int to;",
    "    long long weight;",
    "};",
    "",
    "using Graph = vector<vector<Edge>>;",
    "",
    "int main()",
    "{",
    "    int n, m;",
    "    cin >> n >> m;",
    "    Graph g(n);",
    "    for (int i = 0; i < m; i++)",
    "    {",
    "        int from, to;",
    "        long long weight;",
    "        cin >> from >> to >> weight;",
    "        g[from].push_back({to, weight});",
    "        g[to].push_back({from, weight});",
    "    }",
    "    vector<long long> dist = Dijkstra(g, 0);",
    "    for (int v = 0; v < n; v++)",
    "        cout << v << \": \" << dist[v] << \"\\n\";",
    "    return 0;",
    "}",
]


def listing(doc, caption, lines):
    """Подпись над кодом; код — Courier New 12 пт, одинарный интервал, по левому краю, без отступа."""
    para(doc, caption, align=WD_ALIGN_PARAGRAPH.LEFT, indent=0)
    for line in lines:
        p = para(doc, align=WD_ALIGN_PARAGRAPH.LEFT, indent=0, spacing=1.0)
        if line:
            r = p.add_run(line)
            r.font.name, r.font.size = CODE_FONT, Pt(12)


def bullets(doc, items):
    """Перечисление — через дефис, с абзацного отступа (п. 6.4.5)."""
    for i, item in enumerate(items):
        doc.add_paragraph(f"- {item}{'.' if i == len(items) - 1 else ';'}")


# ── работа ────────────────────────────────────────────────────────────────

def build():
    doc = new_document()
    title_page(doc)
    toc(doc)

    structural(doc, "ВВЕДЕНИЕ")
    body(doc,
         "Поиск кратчайшего пути — одна из базовых задач теории графов. Её решают навигационные сервисы, "
         "логистические компании и службы доставки: каждый день они прокладывают миллионы маршрутов по "
         "дорожным сетям, в которых десятки тысяч перекрёстков и улиц.",
         "Актуальность работы связана с тем, что скорость построения маршрута напрямую влияет на удобство "
         "сервисов и на затраты на перевозки. Даже небольшое ускорение алгоритма при большом числе запросов "
         "даёт заметную экономию вычислительных ресурсов.",
         f"Цель работы — разработать программу поиска кратчайших путей в графе дорожной сети и оценить её "
         f"эффективность.",
         "Для достижения цели поставлены следующие задачи:")
    bullets(doc, ["изучить постановку задачи и существующие алгоритмы её решения",
                  "выбрать структуру данных для хранения графа",
                  "реализовать алгоритм Дейкстры на языке C++",
                  "проверить корректность и скорость работы программы"])
    body(doc, "Объект исследования — графы дорожных сетей, предмет — алгоритмы поиска кратчайших путей в них.")

    doc.add_heading("1 Анализ предметной области", level=1)
    doc.add_heading("1.1 Задача поиска кратчайшего пути", level=2)
    body(doc,
         "Дорожную сеть удобно представить взвешенным графом: перекрёстки становятся вершинами, участки дорог "
         "— рёбрами, а длина или время проезда участка — весом ребра [1]. Пример такого графа показан на "
         "рисунке 1.")
    figure(doc)
    body(doc,
         "Задача состоит в том, чтобы для заданной начальной вершины найти пути минимального суммарного веса "
         "до всех остальных вершин. На рисунке 1 кратчайший путь из вершины A в вершину F проходит через "
         "вершины C, B и D, а его длина равна 2 + 1 + 5 + 6 = 14.",
         "Веса рёбер дорожного графа неотрицательны: расстояние и время проезда не бывают меньше нуля. Это "
         "свойство позволяет использовать более быстрые алгоритмы, чем в общем случае [2].")

    doc.add_heading("1.2 Обзор алгоритмов", level=2)
    body(doc,
         "Для поиска кратчайших путей применяют алгоритмы Дейкстры, Беллмана – Форда и Флойда – Уоршелла [3]. "
         "Они различаются вычислительной сложностью и тем, допускают ли отрицательные веса рёбер. Основные "
         "характеристики алгоритмов приведены в таблице 1.")
    table(doc)
    body(doc,
         "Алгоритм Флойда – Уоршелла находит расстояния между всеми парами вершин, но для графа с десятками "
         "тысяч вершин требует слишком много памяти и времени. Алгоритм Беллмана – Форда допускает "
         "отрицательные веса, которых в дорожной сети нет, и работает медленнее.",
         "По результатам сравнения на реальных дорожных графах алгоритм Дейкстры с двоичной кучей оказывается "
         "самым быстрым для одного источника [4]. Поэтому он выбран для реализации.")

    doc.add_heading("2 Разработка программы", level=1)
    doc.add_heading("2.1 Структура данных", level=2)
    body(doc,
         "Граф хранится списками смежности: для каждой вершины — массив исходящих рёбер с номером конечной "
         "вершины и весом. Такое представление занимает память, пропорциональную числу рёбер, и позволяет "
         "быстро перебирать соседей вершины [5].",
         "Для хранения списков используется контейнер vector стандартной библиотеки C++, а для выбора "
         "вершины с наименьшим расстоянием — очередь с приоритетом priority_queue [6].")

    doc.add_heading("2.2 Реализация алгоритма Дейкстры", level=2)
    body(doc,
         "Функция получает граф и номер начальной вершины и возвращает массив расстояний до всех вершин. "
         "Текст функции приведён в листинге 1.")
    listing(doc, "Листинг 1 – Реализация алгоритма Дейкстры", DIJKSTRA)
    body(doc,
         "Вершина извлекается из очереди вместе с расстоянием, с которым она туда попала. Если расстояние "
         "уже успело уменьшиться, запись устарела и пропускается — так не приходится удалять элементы из "
         "середины очереди. Полный текст программы приведён в приложении А.")

    doc.add_heading("3 Тестирование", level=1)
    body(doc,
         "Корректность программы проверена на графе, изображённом на рисунке 1: найденные расстояния "
         "совпали с вычисленными вручную. Затем программа запущена на графе дорожной сети города с 48 тысячами "
         "вершин и 112 тысячами рёбер.",
         "Поиск расстояний от одной вершины до всех остальных занял в среднем 21 мс на компьютере с "
         "процессором частотой 3,2 ГГц, что достаточно для построения маршрутов в реальном времени.")

    structural(doc, "ЗАКЛЮЧЕНИЕ")
    body(doc,
         "В ходе работы изучена задача поиска кратчайших путей и проведён обзор алгоритмов её решения. Для "
         "графов дорожных сетей с неотрицательными весами выбран алгоритм Дейкстры с двоичной кучей.",
         "Разработана программа на языке C++, хранящая граф списками смежности. Тестирование подтвердило "
         "корректность результатов и показало, что на графе с 48 тысячами вершин расчёт занимает около 21 мс.",
         "Все поставленные задачи выполнены, цель работы достигнута.")

    structural(doc, "СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ")
    for i, src in enumerate(SOURCES, 1):
        doc.add_paragraph(f"{i}. {src}")

    structural(doc, "ПРИЛОЖЕНИЕ А")
    para(doc, "Полный текст программы", align=WD_ALIGN_PARAGRAPH.CENTER, indent=0, bold=True)
    listing(doc, "Листинг А.1 – Основная программа", MAIN)
    return doc


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "Идеальная курсовая.docx"
    build().save(out)
    print(f"сохранено: {out}")
