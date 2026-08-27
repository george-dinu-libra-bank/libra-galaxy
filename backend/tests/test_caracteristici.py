"""Vectorul de trasaturi: ce vede modelul si ce nu are voie sa vada."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.ml.caracteristici import Plata, vector

START = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)

# Pozitiile din vector, ca testele sa nu depinda de numere magice.
SUMA = 0
RAPORT_COMERCIANT = 1
RAPORT_GENERAL = 2
ZILE_DE_LA_ULTIMA = 3
IN_24H = 4


def _plata(zi: float, suma: float, comerciant: str = "kaufland") -> Plata:
    return Plata(
        id=str(uuid4()),
        moment=START + timedelta(days=zi),
        suma=suma,
        valuta="RON",
        comerciant=comerciant,
        iesire=True,
    )


def test_platile_de_dupa_nu_intra_in_trasaturi() -> None:
    """Altfel modelul ar invata cu un avantaj pe care in productie nu-l are."""
    plata = _plata(10, 100.0)
    viitoare = [_plata(20, 5000.0), _plata(30, 6000.0)]
    anterioare = [_plata(1, 100.0), _plata(2, 100.0)]

    doar_anterioare = vector(plata, anterioare, anterioare)
    cu_viitor = vector(plata, anterioare + viitoare, anterioare + viitoare)

    assert doar_anterioare == cu_viitor


def test_vectorul_nu_contine_ziua_calendaristica() -> None:
    """Ziua din luna si ziua saptamanii au fost scoase: raspund la "cat de rar e
    comerciantul", nu la "cat de neobisnuita e plata", si dilueaza semnalul.

    Doua scenarii identice, decalate cu o zi: acelasi interval fata de plata
    anterioara, aceleasi sume. Daca ziua ar conta, vectorii ar diferi.
    """
    istoric_a = [_plata(0, 100.0)]
    istoric_b = [_plata(1, 100.0)]

    assert vector(_plata(5, 100.0), istoric_a, istoric_a) == vector(
        _plata(6, 100.0), istoric_b, istoric_b
    )


def test_sumele_mici_ies_in_evidenta_fata_de_tiparul_general() -> None:
    """Un sir de plati mici la un comerciant nou isi trage singur mediana in jos.

    Fata de comerciant par normale; fata de cat cheltuie omul de obicei, nu.
    """
    obisnuite = [_plata(i, 100.0, "kaufland") for i in range(10)]
    mici = [_plata(10 + i / 24, 5.0, "digitalgoods") for i in range(5)]
    plata = _plata(10.3, 5.0, "digitalgoods")

    trasaturi = vector(plata, mici, obisnuite + mici)

    assert trasaturi[RAPORT_COMERCIANT] == 1.0  # fata de comerciant, pare normala
    assert trasaturi[RAPORT_GENERAL] < 0.2  # fata de tiparul general, nu


def test_platile_in_rafala_sunt_numarate() -> None:
    """Patru plati intr-o zi la un magazin vizitat saptamanal e un ritm anormal,
    chiar daca fiecare suma in parte e obisnuita."""
    saptamanale = [_plata(i * 7, 50.0) for i in range(6)]
    rafala = [_plata(50 + ora / 24, 50.0) for ora in (0, 2, 4)]
    plata = _plata(50 + 6 / 24, 50.0)

    assert vector(plata, saptamanale, saptamanale)[IN_24H] == 0
    assert vector(plata, saptamanale + rafala, saptamanale + rafala)[IN_24H] == 3


def test_prima_plata_la_un_comerciant_nou_nu_are_istoric() -> None:
    plata = _plata(10, 100.0, "magazin nou")
    altele = [_plata(i, 100.0, "kaufland") for i in range(5)]

    trasaturi = vector(plata, [], altele)

    assert trasaturi[ZILE_DE_LA_ULTIMA] == -1.0
    assert trasaturi[IN_24H] == 0
    assert trasaturi[SUMA] == 100.0
    assert trasaturi[RAPORT_COMERCIANT] == 1.0


def test_fara_referinta_generala_se_foloseste_istoricul() -> None:
    """Apelul cu doua argumente ramane valid, ca sa nu rupem apelurile vechi."""
    istoric = [_plata(i, 100.0) for i in range(5)]
    plata = _plata(10, 100.0)

    assert vector(plata, istoric) == vector(plata, istoric, istoric)


# -- miscarile de credit nu sunt plati ale omului ------------------------------


def test_ratele_de_credit_nu_intra_in_analiza():
    """Le genereaza banca din grafic; omul nu alege cand si cat se ia.

    Cat timp intrau, fiecare rata parea alt comerciant („rata 1/12 credit",
    „rata 2/12 credit"), deci fiecare devenea „prima plata la un comerciant
    nou" — si banca ajungea sa-l intrebe pe client daca a autorizat plata
    propriilor rate.
    """
    from uuid import uuid4
    from app.ml.caracteristici import normalizeaza

    uid = uuid4()
    randuri = [
        {"id": "1", "creat_la": "2026-08-20T10:00:00Z", "suma": 878.69,
         "descriere": "Rata 1/12 credit", "id_user_send": str(uid)},
        {"id": "2", "creat_la": "2026-08-20T10:01:00Z", "suma": 7591.67,
         "descriere": "Rambursare anticipata integrala credit", "id_user_send": str(uid)},
        {"id": "3", "creat_la": "2026-08-20T11:00:00Z", "suma": 155.92,
         "descriere": "Kaufland ref 99929175", "id_user_send": str(uid)},
    ]

    plati = normalizeaza(randuri, uid)

    assert [p.id for p in plati] == ["3"]
    assert plati[0].comerciant == "kaufland"


def test_o_plata_obisnuita_care_contine_cuvantul_credit_ramane():
    """Filtrul e ancorat pe formatul exact al RPC-urilor, nu pe cuvinte."""
    from app.ml.caracteristici import e_miscare_de_credit

    assert e_miscare_de_credit("Rata 3/12 credit")
    assert not e_miscare_de_credit("Credit Suisse ref 1234567")
    assert not e_miscare_de_credit("Rata la sala credit card")
    assert not e_miscare_de_credit(None)


def test_numele_pentru_om_pastreaza_scrierea_si_taie_referinta():
    """In grupare conteaza sa fie acelasi loc; intr-o scrisoare conteaza sa arate bine."""
    from app.ml.caracteristici import comerciant_pentru_om, normalizeaza_comerciant

    assert comerciant_pentru_om("Kaufland ref 99929175") == "Kaufland"
    assert comerciant_pentru_om("Bijuterii Lux ref 91112345") == "Bijuterii Lux"
    assert comerciant_pentru_om(None) == "necunoscut"
    # Gruparea ramane pe litere mici, neschimbata.
    assert normalizeaza_comerciant("Kaufland ref 99929175") == "kaufland"
