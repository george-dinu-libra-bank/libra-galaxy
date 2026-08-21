"""Extras de tranzactii, ca PDF, pentru exportul cerut de utilizator din chat-ul asistentului.

Separat de pdf_raport.py (legat de dataclass-ul Raport, folosit de rapoartele
admin de frauda) — acesta e un tabel simplu, un singur utilizator, coloane in
romana. Niciodata nume tehnice de camp (id, counterparty_name etc.) — exact
bug-ul de reparat (orchestration/orchestrator.py::_handle_export_request).
"""

from __future__ import annotations

import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.repositories.banking_read_repository import TransactionRow

PRIMARY_600 = colors.HexColor("#2F6FED")
PRIMARY_50 = colors.HexColor("#EEF4FF")
INK = colors.HexColor("#0F1B33")
INK_SOFT = colors.HexColor("#4A5773")
INK_FAINT = colors.HexColor("#8A96AE")
LINE = colors.HexColor("#E3E9F2")

# Peste atatea randuri, tabelul nu mai incape rezonabil intr-un PDF; taiem si
# spunem cate au ramas, la fel ca pdf_raport.MAX_RANDURI.
MAX_RANDURI = 200


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
        "celula": ParagraphStyle(
            "celula", parent=baza["Normal"], fontSize=8.5, leading=12, textColor=INK_SOFT,
        ),
        "nota": ParagraphStyle(
            "nota", parent=baza["Normal"], fontSize=8.5, leading=12, textColor=INK_FAINT,
        ),
    }


def _tabel_tranzactii(tranzactii: list[TransactionRow], st: dict) -> Table:
    randuri = [["Data", "Descriere", "Contraparte", "Suma", "Sens", "Valuta"]]
    stiluri = [
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY_50),
        ("TEXTCOLOR", (0, 0), (-1, 0), PRIMARY_600),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ALIGN", (3, 1), (3, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
        ("TEXTCOLOR", (0, 1), (-1, -1), INK_SOFT),
    ]

    for i, t in enumerate(tranzactii[:MAX_RANDURI], start=1):
        randuri.append(
            [
                t.created_at[:10],
                Paragraph(t.description or "—", st["celula"]),
                Paragraph(t.counterparty_name or "—", st["celula"]),
                f"{t.amount:,.2f}".replace(",", "."),
                "Incasare" if t.incoming else "Plata",
                t.currency,
            ]
        )
        stiluri.append(
            ("TEXTCOLOR", (4, i), (4, i), colors.HexColor("#1D9A6C") if t.incoming else colors.HexColor("#F0435F"))
        )

    tabel = Table(
        randuri,
        colWidths=[20 * mm, 48 * mm, 40 * mm, 25 * mm, 22 * mm, 20 * mm],
        repeatRows=1,
    )
    tabel.setStyle(TableStyle(stiluri))
    return tabel


def randeaza(nume_titular: str, tranzactii: list[TransactionRow], generat_la: datetime) -> bytes:
    st = _stiluri()
    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"Extras tranzactii {nume_titular}",
        author="Galaxy Bank",
    )

    povestea: list = [
        Paragraph("Extras tranzactii — Galaxy Bank", st["titlu"]),
        Paragraph(
            f"Generat la {generat_la.strftime('%d.%m.%Y, %H:%M')} UTC · titular: {nume_titular}",
            st["subtitlu"],
        ),
        Spacer(1, 8 * mm),
    ]

    if not tranzactii:
        povestea.append(Paragraph("Nicio tranzactie gasita.", st["celula"]))
    else:
        povestea.append(_tabel_tranzactii(tranzactii, st))
        if len(tranzactii) > MAX_RANDURI:
            povestea.append(Spacer(1, 3 * mm))
            povestea.append(
                Paragraph(f"Inca {len(tranzactii) - MAX_RANDURI} tranzactii nu incap in tabel.", st["nota"])
            )

    document.build(povestea)
    return buffer.getvalue()


def nume_fisier(user_id: str, generat_la: datetime) -> str:
    return f"extras-tranzactii-{user_id[:8]}-{generat_la.date().isoformat()}.pdf"
