"""Contractul de credit: sablon, sanitizare si PDF.

Trei lucruri care par unul singur, dar au granite clare:

1. **Sablonul** (`sablon_din_date`) — HTML completat cu datele clientului si ale
   cererii, asa cum le stie baza. Se genereaza o singura data, la prima
   deschidere a dosarului; de acolo incolo textul apartine analistului.
2. **Sanitizarea** (`sanitizeaza`) — HTML-ul vine dintr-un editor din browser,
   deci e continut neincrezut. Trece printr-o lista de etichete permise inainte
   sa atinga baza. Nimic din afara listei nu supravietuieste.
3. **PDF-ul** (`pdf_din_html`) — la semnatura, textul se ingheata. Acelasi
   subset de etichete se traduce in reportlab, deci ce a citit clientul si ce
   ajunge in arhiva sunt acelasi document.

Lista de etichete e aceeasi in toate trei locurile, si nu din intamplare: e cea
pe care o poate produce editorul, o poate stoca baza si o poate desena
reportlab. Daca se adauga una noua, se adauga in toate.
"""

from __future__ import annotations

import io
import re
from datetime import date, datetime
from decimal import Decimal
from html import escape
from html.parser import HTMLParser

# -----------------------------------------------------------------------------
# Subsetul de HTML
# -----------------------------------------------------------------------------

# Structura de bloc pe care o randeaza si editorul, si PDF-ul.
BLOCURI = ("h1", "h2", "h3", "p", "ul", "ol", "li", "br")
# Marcaje in interiorul unui bloc. `<b>`/`<i>`/`<u>` sunt exact cele pe care le
# produce `document.execCommand` si exact cele pe care le intelege reportlab.
MARCAJE = ("b", "strong", "i", "em", "u")

ETICHETE_PERMISE = frozenset(BLOCURI + MARCAJE)

# Niciun atribut nu trece. Fara `href`, fara `style`, fara `class`: un contract
# nu are nevoie de ele, iar fiecare atribut permis e o cale in plus de verificat.
ATRIBUTE_PERMISE: frozenset[str] = frozenset()

_ETICHETE_GOALE = frozenset({"br"})

# Etichete al caror *continut* se arunca, nu doar eticheta. Pentru un `<div>`
# pastram textul dinauntru (o clauza nu trebuie sa dispara fiindca editorul a
# invelit-o); pentru astea, textul dinauntru e cod, nu contract.
_CU_TOT_CU_CONTINUT = frozenset({"script", "style", "noscript", "iframe", "object", "template"})


class _Curatator(HTMLParser):
    """Reconstruieste HTML-ul pastrand doar ce e in `ETICHETE_PERMISE`.

    Textul din interiorul unei etichete respinse se pastreaza — un `<div>` in
    plus nu trebuie sa inghita o clauza. Se pierde doar eticheta.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._bucati: list[str] = []
        self._deschise: list[str] = []
        self._mut = 0

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001 - semnatura HTMLParser
        if tag in _CU_TOT_CU_CONTINUT:
            self._mut += 1
            return
        if self._mut or tag not in ETICHETE_PERMISE:
            return
        if tag in _ETICHETE_GOALE:
            self._bucati.append(f"<{tag}>")
            return
        self._deschise.append(tag)
        self._bucati.append(f"<{tag}>")

    def handle_startendtag(self, tag: str, attrs) -> None:  # noqa: ANN001
        if not self._mut and tag in _ETICHETE_GOALE:
            self._bucati.append(f"<{tag}>")

    def handle_endtag(self, tag: str) -> None:
        if tag in _CU_TOT_CU_CONTINUT:
            self._mut = max(0, self._mut - 1)
            return
        if self._mut or tag not in ETICHETE_PERMISE or tag in _ETICHETE_GOALE:
            return
        # Inchidem si etichetele ramase deschise peste ea: un `</p>` care vine
        # peste un `<b>` nedeschis corect nu trebuie sa scoata iesirea din
        # echilibru.
        if tag not in self._deschise:
            return
        while self._deschise:
            deschisa = self._deschise.pop()
            self._bucati.append(f"</{deschisa}>")
            if deschisa == tag:
                break

    def handle_data(self, data: str) -> None:
        if self._mut:
            return
        self._bucati.append(escape(data, quote=False))

    def rezultat(self) -> str:
        while self._deschise:
            self._bucati.append(f"</{self._deschise.pop()}>")
        return "".join(self._bucati)


def sanitizeaza(html: str) -> str:
    """Curata HTML-ul primit din editor. Singura poarta catre baza."""
    curatator = _Curatator()
    curatator.feed(html or "")
    curatator.close()
    curat = curatator.rezultat()
    # Spatiile multiple si randurile goale vin din editor la fiecare salvare si
    # ar face fiecare diff ilizibil.
    curat = re.sub(r"[ \t]+", " ", curat)
    curat = re.sub(r"(<br>\s*){3,}", "<br><br>", curat)
    return curat.strip()


def are_continut(html: str | None) -> bool:
    """Spune daca a ramas text dupa ce se scot etichetele.

    `<p></p><p><br></p>` e HTML valid si complet gol; fara verificarea asta un
    contract „completat" din trei paragrafe goale ar putea ajunge la client.
    """
    fara_etichete = re.sub(r"<[^>]+>", "", html or "")
    return bool(fara_etichete.replace("\xa0", " ").strip())


# -----------------------------------------------------------------------------
# Sablonul
# -----------------------------------------------------------------------------

LUNI_RO = (
    "ianuarie", "februarie", "martie", "aprilie", "mai", "iunie",
    "iulie", "august", "septembrie", "octombrie", "noiembrie", "decembrie",
)


def _suma(valoare) -> str:
    """1250.5 -> '1.250,50 RON' (DESIGN.md 11)."""
    numar = Decimal(str(valoare or 0)).quantize(Decimal("0.01"))
    intreg, zecimale = f"{numar:.2f}".split(".")
    negativ = intreg.startswith("-")
    intreg = intreg.lstrip("-")
    grupuri = []
    while len(intreg) > 3:
        grupuri.insert(0, intreg[-3:])
        intreg = intreg[:-3]
    grupuri.insert(0, intreg)
    return f"{'-' if negativ else ''}{'.'.join(grupuri)},{zecimale} RON"


def _procent(valoare) -> str:
    if valoare is None:
        return "—"
    return f"{Decimal(str(valoare)) * 100:.2f}".replace(".", ",") + "%"


def _iban_grupat(iban: str | None) -> str:
    """RO49AAAA... -> 'RO49 AAAA ...' (DESIGN.md 11)."""
    curat = re.sub(r"\s+", "", iban or "")
    return " ".join(curat[i:i + 4] for i in range(0, len(curat), 4)) or "—"


def _data_lunga(moment: date | datetime | str | None) -> str:
    if moment is None:
        return "—"
    if isinstance(moment, str):
        try:
            moment = datetime.fromisoformat(moment.replace("Z", "+00:00"))
        except ValueError:
            return moment
    return f"{moment.day} {LUNI_RO[moment.month - 1]} {moment.year}"


def sablon_din_date(
    *,
    profil: dict,
    cerere: dict,
    produs: dict,
    astazi: date | None = None,
) -> str:
    """Contractul completat cu ce stie baza, gata de editat de analist.

    CNP-ul apare intreg, spre deosebire de restul aplicatiei (DESIGN.md 11 cere
    mascarea lui): intr-un contract de credit partile trebuie identificate
    complet, altfel documentul nu inseamna nimic. Textul nu ajunge la client
    decat dupa ce analistul apasa „Aproba", si sta intr-un bucket privat.
    """
    astazi = astazi or date.today()
    nume = escape(str(profil.get("nume") or "—"))
    cnp = escape(str(profil.get("cnp") or "—"))
    adresa_email = escape(str(profil.get("email") or "—"))
    telefon = escape(str(profil.get("telefon") or "—"))
    iban = escape(_iban_grupat(profil.get("iban_cont")))

    suma = _suma(cerere.get("suma_ceruta"))
    luni = int(cerere.get("luni") or 0)
    rata = _suma(cerere.get("rata_lunara")) if cerere.get("rata_lunara") else "—"
    dae = _procent(cerere.get("dae"))
    dobanda = _procent(produs.get("dobanda_anuala"))
    nume_produs = escape(str(produs.get("nume") or "Credit de nevoi personale"))
    scop = escape(str(cerere.get("scop") or "nevoi personale"))
    total = _suma(
        Decimal(str(cerere.get("rata_lunara") or 0)) * luni
    ) if cerere.get("rata_lunara") else "—"

    return f"""<h1>Contract de credit — {nume_produs}</h1>
<p>Încheiat astăzi, {_data_lunga(astazi)}, între:</p>
<p><b>Galaxy Bank S.A.</b>, denumită în continuare <b>Banca</b>, și</p>
<p><b>{nume}</b>, CNP {cnp}, telefon {telefon}, email {adresa_email}, titular al contului
{iban}, denumit în continuare <b>Împrumutatul</b>.</p>

<h2>1. Obiectul contractului</h2>
<p>Banca acordă Împrumutatului un credit de <b>{suma}</b>, pe o perioadă de
<b>{luni} luni</b>, cu destinația: {scop}.</p>

<h2>2. Costurile creditului</h2>
<ul>
<li>Dobândă anuală fixă: <b>{dobanda}</b></li>
<li>Dobândă anuală efectivă (DAE): <b>{dae}</b></li>
<li>Rata lunară: <b>{rata}</b></li>
<li>Total de plată pe durata contractului: <b>{total}</b></li>
</ul>
<p>Rata lunară este fixă pe toată durata contractului. Nu se percep comisioane
de administrare, de analiză a dosarului sau de rambursare anticipată.</p>

<h2>3. Punerea la dispoziție a sumei</h2>
<p>Suma se virează integral, în lei, în contul indicat de Împrumutat la momentul
semnării, în aceeași zi cu semnarea prezentului contract.</p>

<h2>4. Rambursarea</h2>
<p>Împrumutatul rambursează creditul în {luni} rate lunare egale, conform
graficului de rambursare care face parte integrantă din prezentul contract.
Fiecare rată se încasează automat din contul indicat, la data scadenței.</p>
<p>Împrumutatul poate rambursa anticipat, integral sau parțial, oricând, fără
niciun cost suplimentar. Rambursarea anticipată reduce soldul și, implicit,
dobânda datorată în continuare.</p>

<h2>5. Întârzierea la plată</h2>
<p>Dacă la data scadenței contul nu acoperă rata, creditul trece în stare de
restanță. Banca îl anunță pe Împrumutat și încearcă din nou încasarea la
alimentarea contului.</p>

<h2>6. Protecția datelor</h2>
<p>Datele din prezentul contract sunt prelucrate exclusiv pentru administrarea
creditului, pe durata contractului și în termenele de arhivare prevăzute de
lege. Împrumutatul își poate exercita oricând drepturile prevăzute de
Regulamentul (UE) 2016/679.</p>

<h2>7. Dispoziții finale</h2>
<p>Prezentul contract se semnează electronic, prin acceptarea lui în aplicația
Galaxy Bank. Momentul semnării, contul ales și confirmarea citirii se
înregistrează și fac dovada acordului Împrumutatului.</p>
<p><i>Document generat automat din datele dosarului. Verifică-l și
completează-l înainte de a-l trimite clientului.</i></p>"""


# -----------------------------------------------------------------------------
# PDF
# -----------------------------------------------------------------------------

def cale_in_bucket(id_user: str, id_cerere: str, moment: datetime) -> str:
    """Calea din `credit-documente`.

    Primul segment e id-ul utilizatorului: asa cere politica de storage din
    migratia 0009 („fiecare om doar in folderul lui").
    """
    marca = moment.strftime("%Y%m%d%H%M%S")
    return f"{id_user}/contracte/contract-{id_cerere}-{marca}.pdf"


class _Bloc:
    """Un paragraf de randat: stilul si textul lui, deja in dialectul reportlab."""

    __slots__ = ("stil", "text", "marcaj")

    def __init__(self, stil: str, text: str, marcaj: str = "") -> None:
        self.stil = stil
        self.text = text
        self.marcaj = marcaj


_STIL_DUPA_ETICHETA = {"h1": "titlu", "h2": "sectiune", "h3": "subsectiune", "p": "corp"}


class _Extractor(HTMLParser):
    """Sparge HTML-ul sanitizat in blocuri pe care le poate desena reportlab.

    reportlab intelege `<b>`, `<i>`, `<u>` si `<br/>` in interiorul unui
    `Paragraph`, dar nu are notiunea de titlu sau de lista: alea devin blocuri
    separate, cu stil propriu si, la liste, cu bulina scrisa in text.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocuri: list[_Bloc] = []
        self._stil = "corp"
        self._bucati: list[str] = []
        self._in_lista_ordonata = False
        self._numar_element = 0

    def _inchide(self, marcaj: str = "") -> None:
        text = "".join(self._bucati).strip()
        self._bucati = []
        if text:
            self.blocuri.append(_Bloc(self._stil, text, marcaj))

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001
        if tag in _STIL_DUPA_ETICHETA:
            self._inchide()
            self._stil = _STIL_DUPA_ETICHETA[tag]
        elif tag == "ol":
            self._inchide()
            self._in_lista_ordonata = True
            self._numar_element = 0
        elif tag == "ul":
            self._inchide()
            self._in_lista_ordonata = False
        elif tag == "li":
            self._inchide()
            self._stil = "element"
            self._numar_element += 1
        elif tag in MARCAJE:
            self._bucati.append("<b>" if tag in ("b", "strong") else
                                "<i>" if tag in ("i", "em") else "<u>")
        elif tag == "br":
            self._bucati.append("<br/>")

    def handle_startendtag(self, tag: str, attrs) -> None:  # noqa: ANN001
        if tag == "br":
            self._bucati.append("<br/>")

    def handle_endtag(self, tag: str) -> None:
        if tag in _STIL_DUPA_ETICHETA:
            self._inchide()
            self._stil = "corp"
        elif tag == "li":
            marcaj = f"{self._numar_element}." if self._in_lista_ordonata else "•"
            self._inchide(marcaj)
            self._stil = "corp"
        elif tag in ("ul", "ol"):
            self._inchide()
            self._in_lista_ordonata = False
        elif tag in MARCAJE:
            self._bucati.append("</b>" if tag in ("b", "strong") else
                                "</i>" if tag in ("i", "em") else "</u>")

    def handle_data(self, data: str) -> None:
        self._bucati.append(escape(data, quote=False))

    def rezultat(self) -> list[_Bloc]:
        self._inchide()
        return self.blocuri


def pdf_din_html(
    html: str,
    *,
    nume_client: str,
    semnat_la: datetime,
    referinta: str,
) -> bytes:
    """Ingheata contractul intr-un PDF.

    `referinta` e id-ul cererii: apare in subsol, ca documentul sa poata fi legat
    de dosar si dupa ce iese din aplicatie.
    """
    from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    from app.rapoarte import fonturi

    font_normal, font_bold = fonturi.inregistreaza()

    # DESIGN.md, sectiunea 2 — aceleasi culori ca in aplicatie.
    ink = colors.HexColor("#0F1B33")
    ink_soft = colors.HexColor("#4A5773")
    ink_faint = colors.HexColor("#8A96AE")
    primary = colors.HexColor("#2F6FED")

    baza = getSampleStyleSheet()
    stiluri = {
        "titlu": ParagraphStyle(
            "titlu", parent=baza["Title"], fontName=font_bold, fontSize=17, leading=22,
            textColor=ink, alignment=TA_LEFT, spaceAfter=10,
        ),
        "sectiune": ParagraphStyle(
            "sectiune", parent=baza["Heading2"], fontName=font_bold, fontSize=11.5,
            leading=15, textColor=primary, spaceBefore=12, spaceAfter=4,
        ),
        "subsectiune": ParagraphStyle(
            "subsectiune", parent=baza["Heading3"], fontName=font_bold, fontSize=10,
            leading=14, textColor=ink, spaceBefore=8, spaceAfter=3,
        ),
        "corp": ParagraphStyle(
            "corp", parent=baza["Normal"], fontName=font_normal, fontSize=9.5,
            leading=14, textColor=ink_soft, alignment=TA_JUSTIFY, spaceAfter=5,
        ),
        "element": ParagraphStyle(
            "element", parent=baza["Normal"], fontName=font_normal, fontSize=9.5,
            leading=14, textColor=ink_soft, leftIndent=10 * mm, spaceAfter=3,
        ),
        "subsol": ParagraphStyle(
            "subsol", parent=baza["Normal"], fontName=font_normal, fontSize=8,
            leading=11, textColor=ink_faint,
        ),
    }

    extractor = _Extractor()
    extractor.feed(html or "")
    extractor.close()

    povestea = []
    for bloc in extractor.rezultat():
        text = f"{bloc.marcaj} {bloc.text}" if bloc.marcaj else bloc.text
        povestea.append(Paragraph(text, stiluri[bloc.stil]))

    povestea.append(Spacer(1, 10 * mm))
    semnatura = Table(
        [
            [Paragraph("<b>Galaxy Bank S.A.</b>", stiluri["corp"]),
             Paragraph(f"<b>{escape(nume_client)}</b>", stiluri["corp"])],
            [Paragraph("prin serviciul de creditare", stiluri["subsol"]),
             Paragraph(
                 "semnat electronic la "
                 + semnat_la.strftime("%d.%m.%Y, ora %H:%M"),
                 stiluri["subsol"],
             )],
        ],
        colWidths=[80 * mm, 80 * mm],
    )
    semnatura.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LINEABOVE", (0, 0), (-1, 0), 0.5, colors.HexColor("#E3E9F2")),
    ]))
    povestea.append(semnatura)
    povestea.append(Spacer(1, 6 * mm))
    povestea.append(Paragraph(f"Dosar {escape(referinta)}", stiluri["subsol"]))

    tampon = io.BytesIO()
    document = SimpleDocTemplate(
        tampon, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
        title=f"Contract de credit — {nume_client}",
        author="Galaxy Bank",
    )
    document.build(povestea)
    return tampon.getvalue()
