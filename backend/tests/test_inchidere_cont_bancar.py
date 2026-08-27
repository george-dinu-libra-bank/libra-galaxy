"""Cererea de inchidere a unui CONT BANCAR, partea de backend.

Alta operatiune decat `test_stergere_cont.py`, si se confunda usor: acolo pleaca
omul din banca, aici se inchide un singur cont bancar si omul ramane client.

Ce se apara aici e forma in care cererea ajunge la analist. Garzile propriu-zise
— contul principal, contul blocat, soldul negativ, destinatia invalida — stau in
`public.inchide_cont_bancar` (0040) si se verifica acolo, intr-o singura
tranzactie cu mutarea banilor. Un buton dezactivat e o sugestie; o exceptie din
RPC e o regula.
"""

from __future__ import annotations

from app.repositories.admin_repository import AdminRepository

IBAN_PRINCIPAL = "RO49LIBR1510142598441132"


def _cont(**camp) -> dict:
    baza = {
        "id": "11111111-1111-4111-8111-111111111111",
        "id_user": "5f801e91-0fd4-462f-a78c-61ec1d6dc12b",
        "nume": "Vacanta",
        "iban": "RO41LIBR1941724156110784",
        "sold": "340.00",
        "valuta": "RON",
        "blocat_administrativ": False,
        "inchis_la": None,
    }
    baza.update(camp)
    return baza


def test_contul_principal_se_recunoaste_dupa_iban_nu_dupa_pozitie() -> None:
    """Aceeasi regula ca in interfata si in RPC: contul principal e cel al carui
    IBAN sta in `profiles.iban_cont`. Ordinea din lista nu spune nimic."""
    principal = AdminRepository._cont_admin(_cont(iban=IBAN_PRINCIPAL), IBAN_PRINCIPAL)
    secundar = AdminRepository._cont_admin(_cont(), IBAN_PRINCIPAL)

    assert principal["este_principal"] is True
    assert secundar["este_principal"] is False


def test_fara_iban_principal_niciun_cont_nu_e_marcat() -> None:
    """Un profil fara `iban_cont` nu trebuie sa faca primul cont sa para
    principal — mai bine niciunul decat unul gresit."""
    cont = AdminRepository._cont_admin(_cont(), None)

    assert cont["este_principal"] is False


def test_contul_inchis_se_vede_ca_inchis() -> None:
    inchis = AdminRepository._cont_admin(_cont(inchis_la="2026-08-26T10:00:00+00:00"), None)
    deschis = AdminRepository._cont_admin(_cont(), None)

    assert inchis["inchis"] is True
    assert deschis["inchis"] is False


def test_soldul_ajunge_ca_text_nu_ca_float() -> None:
    """Soldurile sunt `numeric(14,2)`. Trecerea prin float ar rotunji tacit sume
    pe care un analist le compara cu ce vede clientul pe ecran."""
    cont = AdminRepository._cont_admin(_cont(sold="1234.56"), None)

    assert cont["sold"] == "1234.56"
    assert isinstance(cont["sold"], str)


def test_soldul_lipsa_devine_zero_nu_none() -> None:
    cont = AdminRepository._cont_admin(_cont(sold=None), None)

    assert cont["sold"] == "0"
