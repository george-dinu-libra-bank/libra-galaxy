"""Raportul ca PDF.

reportlab si nu weasyprint: weasyprint cere cairo si pango instalate in sistem,
ceea ce merge pe o masina de dezvoltare si cade in container. reportlab e
python curat.

Culorile vin din DESIGN.md, ca raportul sa semene cu aplicatia din care iese.
"""

import io

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.services.raport_service import ETICHETE_TIP, Raport

# DESIGN.md, sectiunea 2.
PRIMARY_600 = colors.HexColor("#2F6FED")
PRIMARY_50 = colors.HexColor("#EEF4FF")
INK = colors.HexColor("#0F1B33")
INK_SOFT = colors.HexColor("#4A5773")
INK_FAINT = colors.HexColor("#8A96AE")
LINE = colors.HexColor("#E3E9F2")
DANGER = colors.HexColor("#F0435F")
WARNING = colors.HexColor("#F5A524")

# Peste atatea constatari, tabelul nu mai incape intr-o pagina; le taiem si
# spunem cate au ramas, ca sa nu para ca raportul le-a pierdut.
MAX_RANDURI = 60


def _stiluri() -> dict[str, ParagraphStyle]:
    baza = getSampleStyleSheet()
    return {
        "titlu": ParagraphStyle(
            "titlu", parent=baza["Title"], fontSize=20, leading=25,
            textColor=INK, alignment=TA_LEFT, spaceAfter=2,
        ),
        "subtitlu": ParagraphStyle(
            "subtitlu", parent=baza["Normal"], fontSize=10, leading=14, textColor=INK_FAINT,
        ),
        "sectiune": ParagraphStyle(
            "sectiune", parent=baza["Heading2"], fontSize=12, leading=16,
            textColor=INK, spaceBefore=14, spaceAfter=6,
        ),
        "corp": ParagraphStyle(
            "corp", parent=baza["Normal"], fontSize=9.5, leading=13.5, textColor=INK_SOFT,
        ),
        "celula": ParagraphStyle(
            "celula", parent=baza["Normal"], fontSize=8, leading=11, textColor=INK_SOFT,
        ),
        "nota": ParagraphStyle(
            "nota", parent=baza["Normal"], fontSize=8.5, leading=12, textColor=INK_FAINT,
        ),
    }


def _antet(raport: Raport, st: dict) -> list:
    return [
        Paragraph("Raport de analiza a tranzactiilor", st["titlu"]),
        Paragraph(
            f"Generat la {raport.generat_la.strftime('%d.%m.%Y, %H:%M')} UTC · "
            f"perioada analizata: ultimele {raport.zile} de zile",
            st["subtitlu"],
        ),
        Spacer(1, 8 * mm),
    ]


def _tabel_identitate(raport: Raport, st: dict) -> Table:
    randuri = [
        ["Titular", raport.nume],
        ["Email", raport.email],
        ["IBAN", raport.iban],
        ["Tranzactii analizate", str(raport.total_tranzactii)],
    ]
    tabel = Table(randuri, colWidths=[45 * mm, 120 * mm])
    tabel.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TEXTCOLOR", (0, 0), (0, -1), INK_FAINT),
                ("TEXTCOLOR", (1, 0), (1, -1), INK),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("LINEBELOW", (0, 0), (-1, -2), 0.5, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return tabel


def _tabel_rezumat(raport: Raport, st: dict) -> Table:
    randuri = [["Tip semnalare", "Numar"]]
    for tip, cate in sorted(raport.pe_tip.items(), key=lambda x: -x[1]):
        randuri.append([ETICHETE_TIP.get(tip, tip), str(cate)])
    randuri.append(["Total", str(len(raport.constatari))])

    tabel = Table(randuri, colWidths=[120 * mm, 45 * mm])
    tabel.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), PRIMARY_50),
                ("TEXTCOLOR", (0, 0), (-1, 0), PRIMARY_600),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("TEXTCOLOR", (0, 1), (-1, -1), INK_SOFT),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LINEBELOW", (0, 0), (-1, -1), 0.5, LINE),
            ]
        )
    )
    return tabel


def _culoare_scor(scor: float) -> colors.Color:
    if scor >= 10:
        return DANGER
    if scor >= 5:
        return WARNING
    return INK_SOFT


def _tabel_constatari(raport: Raport, st: dict) -> Table:
    randuri = [["Data", "Comerciant", "Suma", "Tip", "Scor", "Explicatie"]]
    stiluri = [
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY_50),
        ("TEXTCOLOR", (0, 0), (-1, 0), PRIMARY_600),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (2, 1), (2, -1), "RIGHT"),
        ("ALIGN", (4, 1), (4, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
        ("TEXTCOLOR", (0, 1), (-1, -1), INK_SOFT),
    ]

    for i, c in enumerate(raport.constatari[:MAX_RANDURI], start=1):
        randuri.append(
            [
                c.data,
                Paragraph(c.comerciant, st["celula"]),
                f"{c.suma:,.2f}".replace(",", "."),
                Paragraph(ETICHETE_TIP.get(c.tip, c.tip), st["celula"]),
                f"{c.scor:.2f}",
                Paragraph(c.explicatie, st["celula"]),
            ]
        )
        stiluri.append(("TEXTCOLOR", (4, i), (4, i), _culoare_scor(c.scor)))
        stiluri.append(("FONTNAME", (4, i), (4, i), "Helvetica-Bold"))

    tabel = Table(
        randuri,
        colWidths=[18 * mm, 30 * mm, 20 * mm, 30 * mm, 13 * mm, 54 * mm],
        repeatRows=1,
    )
    tabel.setStyle(TableStyle(stiluri))
    return tabel


def randeaza(raport: Raport) -> bytes:
    st = _stiluri()
    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"Raport analiza {raport.nume}",
        author="Libra",
    )

    povestea: list = [*_antet(raport, st)]
    povestea.append(Paragraph("Contul analizat", st["sectiune"]))
    povestea.append(_tabel_identitate(raport, st))

    if raport.sinteza:
        povestea.append(Paragraph("Sinteza", st["sectiune"]))
        povestea.append(Paragraph(raport.sinteza, st["corp"]))
        povestea.append(Spacer(1, 2 * mm))
        povestea.append(
            Paragraph(
                "Sinteza de mai sus e generata automat. Faptele pe care se bazeaza sunt "
                "in tabelul de constatari; in caz de nepotrivire, tabelul are dreptate.",
                st["nota"],
            )
        )

    if not raport.constatari:
        povestea.append(Paragraph("Constatari", st["sectiune"]))
        povestea.append(
            Paragraph(
                "Nicio plata nu a iesit din tiparul obisnuit al acestui cont in perioada "
                "analizata.",
                st["corp"],
            )
        )
    else:
        povestea.append(Paragraph("Rezumat", st["sectiune"]))
        povestea.append(_tabel_rezumat(raport, st))
        povestea.append(PageBreak())
        povestea.append(Paragraph("Constatari, cea mai grava prima", st["sectiune"]))
        povestea.append(_tabel_constatari(raport, st))

        if len(raport.constatari) > MAX_RANDURI:
            povestea.append(Spacer(1, 3 * mm))
            povestea.append(
                Paragraph(
                    f"Inca {len(raport.constatari) - MAX_RANDURI} constatari nu incap in "
                    "tabel. Sunt toate in fisierul CSV.",
                    st["nota"],
                )
            )

    povestea.append(Spacer(1, 8 * mm))
    povestea.append(
        KeepTogether(
            Paragraph(
                "<b>Constatarile sunt statistice, nu fraude dovedite.</b> Ele arata plati "
                "care ies din tiparul obisnuit al contului si care merita verificate — "
                "nu stabilesc ca s-a intamplat ceva ilegal. Orice masura asupra contului "
                "se ia dupa verificare, nu pe baza acestui raport singur.",
                st["nota"],
            )
        )
    )

    document.build(povestea)
    return buffer.getvalue()


def nume_fisier(raport: Raport) -> str:
    return f"raport-{raport.id_utilizator[:8]}-{raport.generat_la.date().isoformat()}.pdf"
