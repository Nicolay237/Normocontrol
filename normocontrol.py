#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Нормоконтроль — CLI. Логика проверок живёт в пакете checker/.

    python normocontrol.py работа.docx --type vkr
    python normocontrol.py курсовая.pdf --type coursework --html отчёт.html
"""

import os
import sys
import argparse

from checker import (
    run_normocontrol, build_html_report, format_text_report, PROFILES,
)
from checker.title_page import load_title_page_template


def main():
    parser = argparse.ArgumentParser(description="Проверка .docx/.pdf на нормоконтроль")
    parser.add_argument("doc_path", help="путь к .docx или .pdf файлу")
    parser.add_argument("--type", choices=sorted(PROFILES), default="vkr",
                        help="тип работы: vkr (ВКР) или coursework (курсовая)")
    parser.add_argument("--html", help="путь для HTML-отчёта (по умолчанию: <файл>_report.html)")
    parser.add_argument("--report", help="путь для текстового отчёта (опционально)")
    parser.add_argument("--no-html", action="store_true", help="не создавать HTML-отчёт")
    parser.add_argument("--title-template", help="образец титульного листа (.docx) для сравнения")
    args = parser.parse_args()

    template = None
    if args.title_template:
        try:
            template = load_title_page_template(args.title_template)
        except Exception as e:
            print(f"Не удалось загрузить шаблон титульного листа: {e}", file=sys.stderr)
            sys.exit(1)

    try:
        report = run_normocontrol(args.doc_path, args.type, title_page_template=template)
    except Exception as e:
        print(f"Ошибка при обработке файла: {e}", file=sys.stderr)
        sys.exit(1)

    text = format_text_report(report, args.doc_path)
    print(text)
    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"\nТекстовый отчёт сохранён в: {args.report}")
    if not args.no_html:
        html_path = args.html or os.path.splitext(args.doc_path)[0] + "_report.html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(build_html_report(report, os.path.basename(args.doc_path)))
        print(f"HTML-отчёт сохранён в: {html_path}")


if __name__ == "__main__":
    main()
