"""Raportul ca CSV — datele, pentru prelucrare mai departe."""

import csv
import io

from app.services.raport_service import ETICHETE_TIP, Raport

COLOANE = [
    "data",
    "comerciant",
    "suma",
    "valuta",
    "tip",
    "tip_afisat",
    "scor",
    "explicatie",
    "id_tranzactie",
]


def randeaza(raport: Raport) -> bytes:
    """UTF-8 cu BOM: fara el, Excel pe Windows strica diacriticele."""
    buffer = io.StringIO()
    scriitor = csv.DictWriter(buffer, fieldnames=COLOANE, lineterminator="\n")
    scriitor.writeheader()

    for c in raport.constatari:
        scriitor.writerow(
            {
                "data": c.data,
                "comerciant": c.comerciant,
                "suma": f"{c.suma:.2f}",
                "valuta": c.valuta,
                "tip": c.tip,
                "tip_afisat": ETICHETE_TIP.get(c.tip, c.tip),
                "scor": f"{c.scor:.2f}",
                "explicatie": c.explicatie,
                "id_tranzactie": c.id_tranzactie,
            }
        )

    return buffer.getvalue().encode("utf-8-sig")


def nume_fisier(raport: Raport) -> str:
    return f"raport-{raport.id_utilizator[:8]}-{raport.generat_la.date().isoformat()}.csv"
