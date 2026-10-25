#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Курсовая со множеством ошибок оформления — эталон (make_sample_coursework.py), испорченный
по каталогу tests/mutations.py (список COMBINED). Рядом пишется перечень внесённых ошибок,
чтобы сверить с отчётом сервиса.

    python scripts/make_broken_coursework.py "samples/Курсовая с ошибками.docx"
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [ROOT, os.path.join(ROOT, "tests"), os.path.join(ROOT, "scripts")]

from make_sample_coursework import build  # noqa: E402
from mutations import COMBINED, MUTATIONS  # noqa: E402


def main(out):
    by_key = {m.key: m for m in MUTATIONS}
    doc = build()
    lines = ["Ошибки, внесённые в «Курсовую с ошибками» (эталон: «Идеальная курсовая»)", ""]
    for n, key in enumerate(COMBINED, 1):
        m = by_key[key]
        m.apply(doc)
        lines.append(f"{n:2}. {m.title} — {m.gost}{' (исправляется автоматически)' if m.fixable else ''}")
    doc.save(out)
    listing = os.path.splitext(out)[0] + " — список ошибок.txt"
    with open(listing, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"сохранено: {out}\nсписок ошибок: {listing}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "Курсовая с ошибками.docx")
