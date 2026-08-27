"""Trasatura de loc: platile venite dintr-un IP nemaivazut.

Deciziile care conteaza aici nu sunt despre IP-uri, ci despre ce inseamna
absenta lor — pe datele de azi, aproape nimic nu are IP.
"""

from datetime import datetime, timedelta, timezone

from app.ml.caracteristici import Plata, loc_nou, vector

ACUM = datetime(2026, 8, 27, 12, 0, tzinfo=timezone.utc)


def _plata(minute_in_urma: float = 0, ip: str | None = None, suma: float = 100.0) -> Plata:
    return Plata(
        id=f"p{minute_in_urma}-{ip}",
        moment=ACUM - timedelta(minutes=minute_in_urma),
        suma=suma,
        valuta="RON",
        comerciant="kaufland",
        iesire=True,
        ip=ip,
    )


def test_un_ip_nemaivazut_e_semnalat() -> None:
    istoric = [_plata(60, "86.120.1.1"), _plata(30, "86.120.1.1")]

    assert loc_nou(_plata(0, "203.0.113.9"), istoric) == 1.0


def test_un_ip_cunoscut_nu_e_semnalat() -> None:
    istoric = [_plata(60, "86.120.1.1"), _plata(30, "203.0.113.9")]

    assert loc_nou(_plata(0, "203.0.113.9"), istoric) == 0.0


def test_fara_ip_nu_se_inventeaza_un_semnal() -> None:
    """Lipsa IP-ului e o lipsa a noastra, nu un fapt despre plata."""
    istoric = [_plata(60, "86.120.1.1")]

    assert loc_nou(_plata(0, None), istoric) == 0.0


def test_primul_ip_al_unui_om_nu_e_nou() -> None:
    """Altfel fiecare client ar fi semnalat la prima plata de dupa capturare."""
    istoric = [_plata(60, None), _plata(30, None)]

    assert loc_nou(_plata(0, "86.120.1.1"), istoric) == 0.0


def test_o_plata_ulterioara_nu_face_ip_ul_cunoscut() -> None:
    """Viitorul nu exista la inferenta; nici la antrenare nu are voie sa existe.

    Aici omul are istoric — de la alt IP — deci comparatia se poate face. Faptul
    ca acelasi IP apare mai tarziu nu are voie sa il faca „stiut" acum.
    """
    istoric = [_plata(60, "86.120.1.1"), _plata(-30, "203.0.113.9")]

    assert loc_nou(_plata(0, "203.0.113.9"), istoric) == 1.0


def test_fara_niciun_ip_anterior_nu_se_poate_judeca() -> None:
    """Nici „nou", nici „cunoscut": pur si simplu nu exista cu ce compara."""
    doar_viitor = [_plata(-30, "203.0.113.9")]

    assert loc_nou(_plata(0, "203.0.113.9"), doar_viitor) == 0.0


def test_vectorul_are_sase_trasaturi() -> None:
    """Antrenarea si inferenta folosesc acelasi `vector`; daca lungimea se
    schimba intr-o parte si nu in cealalta, modelul primeste altceva decat a
    invatat."""
    istoric = [_plata(60), _plata(45), _plata(30), _plata(15)]

    assert len(vector(_plata(0), istoric, istoric)) == 6


def test_trasatura_de_loc_e_ultima_in_vector() -> None:
    """Ordinea e contractul dintre antrenare si inferenta."""
    istoric = [_plata(60, "86.120.1.1"), _plata(45, "86.120.1.1"),
               _plata(30, "86.120.1.1"), _plata(15, "86.120.1.1")]

    assert vector(_plata(0, "203.0.113.9"), istoric, istoric)[-1] == 1.0
    assert vector(_plata(0, "86.120.1.1"), istoric, istoric)[-1] == 0.0
