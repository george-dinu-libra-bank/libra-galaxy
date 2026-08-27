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

from app.rapoarte import fonturi
from app.services.raport_service import ETICHETE_TIP, Raport

# Fontul cu diacritice e cautat de `rapoarte/fonturi.py` — vezi acolo de ce nu
# ajunge Helvetica si ce se intampla cand nu se gaseste nimic mai bun.
FONT_NORMAL = "Helvetica"
FONT_BOLD = "Helvetica-Bold"


def _inregistreaza_fontul() -> None:
    """Fixeaza numele fontului pentru tot modulul, la prima folosire."""
    global FONT_NORMAL, FONT_BOLD
    FONT_NORMAL, FONT_BOLD = fonturi.inregistreaza()


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
    _inregistreaza_fontul()
    baza = getSampleStyleSheet()
    return {
        "titlu": ParagraphStyle(
            "titlu", parent=baza["Title"], fontName=FONT_NORMAL, fontSize=20, leading=25,
            textColor=INK, alignment=TA_LEFT, spaceAfter=2,
        ),
        "subtitlu": ParagraphStyle(
            "subtitlu", parent=baza["Normal"], fontName=FONT_NORMAL, fontSize=10, leading=14, textColor=INK_FAINT,
        ),
        "sectiune": ParagraphStyle(
            "sectiune", parent=baza["Heading2"], fontName=FONT_NORMAL, fontSize=12, leading=16,
            textColor=INK, spaceBefore=14, spaceAfter=6,
        ),
        "corp": ParagraphStyle(
            "corp", parent=baza["Normal"], fontName=FONT_NORMAL, fontSize=9.5, leading=13.5, textColor=INK_SOFT,
        ),
        "celula": ParagraphStyle(
            "celula", parent=baza["Normal"], fontName=FONT_NORMAL, fontSize=8, leading=11, textColor=INK_SOFT,
        ),
        "nota": ParagraphStyle(
            "nota", parent=baza["Normal"], fontName=FONT_NORMAL, fontSize=8.5, leading=12, textColor=INK_FAINT,
        ),
    }


def _antet(raport: Raport, st: dict) -> list:
    return [
        Paragraph("Raport de analiză a tranzacțiilor", st["titlu"]),
        Paragraph(
            f"Generat la {raport.generat_la.strftime('%d.%m.%Y, %H:%M')} UTC · "
            f"perioada analizată: ultimele {raport.zile} de zile",
            st["subtitlu"],
        ),
        Spacer(1, 8 * mm),
    ]


def _tabel_identitate(raport: Raport, st: dict) -> Table:
    randuri = [
        ["Titular", raport.nume],
        ["Email", raport.email],
        ["IBAN", raport.iban],
        ["Tranzacții analizate", str(raport.total_tranzactii)],
    ]
    tabel = Table(randuri, colWidths=[45 * mm, 120 * mm])
    tabel.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), FONT_NORMAL),
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
    randuri = [["Tip semnalare", "Număr"]]
    for tip, cate in sorted(raport.pe_tip.items(), key=lambda x: -x[1]):
        randuri.append([ETICHETE_TIP.get(tip, tip), str(cate)])
    randuri.append(["Total", str(len(raport.constatari))])

    tabel = Table(randuri, colWidths=[120 * mm, 45 * mm])
    tabel.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), FONT_NORMAL),
                ("BACKGROUND", (0, 0), (-1, 0), PRIMARY_50),
                ("TEXTCOLOR", (0, 0), (-1, 0), PRIMARY_600),
                ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
                ("FONTNAME", (0, -1), (-1, -1), FONT_BOLD),
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
    # Praguri pe severitatea 1-100 (BENZI_SEVERITATE din ml/neregularitati.py),
    # nu pe scorul brut de altadata.
    if scor >= 70:
        return DANGER
    if scor >= 45:
        return WARNING
    return INK_SOFT


def _tabel_constatari(raport: Raport, st: dict) -> Table:
    randuri = [["Data", "Comerciant", "Suma", "Tip", "Scor", "Explicatie"]]
    stiluri = [
        ("FONTNAME", (0, 0), (-1, -1), FONT_NORMAL),
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY_50),
        ("TEXTCOLOR", (0, 0), (-1, 0), PRIMARY_600),
        ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
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
        stiluri.append(("FONTNAME", (4, i), (4, i), FONT_BOLD))

    tabel = Table(
        randuri,
        colWidths=[18 * mm, 30 * mm, 20 * mm, 30 * mm, 13 * mm, 54 * mm],
        repeatRows=1,
    )
    tabel.setStyle(TableStyle(stiluri))
    return tabel


def _cum_s_a_calculat(st: dict) -> list:
    """Cum se naste scorul, in cuvinte, pentru cine citeste raportul.

    Pragurile sunt citite din modulul de detectie, nu scrise de mana aici: un
    numar copiat ramane in urma cand cineva schimba regula, iar un raport care
    isi descrie gresit propriul scor e mai rau decat unul care tace.
    """
    from app.ml.neregularitati import (
        BENZI_SEVERITATE,
        FEREASTRA_DUBLARE,
        FEREASTRA_RAFALA,
        PRAG_COMERCIANT_NOU_MULTIPLU,
        PRAG_RAFALA,
    )

    def banda(tip: str) -> str:
        jos, sus, _ = BENZI_SEVERITATE[tip]
        return str(jos) if jos == sus else f"{jos}–{sus}"

    randuri = [
        [
            "Plată dublată",
            f"Două plăți identice la același comerciant în "
            f"{int(FEREASTRA_DUBLARE.total_seconds() // 60)} de minute.",
            banda("plata_dublata"),
        ],
        [
            "Rafală de plăți",
            f"Cel puțin {PRAG_RAFALA} plăți la același comerciant în "
            f"{int(FEREASTRA_RAFALA.total_seconds() // 3600)} de ore.",
            banda("rafala_de_plati"),
        ],
        [
            "Sumă neobișnuită",
            "Cât de departe e suma față de mediana plăților tale la acel "
            "comerciant, măsurată în abateri absolute mediane.",
            banda("suma_neobisnuita"),
        ],
        [
            "Comerciant nou",
            f"Prima plată la un comerciant, de cel puțin "
            f"{PRAG_COMERCIANT_NOU_MULTIPLU:.0f} ori peste plata ta obișnuită.",
            banda("comerciant_nou"),
        ],
        [
            "Tipar neobișnuit",
            "Semnalat de modelul statistic antrenat pe istoricul de plăți, "
            "nu de o regulă scrisă de om.",
            banda("tipar_neobisnuit"),
        ],
    ]

    tabel = Table(
        [["Tip", "Cum se stabilește", "Severitate"], *randuri],
        colWidths=[33 * mm, 107 * mm, 25 * mm],
    )
    tabel.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), FONT_NORMAL),
                ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("BACKGROUND", (0, 0), (-1, 0), PRIMARY_50),
                ("TEXTCOLOR", (0, 0), (-1, 0), PRIMARY_600),
                ("TEXTCOLOR", (0, 1), (-1, -1), INK_SOFT),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (2, 0), (2, -1), "RIGHT"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LINEBELOW", (0, 0), (-1, -1), 0.5, LINE),
            ]
        )
    )

    return [
        Paragraph("Cum a fost calculată severitatea", st["sectiune"]),
        Paragraph(
            "Severitatea merge de la 1 la 100 și <b>nu este un procent și nici o "
            "probabilitate de fraudă</b>. Sistemul nu a văzut niciodată o fraudă "
            "confirmată din care să învețe, deci nu poate estima o astfel de șansă. "
            "E o ordine de prioritate: cu cât numărul e mai mare, cu atât plata iese "
            "mai mult din tiparul obișnuit al acestui cont — comparat cu el însuși, "
            "nu cu alți clienți.",
            st["corp"],
        ),
        Spacer(1, 3 * mm),
        tabel,
        Spacer(1, 3 * mm),
        Paragraph(
            "Fiecare tip are propriul interval, ales după cât de sigură e "
            "constatarea: o dublare confirmată e o certitudine aritmetică și stă sus, "
            "în timp ce un tipar semnalat doar de model rămâne jos, fiindcă e cea mai "
            "slabă dovadă. În interiorul intervalului, poziția e dată de cât de mult "
            "se abate plata de la obișnuit.",
            st["nota"],
        ),
    ]


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
        author="Galaxy Bank",
    )

    povestea: list = [*_antet(raport, st)]
    povestea.append(Paragraph("Contul analizat", st["sectiune"]))
    povestea.append(_tabel_identitate(raport, st))

    if raport.sinteza:
        povestea.append(Paragraph("Sinteză", st["sectiune"]))
        povestea.append(Paragraph(raport.sinteza, st["corp"]))
        povestea.append(Spacer(1, 2 * mm))
        povestea.append(
            Paragraph(
                "Sinteza de mai sus e scrisă de un model de limbaj, pornind de la "
                "constatările din tabel. Faptele pe care se bazează sunt în tabelul de "
                "constatări; în caz de nepotrivire, tabelul are dreptate.",
                st["nota"],
            )
        )

    if not raport.constatari:
        povestea.append(Paragraph("Constatări", st["sectiune"]))
        povestea.append(
            Paragraph(
                "Nicio plată nu a ieșit din tiparul obișnuit al acestui cont în perioada "
                "analizată.",
                st["corp"],
            )
        )
    else:
        povestea.append(Paragraph("Rezumat", st["sectiune"]))
        povestea.append(_tabel_rezumat(raport, st))
        povestea.append(PageBreak())
        povestea.append(Paragraph("Constatări, cea mai gravă prima", st["sectiune"]))
        povestea.append(_tabel_constatari(raport, st))

        if len(raport.constatari) > MAX_RANDURI:
            povestea.append(Spacer(1, 3 * mm))
            povestea.append(
                Paragraph(
                    f"Încă {len(raport.constatari) - MAX_RANDURI} constatări nu încap în "
                    "tabel. Sunt toate în fișierul CSV.",
                    st["nota"],
                )
            )

    povestea.append(Spacer(1, 4 * mm))
    povestea.extend(_cum_s_a_calculat(st))

    povestea.append(Spacer(1, 8 * mm))
    povestea.append(
        KeepTogether(
            Paragraph(
                "<b>Constatările sunt statistice, nu fraude dovedite.</b> Ele arată plăți "
                "care ies din tiparul obișnuit al contului și care merită verificate — "
                "nu stabilesc că s-a întâmplat ceva ilegal. Orice măsură asupra contului "
                "se ia după verificare, nu pe baza acestui raport singur.",
                st["nota"],
            )
        )
    )

    povestea.append(Spacer(1, 4 * mm))
    povestea.append(
        KeepTogether(
            Paragraph(
                "<b>Document generat automat.</b> Constatările din acest raport au fost "
                "produse de reguli statistice și de un model de învățare automată, iar "
                "sinteza de la început a fost scrisă de un model de limbaj. "
                "Niciun operator uman nu a analizat contul înainte de generarea acestui "
                "document și niciun conținut de aici nu reprezintă o decizie a băncii. "
                "Verificarea de către o persoană și orice decizie care decurge din ea "
                "sunt pași separați, ulteriori.",
                st["nota"],
            )
        )
    )

    document.build(povestea)
    return buffer.getvalue()


def nume_fisier(raport: Raport) -> str:
    return f"raport-{raport.id_utilizator[:8]}-{raport.generat_la.date().isoformat()}.pdf"
