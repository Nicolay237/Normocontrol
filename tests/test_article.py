# -*- coding: utf-8 -*-
"""Оформление статьи по правилам журнала «Интеллектуальные технологии на транспорте»."""

import io
import os
import sys
from urllib.parse import quote

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt

from checker.article import format_article

ABSTRACT = ("Представлено исследование о разработке чат-бота для технологов. " * 16).strip()


def draft():
    """Черновик, как его присылает автор: Arial 12, двойной интервал, поля 2 см, стиль «Заголовок»."""
    doc = Document()
    s = doc.sections[0]
    s.left_margin = s.right_margin = s.top_margin = s.bottom_margin = Cm(2)
    st = doc.styles["Normal"]
    st.font.name, st.font.size = "Arial", Pt(12)
    st.paragraph_format.line_spacing = 2.0
    add = doc.add_paragraph
    add("УДК 656.073")
    add("Разработка чат-бота для поддержки технологов.")
    add("Власов Олег Петрович - канд. техн. наук, доцент. Научные интересы: информационные системы. "
        "E-mail: vlasov@pgups.ru.")
    add("Петербургский государственный университет путей сообщения Императора Александра I, Россия")
    add("Для цитирования: Власов О. П. Разработка чат-бота // Интеллектуальные технологии на транспорте. "
        "2025. № 1 (41). С. 00–00.")
    add("Аннотация. " + ABSTRACT)
    add("Ключевые слова: чат-бот; ГИД; РЖД; автоматизация; интеграция; цифровые технологии; диспетчер.")
    add("1.2.1 — искусственный интеллект и машинное обучение (технические науки).")
    doc.add_heading("Введение", level=1)
    add('Система "ГИД" повышает уровень управления [1]. Время отклика 0.25 с, в 2019-2020 годах - рост [2].')
    doc.add_heading("Обоснование внедрения чат-бота", level=1)
    add("Перечень задач решён ещё до внедрения [3]:")
    add("- обработка запросов;")
    add("• поиск документов.")
    add("Таблица 1 - Сравнение решений.")
    t = doc.add_table(rows=2, cols=2)
    t.cell(0, 0).text, t.cell(1, 0).text = "Решение", "ГИД"
    doc.add_paragraph().add_run().add_picture(_png(), width=Cm(3))
    add("Рисунок 1 - Схема работы.")
    doc.add_heading("Требования к функциям", level=1)
    add("Текст второго раздела со ссылкой [2].")
    doc.add_heading("Заключение", level=1)
    add("Краткие результаты работы.")
    add("Список литературы")
    for ref in ("Коробко А. В. Подход к отчётам // Информационные технологии. 2022. № 4. С. 181-189.",
                "Озерова В. С. Идентификация систем. Саратов: СГУ, 2023. 91 с.",
                "Лычкина Н. Н. Имитационное моделирование. М.: ИНФРА-М, 2022. 254 с.",
                "Неупомянутый И. И. Источник без ссылки. М., 2020. 10 с."):
        add(ref)
    add("Дата поступления: 00.00.2025")
    add("Решение о публикации: 00.00.2025")
    add("Development of a Chatbot to Support Railway Technologists")
    add("Oleg P. Vlasov - PhD in Engineering. Research interests: information systems. E-mail: vlasov@pgups.ru")
    add("Emperor Alexander I St. Petersburg State Transport University, Russia")
    add("Abstract. A study on the development of a chatbot is presented.")
    add("Keywords: chatbot, automation, integration.")
    add("References")
    add("Korobko A. V. Approach to reports. Informatsionnye tekhnologii, 2022, no. 4, pp. 181–189 (In Russian).")
    add("Received: 00.00.2025")
    return doc


def _png():
    import base64
    return io.BytesIO(base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="))


def formatted(tmp_path):
    src, dst = tmp_path / "draft.docx", tmp_path / "article.docx"
    draft().save(src)
    result = format_article(str(src), str(dst))
    return result, Document(str(dst))


def para(doc, start):
    return next(p for p in doc.paragraphs if p.text.strip().startswith(start))


def size(p):
    return p.runs[0].font.size.pt


def test_page_and_head(tmp_path):
    result, doc = formatted(tmp_path)
    s = doc.sections[0]
    assert [round(x.cm, 2) for x in (s.left_margin, s.right_margin, s.top_margin, s.bottom_margin)] == [1.29, 1.29, 1.9, 2.5]
    title = para(doc, "Разработка чат-бота")
    assert size(title) == 24 and all(r.bold for r in title.runs) and not title.text.endswith(".")
    author = para(doc, "Власов Олег")
    assert author.runs[0].text == "Власов Олег Петрович" and author.runs[0].bold
    assert " — канд." in author.text and author.text.endswith("pgups.ru")
    kw = para(doc, "Ключевые слова")
    assert kw.runs[0].bold and not kw.text.endswith(".") and size(kw) == 12
    spec = para(doc, "1.2.1")
    assert all(r.italic for r in spec.runs) and spec.runs[0].bold and not spec.text.endswith(".")
    assert para(doc, "Для цитирования").runs[0].bold
    texts = [p.text.strip() for p in doc.paragraphs]
    assert texts[:3] == ["УДК 656.073", "", "Разработка чат-бота для поддержки технологов"]
    assert texts[texts.index("Обоснование внедрения чат-бота") - 1] == ""    # пустая строка перед разделом


def test_body_headings_tables_figures(tmp_path):
    result, doc = formatted(tmp_path)
    h = para(doc, "Обоснование")
    assert size(h) == 14 and h.runs[0].bold and h.runs[0].font.small_caps
    body = para(doc, "Система")
    assert size(body) == 14 and round(body.paragraph_format.first_line_indent.cm, 2) == 0.5
    assert body.paragraph_format.alignment == WD_ALIGN_PARAGRAPH.JUSTIFY
    assert "«ГИД»" in body.text and "2019–2020" in body.text and " – рост" in body.text
    assert "еще" in para(doc, "Перечень").text                       # ё → е
    assert para(doc, "– поиск").text.startswith("– поиск")            # маркер «•» → тире
    label = para(doc, "Таблица 1")
    assert label.text == "Таблица 1" and label.runs[0].italic and label.alignment == WD_ALIGN_PARAGRAPH.RIGHT
    title = para(doc, "Сравнение решений")
    assert title.alignment == WD_ALIGN_PARAGRAPH.CENTER and not title.text.endswith(".")
    assert doc.tables[0].cell(0, 0).paragraphs[0].runs[0].font.size.pt == 11
    fig = para(doc, "Рис. 1.")
    assert fig.text == "Рис. 1. Схема работы" and fig.runs[0].italic and fig.alignment == WD_ALIGN_PARAGRAPH.CENTER


def test_references_and_english(tmp_path):
    result, doc = formatted(tmp_path)
    head = para(doc, "СПИСОК ИСТОЧНИКОВ")
    assert size(head) == 12 and head.alignment == WD_ALIGN_PARAGRAPH.LEFT
    ref = para(doc, "1. Коробко")
    assert size(ref) == 12 and "С. 181–189" in ref.text
    assert para(doc, "4. Неупомянутый")
    assert size(para(doc, "Development of a Chatbot")) == 24
    assert para(doc, "Oleg P. Vlasov").runs[0].bold
    assert para(doc, "REFERENCES")
    assert para(doc, "Abstract").runs[0].bold


def test_warnings_for_author(tmp_path):
    result, doc = formatted(tmp_path)
    w = " | ".join(result.warnings)
    assert "Источников 4" in w                       # редакция рекомендует 15–30
    assert "[4]" in w                                # на источник нет ссылки
    assert "0.25" in w                               # десятичная точка
    assert "Объём аннотации" not in w and "Ключевых слов" not in w
    assert not any("Английский блок" in x for x in result.warnings)


def test_reference_example_is_kept(tmp_path):
    """Уже оформленная статья не ломается от повторного оформления."""
    result, doc = formatted(tmp_path)
    path = tmp_path / "article.docx"
    again = format_article(str(path), str(tmp_path / "again.docx"))
    doc2 = Document(str(tmp_path / "again.docx"))
    assert [p.text for p in doc.paragraphs] == [p.text for p in doc2.paragraphs]
    assert not any(k.startswith("Источники пронумерованы") for k in again.done)


# ── доступ: только тем, кому открыл администратор ──

def _upload(c):
    buf = io.BytesIO()
    draft().save(buf)
    return c.post("/api/article/format", data={"file": (io.BytesIO(buf.getvalue()), "статья.docx")},
                  content_type="multipart/form-data")


def test_article_access_is_granted_by_admin():
    from test_auth import admin_client, client, register
    assert _upload(client()).status_code == 401                     # без входа

    c = client()
    assert register(c, "teacher@pgups.ru", ip="10.9.9.9").status_code == 201
    me = c.get("/api/me").get_json()["user"]
    assert me["article_access"] is False
    r = _upload(c)
    assert r.status_code == 403 and r.get_json()["code"] == "no_access"

    adm = admin_client()
    uid = me["id"]
    assert adm.patch(f"/api/admin/users/{uid}", json={"article_access": True}).status_code == 200
    row = next(x for x in adm.get("/api/admin/users").get_json()["users"] if x["id"] == uid)
    assert row["article_access"] is True
    assert c.get("/api/me").get_json()["user"]["article_access"] is True
    r = _upload(c)
    body = r.get_json()
    assert r.status_code == 200 and body["download_id"] and body["done"] and body["warnings"]
    file = c.get(f"/api/fixed/{body['download_id']}")
    assert file.status_code == 200 and file.data[:2] == b"PK"       # готовый .docx
    assert quote("статья_оформлено.docx") in file.headers["Content-Disposition"]

    assert adm.patch(f"/api/admin/users/{uid}", json={"article_access": False}).status_code == 200
    assert _upload(c).status_code == 403


def test_admin_needs_article_access_too():
    """Вкладку «Статьи ПГУПС» видят только те, кому она включена, — администратор тоже."""
    from test_auth import admin_client
    adm = admin_client()
    me = adm.get("/api/me").get_json()["user"]
    try:
        adm.patch(f"/api/admin/users/{me['id']}", json={"article_access": False})
        assert adm.get("/api/me").get_json()["user"]["article_access"] is False
        assert _upload(adm).status_code == 403
        assert adm.patch(f"/api/admin/users/{me['id']}", json={"article_access": True}).status_code == 200
        assert _upload(adm).status_code == 200
    finally:
        adm.patch(f"/api/admin/users/{me['id']}", json={"article_access": True})


def test_article_rejects_pdf():
    from test_auth import admin_client
    adm = admin_client()
    me = adm.get("/api/me").get_json()["user"]
    adm.patch(f"/api/admin/users/{me['id']}", json={"article_access": True})
    r = adm.post("/api/article/format", data={"file": (io.BytesIO(b"%PDF-1.4"), "a.pdf")},
                            content_type="multipart/form-data")
    assert r.status_code == 400


# ── статья в формате сборника: авторы списком, название прописными, английский блок до текста ──

def conference_draft():
    doc = Document()
    add = doc.add_paragraph
    add("УДК 004.896")
    add("Торнев А.М.1, Сидельников А.А.1, Забродин А.В.2")
    add("Петербургский государственный университет путей сообщения Императора Александра I")
    add("1 студент группы ИВБ-415")
    add("2 к.и.н., доцент кафедры “Информационные и вычислительные системы”")
    add("ИНТЕЛЛЕКТУАЛЬНАЯ СИСТЕМА ТЕХНИЧЕСКОГО ОСМОТРА РЕЛЬСОВОГО ПУТИ").runs[0].bold = True
    add("Аннотация. " + ABSTRACT[:500])
    add("Рассматриваются конкретные технологические решения и их эффект.")
    add("Ключевые слова: рельсы, осмотр, робот, нейросеть, лидар, камеры, автоматизация.")
    add("Tornev A.M.1, Sidelnikov A.A.1, Zabrodin A.V.2")
    add("Emperor Alexander I St. Petersburg State Transport University")
    add("AN INTELLIGENT SYSTEM FOR TECHNICAL INSPECTION OF RAIL TRACKS")
    add("Abstract. This paper addresses the inspection of rail tracks.")
    add("Keywords: rail tracks, inspection, robot.")
    p = add("")
    p.add_run("Введение").bold = True
    p.add_run(".").bold = True
    p.add_run(" Железнодорожный транспорт остается ключевым элементом экономики [1].")
    add("1.1. Аппаратная часть: роботизированная платформа")
    add("Главной частью является автономная каретка [2].")
    add("Заключение").runs[0].bold = True
    add("Система сокращает время осмотра.")
    add("Библиографический список:")
    add("Лидар // Wikipedia. URL: https://ru.wikipedia.org/wiki/Лидар (дата обращения: 01.11.2025).")
    add("Классификация дефектов рельсов. М., 2020. 12 с.")
    return doc


def test_conference_style_article(tmp_path):
    src, dst = tmp_path / "conf.docx", tmp_path / "conf_out.docx"
    conference_draft().save(src)
    result = format_article(str(src), str(dst))
    doc = Document(str(dst))
    texts = [p.text.strip() for p in doc.paragraphs]
    nonempty = [t for t in texts if t]
    # название — сразу после УДК, затем авторы и должности
    assert nonempty[:3] == ["УДК 004.896", "ИНТЕЛЛЕКТУАЛЬНАЯ СИСТЕМА ТЕХНИЧЕСКОГО ОСМОТРА РЕЛЬСОВОГО ПУТИ",
                            "Торнев А.М.1, Сидельников А.А.1, Забродин А.В.2"]
    assert size(para(doc, "ИНТЕЛЛЕКТУАЛЬНАЯ")) == 24 and para(doc, "Торнев").runs[0].bold
    assert "«Информационные и вычислительные системы»" in para(doc, "2 к.и.н.").text
    # аннотация из двух абзацев — 12 пт, не основной текст
    assert size(para(doc, "Рассматриваются")) == 12
    # «Введение.» вынесено отдельным заголовком
    intro = para(doc, "Введение")
    assert intro.text == "Введение" and intro.runs[0].font.small_caps
    assert para(doc, "Железнодорожный").text.startswith("Железнодорожный")
    # подраздел «1.1. …» без жирного — заголовок
    assert para(doc, "1.1. Аппаратная").runs[0].bold
    # английский блок — в конце, после списка источников
    assert nonempty.index("Tornev A.M.1, Sidelnikov A.A.1, Zabrodin A.V.2") > nonempty.index("СПИСОК ИСТОЧНИКОВ")
    assert size(para(doc, "AN INTELLIGENT")) == 24
    w = " | ".join(result.warnings)
    assert "Авторы указаны списком" in w and "прописными" in w
    assert "Не найдено: сведения об авторах" not in w and "Объём аннотации" in w
    assert any("Английский блок перенесён" in k for k in result.done)


# ── ошибки на статьях кафедры: источники теряются, ложные «несуществующие источники» ──

def _math(p):
    """Формула Word (OMML) внутри абзаца — как O(n + m) в тексте."""
    from docx.oxml import parse_xml
    p._p.append(parse_xml(
        '<m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">'
        '<m:r><m:t>O(n+m)</m:t></m:r></m:oMath>'))


def refs_article(refs_heading="Библиографический список:"):
    doc = Document()
    add = doc.add_paragraph
    add("УДК 004.4")
    add("СИСТЕМА ОБНАРУЖЕНИЯ ПЛАГИАТА НА ОСНОВЕ АЛГОРИТМА").runs[0].bold = True
    add("Аннотация. " + ABSTRACT[:900])
    add("Ключевые слова: плагиат, хеш, алгоритм, код, токены, сравнение, нормализация.")
    add("Введение").runs[0].bold = True
    p = add("Алгоритм использует хеширование [1]. Средняя сложность ")
    _math(p)
    p.add_run(", что быстрее перебора [2].")
    head = add("")
    head.add_run("Архитектура системы").bold = True
    head.add_run().add_break()
    head.add_run("Система состоит из модулей [3], хранилище описано в [4].")
    add("Методы сжатия без потерь.").runs[0].bold = True
    add("Сравнение выполняется по окнам [5].")
    add("Заключение").runs[0].bold = True
    add("Система работает.")
    add(refs_heading)
    add("Бхаргава А. Грокаем алгоритмы. СПб.: Питер, 2022. 288 с.")
    add("Строус Л. Алгоритмы с нуля. СПб.: Питер, 2024. 256 с.")
    add("Banks A., Porcello E. Learning React: Modern Patterns for Developing React Apps. 3rd ed. O'Reilly, 2020. 310 p.")
    add("Абдулазиз А. А. Создание веб-API Python с помощью FastAPI. М.: ДМК Пресс, 2023. 220 с.")
    add("Obe R., Hsu L. PostgreSQL: Up and Running. Sebastopol: O'Reilly Media, 2017. 312 p.")
    add("PLAGIARISM DETECTION SYSTEM BASED ON THE ALGORITHM")
    add("Abstract. The article discusses plagiarism detection.")
    return doc


def _run_refs(tmp_path, **kw):
    src, dst = tmp_path / "refs.docx", tmp_path / "refs_out.docx"
    refs_article(**kw).save(src)
    return format_article(str(src), str(dst)), Document(str(dst))


def test_foreign_books_stay_in_reference_list(tmp_path):
    result, doc = _run_refs(tmp_path)
    w = " | ".join(result.warnings)
    assert "Источников 5" in w                         # все пять, а не два до первой иностранной книги
    assert "несуществующие" not in w and "нет ссылок" not in w
    assert size(para(doc, "3. Banks A.")) == 12 and size(para(doc, "5. Obe R.")) == 12   # пронумерованы
    assert size(para(doc, "PLAGIARISM DETECTION")) == 24        # английский блок — после списка


def test_reference_heading_variants(tmp_path):
    result, doc = _run_refs(tmp_path, refs_heading="ИСПОЛЬЗУЕМЫЕ ИСТОЧНИКИ")
    assert para(doc, "СПИСОК ИСТОЧНИКОВ")
    assert "Источников 5" in " | ".join(result.warnings)


def test_paragraph_with_inline_formula_is_text(tmp_path):
    """Формула внутри абзаца не делает его формулой: абзац оформлен, ссылка [1] учтена."""
    result, doc = _run_refs(tmp_path)
    p = para(doc, "Алгоритм использует")
    assert size(p) == 14 and round(p.paragraph_format.first_line_indent.cm, 2) == 0.5
    assert not any("[1]" in x for x in result.warnings)


def test_heading_with_period_and_heading_with_line_break(tmp_path):
    result, doc = _run_refs(tmp_path)
    h = para(doc, "Методы сжатия без потерь")
    assert h.text == "Методы сжатия без потерь" and h.runs[0].font.small_caps
    arch = para(doc, "Архитектура системы")
    assert arch.text == "Архитектура системы" and arch.runs[0].font.small_caps
    body = para(doc, "Система состоит")
    assert size(body) == 14 and not body.runs[0].bold
    assert not any("Разделов" in x for x in result.warnings)


def test_missing_introduction_is_reported(tmp_path):
    doc = refs_article()
    for p in doc.paragraphs:
        if p.text == "Введение":
            p.runs[0].text = "Постановка задачи"
    src, dst = tmp_path / "a.docx", tmp_path / "b.docx"
    doc.save(src)
    result = format_article(str(src), str(dst))
    assert any("Нет раздела «Введение»" in x for x in result.warnings)
    assert not any("«Заключение»" in x for x in result.warnings)
