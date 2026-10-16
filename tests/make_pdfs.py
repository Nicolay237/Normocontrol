# -*- coding: utf-8 -*-
"""Генератор тестовых PDF (reportlab, встроенный шрифт Times — только латиница в тексте)."""
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

import random

WORDS = ("data analysis method system quality decision model design approach hypothesis result "
         "comparison experiment parameter value research information structure process control "
         "technology development algorithm evaluation performance statistics sample variable").split()


def _text(rng, n_words):
    return " ".join(rng.choice(WORDS) for _ in range(n_words)).capitalize() + ". "


def make_pdf(path, left=3.0, right=1.5, top=2.0, bottom=2.0, size=14, leading=None,
             align=TA_JUSTIFY, indent=1.25, numbers=True, paragraphs=120):
    leading = leading or size * 1.15 * 1.5
    style = ParagraphStyle("b", fontName="Times-Roman", fontSize=size, leading=leading,
                           alignment=align, firstLineIndent=indent * cm, spaceAfter=0)

    def footer(canvas, doc):
        if numbers:
            canvas.setFont("Times-Roman", 12)
            canvas.drawCentredString(A4[0] / 2, 1.2 * cm, str(doc.page))

    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=left * cm, rightMargin=right * cm,
                            topMargin=top * cm, bottomMargin=bottom * cm)
    story = [Paragraph("INTRODUCTION", ParagraphStyle("h", fontName="Times-Bold", fontSize=size,
                                                       leading=leading, alignment=1))]
    rng = random.Random(7)
    story += [Paragraph(_text(rng, rng.randint(25, 70)), style) for _ in range(paragraphs)]
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
