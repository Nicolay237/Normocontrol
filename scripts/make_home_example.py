#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Пример отчёта для главной страницы — настоящий отчёт сервиса по «Курсовой с ошибками»
(make_broken_coursework.py), урезанный до нескольких замечаний в разделе. Пишется в
content/home.json рядом с FAQ; перезапускать, когда меняются тексты замечаний.

    python scripts/make_home_example.py
"""

import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [ROOT, os.path.join(ROOT, "tests"), os.path.join(ROOT, "scripts")]

from make_sample_coursework import build  # noqa: E402
from mutations import COMBINED, MUTATIONS  # noqa: E402
from checker import run_normocontrol  # noqa: E402
from checker.fixers import estimate_fixable, fix_docx  # noqa: E402
from checker.norms import PROFILES  # noqa: E402

PER_CATEGORY = 3
FILE_NAME = "Курсовая_Иванов_ИВТ-21.docx"
HOME_JSON = os.path.join(ROOT, "content", "home.json")


def example():
    by_key = {m.key: m for m in MUTATIONS}
    doc = build()
    for key in COMBINED:
        by_key[key].apply(doc)
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "work.docx")
        doc.save(path)
        report = run_normocontrol(path, "coursework")
        after = fix_docx(path, os.path.join(tmp, "fixed.docx"), PROFILES["coursework"]).after
    data = report.to_dict(FILE_NAME)
    return {
        "file": FILE_NAME,
        "profile": data["profile"]["title"],
        "total": data["total"],
        "fixable": estimate_fixable(report),
        "after_fix": len(after.issues),
        "categories": [{"name": c["name"], "count": c["count"],
                        "issues": [{"message": i["message"], "location": i["location"]}
                                   for i in c["issues"][:PER_CATEGORY]]}
                       # сначала самые насыщенные разделы — они видны раскрытыми
                       for c in sorted(data["categories"], key=lambda c: -c["count"])],
    }


def main():
    with open(HOME_JSON, encoding="utf-8") as fh:
        home = json.load(fh)
    home["example"] = example()
    with open(HOME_JSON, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(home, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    ex = home["example"]
    print(f"{HOME_JSON}: {ex['total']} замечаний, исправимо {ex['fixable']}, после исправления {ex['after_fix']}")


if __name__ == "__main__":
    main()
