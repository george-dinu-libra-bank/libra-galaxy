"""Fluxul investigatiei de frauda: masina de stari si cei trei agenti.

Modelul si baza de date sunt inlocuite cu duble. Ce se verifica aici e ordinea
pasilor si granitele — cine are voie sa faca ce — nu inspiratia modelului.
"""

import pytest

from app.agents.caz.extractor import ExtractorCaz, _curata
from app.agents.caz.fapte import FapteCaz, TranzactieCaz
from app.core.errors import ResourceNotFoundError, ValidationError
from app.services.caz_service import (
    CazService,
    _fara_raspuns,
    _prenume_din,
    _verifica_tranzitie,
)

ADMIN = "11111111-1111-1111-1111-111111111111"
CLIENT = "22222222-2222-2222-2222-222222222222"
STRAIN = "33333333-3333-3333-3333-333333333333"


# -- duble ---------------------------------------------------------------------


class CazuriFalse:
    """Tine cazurile si mesajele in memorie, cu aceleasi metode ca depozitul real."""

    def __init__(self) -> None:
        self.cazuri: dict[str, dict] = {}
        self.mesaje: list[dict] = []
        self.legaturi: list[dict] = []
        self._n = 0

    async def creeaza(self, campuri: dict) -> dict:
        self._n += 1
        rand = {
            "id": f"caz-{self._n}",
            "stare": "nou",
            "rezultat": None,
            "inchis_la": None,
            "deschis_la": "2026-08-27T10:00:00Z",
            **campuri,
        }
        self.cazuri[rand["id"]] = rand
        return rand

    async def caz(self, id_caz):
        return self.cazuri.get(str(id_caz))

    async def deschis_pentru(self, user_id):
        for c in self.cazuri.values():
            if c["id_utilizator"] == str(user_id) and c["stare"] not in (
                "rezolvat",
                "escalat",
                "inchis",
            ):
                return c
        return None

    async def ale_utilizatorului(self, user_id, limita=20):
        return [c for c in self.cazuri.values() if c["id_utilizator"] == str(user_id)]

    async def coada(self, doar_deschise=True, limita=200):
        return list(self.cazuri.values())

    async def schimba_starea(self, id_caz, stare, rezultat=None, inchide=False):
        c = self.cazuri[str(id_caz)]
        c["stare"] = stare
        if rezultat is not None:
            c["rezultat"] = rezultat
        if inchide:
            c["inchis_la"] = "2026-08-27T12:00:00Z"
        return c

    async def leaga_tranzactii(self, id_caz, tranzactii):
        self.legaturi.extend({"id_caz": str(id_caz), **t} for t in tranzactii)
        return len(tranzactii)

    async def tranzactiile(self, id_caz):
        return [
            {
                "motiv": "suma neobisnuita",
                "id_tranzactie": "t1",
                "tranzactii": {
                    "id": "t1",
                    "suma": 4200.0,
                    "valuta": "RON",
                    "descriere": "MagazinX",
                    "creat_la": "2026-08-20T09:30:00Z",
                },
            }
        ]

    async def adauga_mesaj(self, campuri: dict) -> dict:
        rand = {
            "id": f"mesaj-{len(self.mesaje) + 1}",
            "structura": {},
            "propus_de_agent": False,
            "editat_de_om": False,
            "creat_la": f"2026-08-27T1{len(self.mesaje)}:00:00Z",
            **campuri,
        }
        self.mesaje.append(rand)
        return rand

    async def mesajele(self, id_caz, limita=200):
        return [m for m in self.mesaje if m["id_caz"] == str(id_caz)]


class AnalizeFalse:
    def __init__(self, blocat: bool = True) -> None:
        self._blocat = blocat
        self.notificari: list[tuple] = []

    async def conturi(self, user_id):
        return [{"id": "c1", "blocat_administrativ": self._blocat}]

    async def scrie_notificare(self, user_id, titlu, mesaj, tip):
        self.notificari.append((str(user_id), titlu, tip))
        return {"id": "n1"}


class ProfiluriFalse:
    # Ordinea e cea ceruta de formularul de inregistrare: „Nume si prenume".
    async def profil(self, user_id):
        return {"id": str(user_id), "nume": "Popescu Andrei"}


class RedactorFals:
    def __init__(self, text: str = "Buna ziua, Andrei, ...") -> None:
        self.text = text
        self.fapte_primite: list[FapteCaz] = []

    async def propune(self, fapte: FapteCaz) -> str:
        self.fapte_primite.append(fapte)
        return self.text


class ExtractorFals:
    def __init__(self, campuri=()) -> None:
        self.campuri = campuri
        self.intrebari_primite = None

    async def extrage(self, intrebari, raspuns_client):
        self.intrebari_primite = intrebari
        return self.campuri


class AnalistFals:
    def __init__(self, text: str = "Clientul sustine ca nu a facut platile.") -> None:
        self.text = text
        self.chemat = False

    async def rezuma(self, fapte, raspuns) -> str:
        self.chemat = True
        return self.text


def _serviciu(**peste) -> tuple[CazService, CazuriFalse, AnalizeFalse]:
    cazuri = CazuriFalse()
    analize = AnalizeFalse()
    serviciu = CazService(
        cazuri,
        analize,
        ProfiluriFalse(),
        redactor=peste.get("redactor", RedactorFals()),
        extractor=peste.get("extractor", ExtractorFals()),
        analist=peste.get("analist", AnalistFals()),
    )
    return serviciu, cazuri, analize


async def _pana_la_raspuns(serviciu, cazuri) -> str:
    caz = await serviciu.deschide(ADMIN, CLIENT, "plati neobisnuite")
    await serviciu.trimite_mesaj(
        caz["id"], ADMIN, "Buna ziua, ...", ["Ai facut tu platile?"]
    )
    return caz["id"]


# -- masina de stari -----------------------------------------------------------


def test_tranzitiile_finale_sunt_fundaturi():
    """Un caz inchis ramane inchis: nimic nu pleaca din starile finale."""
    for stare in ("rezolvat", "escalat", "inchis"):
        with pytest.raises(ValidationError):
            _verifica_tranzitie(stare, "in_analiza")


def test_clientul_nu_poate_raspunde_inainte_sa_fie_intrebat():
    """Fara un mesaj trimis, cazul e 'nou' si nu accepta raspuns."""
    with pytest.raises(ValidationError):
        _verifica_tranzitie("nou", "client_a_raspuns")


@pytest.mark.anyio
async def test_al_doilea_caz_il_intoarce_pe_primul():
    """Doua cazuri deschise pe acelasi om ar insemna doua fire de discutie."""
    serviciu, cazuri, _ = _serviciu()

    unu = await serviciu.deschide(ADMIN, CLIENT, "plati neobisnuite")
    doi = await serviciu.deschide(ADMIN, CLIENT, "alt motiv")

    assert unu["id"] == doi["id"]
    assert len(cazuri.cazuri) == 1


@pytest.mark.anyio
async def test_platile_pleaca_odata_cu_investigatia():
    """Fara ele, redactorul n-are ce cita si scrie un mesaj vag."""
    serviciu, cazuri, _ = _serviciu()

    await serviciu.deschide(
        ADMIN,
        CLIENT,
        "plati neobisnuite",
        tranzactii=[
            {"id_tranzactie": "t1", "motiv": "Sumă neobișnuită"},
            {"id_tranzactie": "t2", "motiv": "Rafală de plăți"},
        ],
    )

    assert [l["id_tranzactie"] for l in cazuri.legaturi] == ["t1", "t2"]


@pytest.mark.anyio
async def test_aceeasi_plata_semnalata_de_doua_ori_nu_darama_deschiderea():
    """Cheia primara e (id_caz, id_tranzactie): un duplicat ar pica tot insertul."""
    serviciu, cazuri, _ = _serviciu()

    await serviciu.deschide(
        ADMIN,
        CLIENT,
        "plati neobisnuite",
        tranzactii=[
            {"id_tranzactie": "t1", "motiv": "Sumă neobișnuită"},
            {"id_tranzactie": "t1", "motiv": "Rafală de plăți"},
        ],
    )

    assert len(cazuri.legaturi) == 1
    # Se păstrează primul motiv: constatările vin ordonate după scor.
    assert cazuri.legaturi[0]["motiv"] == "Sumă neobișnuită"


@pytest.mark.anyio
async def test_cazul_ramane_chiar_daca_legarea_platilor_pica():
    """Mai bine o investigație fără listă de plăți decât un ecran de eroare."""
    cazuri = CazuriFalse()

    async def leaga_si_pica(id_caz, tranzactii):
        raise RuntimeError("cheia straina a refuzat")

    cazuri.leaga_tranzactii = leaga_si_pica  # type: ignore[method-assign]
    serviciu = CazService(cazuri, AnalizeFalse(), ProfiluriFalse())

    caz = await serviciu.deschide(
        ADMIN, CLIENT, "plati neobisnuite", tranzactii=[{"id_tranzactie": "t1"}]
    )

    assert caz["id"] in cazuri.cazuri


@pytest.mark.anyio
async def test_trimiterea_muta_cazul_si_anunta_clientul():
    serviciu, cazuri, analize = _serviciu()
    caz = await serviciu.deschide(ADMIN, CLIENT, "plati neobisnuite")

    await serviciu.trimite_mesaj(caz["id"], ADMIN, "Buna ziua, ...", ["Ai facut tu platile?"])

    assert cazuri.cazuri[caz["id"]]["stare"] == "asteptam_clientul"
    assert analize.notificari and analize.notificari[0][0] == CLIENT


@pytest.mark.anyio
async def test_intrebarile_raman_pe_mesajul_care_le_a_pus():
    """Extractorul le ia de acolo cand vine raspunsul — fara tabela separata."""
    serviciu, cazuri, _ = _serviciu()
    caz = await serviciu.deschide(ADMIN, CLIENT, "plati neobisnuite")

    await serviciu.trimite_mesaj(
        caz["id"], ADMIN, "Buna ziua, ...", ["Ai facut tu platile?", "Ai fost in strainatate?"]
    )

    banca = [m for m in cazuri.mesaje if m["autor"] == "banca"][0]
    assert banca["structura"]["intrebari"] == [
        "Ai facut tu platile?",
        "Ai fost in strainatate?",
    ]


# -- granite -------------------------------------------------------------------


@pytest.mark.anyio
async def test_un_strain_nu_poate_raspunde_in_dosarul_altuia():
    """Si nu afla nici macar ca dosarul exista."""
    serviciu, cazuri, _ = _serviciu()
    id_caz = await _pana_la_raspuns(serviciu, cazuri)

    with pytest.raises(ResourceNotFoundError):
        await serviciu.primeste_raspuns(id_caz, STRAIN, "nu am facut eu nimic")


@pytest.mark.anyio
async def test_clientul_nu_vede_mesajele_interne():
    """Analiza si citirea structurata sunt scrise pentru administrator."""
    serviciu, cazuri, _ = _serviciu()
    id_caz = await _pana_la_raspuns(serviciu, cazuri)
    await serviciu.primeste_raspuns(id_caz, CLIENT, "nu am facut eu platile")

    dosar = await serviciu.dosar(id_caz)
    fir = await serviciu.dosarul_clientului(id_caz, CLIENT)

    assert any(m["autor"] == "sistem" for m in dosar["mesaje"])
    assert all(m["autor"] != "sistem" for m in fir["mesaje"])


@pytest.mark.anyio
async def test_inchiderea_nu_atinge_conturile():
    """Deblocarea ramane o apasare separata, in ecranul contului.

    Contul e blocat inainte, si trebuie sa ramana blocat dupa ce cazul s-a
    inchis cu urmarea 'deblocat' — altfel masura ar deveni efectul secundar al
    unui formular.
    """
    serviciu, cazuri, analize = _serviciu()
    id_caz = await _pana_la_raspuns(serviciu, cazuri)

    await serviciu.inchide(id_caz, ADMIN, "deblocat", "clientul a lamurit situatia")

    assert cazuri.cazuri[id_caz]["stare"] == "rezolvat"
    assert cazuri.cazuri[id_caz]["rezultat"] == "deblocat"
    conturi = await analize.conturi(CLIENT)
    assert conturi[0]["blocat_administrativ"] is True


@pytest.mark.anyio
async def test_urmarea_catre_conformitate_escaladeaza():
    """'anaf' inseamna predat conformitatii, deci escalat, nu rezolvat."""
    serviciu, cazuri, _ = _serviciu()
    id_caz = await _pana_la_raspuns(serviciu, cazuri)

    await serviciu.inchide(id_caz, ADMIN, "anaf")

    assert cazuri.cazuri[id_caz]["stare"] == "escalat"


# -- agentii -------------------------------------------------------------------


@pytest.mark.anyio
async def test_pregatirea_nu_scrie_nimic_in_dosar():
    """Propunerea redactorului e doar text pe ecranul administratorului."""
    serviciu, cazuri, _ = _serviciu()
    caz = await serviciu.deschide(ADMIN, CLIENT, "plati neobisnuite")

    propus = await serviciu.pregateste_mesaj(caz["id"], ["Ai facut tu platile?"])

    assert propus.scris_de_agent is True
    assert cazuri.mesaje == []
    assert cazuri.cazuri[caz["id"]]["stare"] == "nou"


@pytest.mark.anyio
async def test_fluxul_merge_si_fara_agenti():
    """Fara model configurat, administratorul scrie singur si citeste singur."""
    cazuri = CazuriFalse()
    serviciu = CazService(cazuri, AnalizeFalse(), ProfiluriFalse())

    caz = await serviciu.deschide(ADMIN, CLIENT, "plati neobisnuite")
    propus = await serviciu.pregateste_mesaj(caz["id"], ["Ai facut tu platile?"])
    await serviciu.trimite_mesaj(caz["id"], ADMIN, "scris de mine", ["Ai facut tu platile?"])
    await serviciu.primeste_raspuns(caz["id"], CLIENT, "nu am facut eu")

    assert propus.text == "" and propus.scris_de_agent is False
    # Doar cele doua mesaje reale: nicio analiza, nicio citire structurata.
    assert [m["autor"] for m in cazuri.mesaje] == ["banca", "client"]


@pytest.mark.anyio
async def test_raspunsul_se_salveaza_chiar_daca_agentii_pica():
    """Textul omului intra in dosar inainte sa fie chemat vreun agent."""

    class AnalistCarePica:
        async def rezuma(self, fapte, raspuns):
            raise RuntimeError("providerul e picat")

    cazuri = CazuriFalse()
    serviciu = CazService(
        cazuri,
        AnalizeFalse(),
        ProfiluriFalse(),
        redactor=RedactorFals(),
        extractor=ExtractorFals(),
        analist=AnalistCarePica(),
    )
    id_caz = await _pana_la_raspuns(serviciu, cazuri)

    # Nu arunca: raspunsul e salvat, deci cererea a reusit din punctul de vedere
    # al omului care a apasat trimite.
    await serviciu.primeste_raspuns(id_caz, CLIENT, "nu am facut eu platile")

    assert any(m["autor"] == "client" for m in cazuri.mesaje)
    assert all(m["structura"].get("tip") != "analiza" for m in cazuri.mesaje)


@pytest.mark.anyio
async def test_redactorul_primeste_faptele_nu_randurile_brute():
    """Nici IP, nici IBAN, nici id-uri — doar ce ajuta la scris un mesaj."""
    redactor = RedactorFals()
    cazuri = CazuriFalse()
    serviciu = CazService(
        cazuri, AnalizeFalse(), ProfiluriFalse(), redactor=redactor
    )
    caz = await serviciu.deschide(ADMIN, CLIENT, "plati neobisnuite")

    await serviciu.pregateste_mesaj(caz["id"], ["Ai facut tu platile?"])

    fapte = redactor.fapte_primite[0]
    assert fapte.prenume_client == "Andrei"
    assert fapte.cont_blocat is True
    rezumat = fapte.rezumat()
    assert "4200.00 RON" in rezumat and "MagazinX" in rezumat
    assert "t1" not in rezumat


# -- extractorul ---------------------------------------------------------------


def test_citatul_fabricat_se_arunca():
    """Campul ramane, ghilimelele dispar: omul n-a spus asta."""
    date = {
        "raspunsuri": [
            {"intrebare": "Ai facut tu platile?", "valoare": "nu", "citat": "nu am fost eu"}
        ]
    }
    campuri = _curata(date, ("Ai facut tu platile?",), "Nu recunosc nimic din ce scrieti.")

    assert campuri[0].valoare == "nu"
    assert campuri[0].citat == ""


def test_citatul_real_se_pastreaza():
    text = "Nu am facut eu platile alea, eram la munca."
    date = {
        "raspunsuri": [
            {"intrebare": "Ai facut tu platile?", "valoare": "nu", "citat": "Nu am facut eu platile"}
        ]
    }
    campuri = _curata(date, ("Ai facut tu platile?",), text)

    assert campuri[0].citat == "Nu am facut eu platile"


def test_intrebarea_inventata_se_ignora():
    """Modelul nu poate adauga in dosar intrebari pe care banca nu le-a pus."""
    date = {
        "raspunsuri": [
            {"intrebare": "Ai facut tu platile?", "valoare": "nu", "citat": ""},
            {"intrebare": "Ai datorii la alta banca?", "valoare": "da", "citat": ""},
        ]
    }
    campuri = _curata(date, ("Ai facut tu platile?",), "nu am facut eu")

    assert len(campuri) == 1
    assert campuri[0].intrebare == "Ai facut tu platile?"


def test_valoarea_din_afara_listei_se_ignora():
    date = {"raspunsuri": [{"intrebare": "Ai facut tu platile?", "valoare": "poate", "citat": ""}]}
    assert _curata(date, ("Ai facut tu platile?",), "poate") == ()


@pytest.mark.anyio
async def test_extractorul_tace_fara_intrebari():
    """Fara intrebari puse nu are ce compara — si nu cheama modelul degeaba."""

    class ModelCareNuTrebuieChemat:
        deployment = "fals"

        async def complete_json(self, messages, schema_name, schema):
            raise AssertionError("modelul nu trebuia chemat")

    extractor = ExtractorCaz(ModelCareNuTrebuieChemat())
    assert await extractor.extrage((), "ceva") == ()


# -- faptele -------------------------------------------------------------------


def test_rezumatul_spune_cand_contul_nu_e_blocat():
    """Redactorul nu trebuie sa poata presupune o blocare care nu exista."""
    fapte = FapteCaz(
        prenume_client="Andrei",
        motiv_deschidere="plati neobisnuite",
        gravitate=71,
        numar_semnalari=3,
        tranzactii=(),
        intrebari=("Ai facut tu platile?",),
        cont_blocat=False,
    )
    assert "NU este blocat" in fapte.rezumat()


# -- numele si intrebarile ramase ---------------------------------------------


def test_prenumele_e_ultimul_cuvant():
    """Formularul cere „Nume si prenume", in ordinea asta.

    Luand primul cuvant, scrisoarea a inceput cu „Buna ziua, Oancea" — cu numele
    de familie, ca o somatie.
    """
    assert _prenume_din("Oancea Alexandru") == "Alexandru"
    assert _prenume_din("Popescu Ion Andrei") == "Andrei"
    assert _prenume_din("Ionescu") == "Ionescu"
    assert _prenume_din("") == ""


def test_raspunsul_pe_langa_subiect_lasa_intrebarea_deschisa():
    """„Am platit doar facturile" nu spune daca a facut el cele zece plati."""
    from app.agents.caz.fapte import RaspunsExtras

    intrebari = ("Ai facut tu platile?", "Ai pierdut cardul?")
    campuri = (
        RaspunsExtras(intrebare="Ai facut tu platile?", valoare="nu_a_spus"),
        RaspunsExtras(intrebare="Ai pierdut cardul?", valoare="nu", citat="nu l-am pierdut"),
    )

    assert _fara_raspuns(intrebari, campuri) == ("Ai facut tu platile?",)


def test_fara_citire_structurata_nicio_intrebare_nu_e_lamurita():
    """Daca extractorul a picat, nu presupunem ca s-a raspuns la tot.

    Altfel un caz s-ar inchide cu intrebari nelamurite doar fiindca un model
    a esuat.
    """
    intrebari = ("Ai facut tu platile?", "Ai pierdut cardul?")
    assert _fara_raspuns(intrebari, ()) == intrebari


# -- reluarea automata ---------------------------------------------------------


@pytest.mark.anyio
async def test_raspunsul_nelamuritor_declanseaza_o_reluare_catre_client():
    """Fara administrator la mijloc: intrebarile ramase pleaca singure inapoi."""
    serviciu, cazuri, analize = _serviciu()
    id_caz = await _pana_la_raspuns(serviciu, cazuri)

    await serviciu.primeste_raspuns(id_caz, CLIENT, "Am platit doar facturile.")

    banca = [m for m in cazuri.mesaje if m["autor"] == "banca"]
    assert len(banca) == 2
    reluarea = banca[-1]
    # Niciun om nu a scris si nu a citit mesajul asta: dosarul o spune pe fata.
    assert reluarea["propus_de_agent"] is True
    assert reluarea["editat_de_om"] is False
    assert reluarea.get("id_autor") is None
    assert reluarea["structura"]["reluare"] is True

    assert cazuri.cazuri[id_caz]["stare"] == "asteptam_clientul"
    assert len(analize.notificari) == 2


@pytest.mark.anyio
async def test_raspunsul_lamuritor_nu_declanseaza_nimic():
    from app.agents.caz.fapte import RaspunsExtras

    extractor = ExtractorFals(
        campuri=(
            RaspunsExtras(intrebare="Ai facut tu platile?", valoare="nu", citat="nu am facut eu"),
        )
    )
    serviciu, cazuri, _ = _serviciu(extractor=extractor)
    id_caz = await _pana_la_raspuns(serviciu, cazuri)

    await serviciu.primeste_raspuns(id_caz, CLIENT, "nu am facut eu")

    assert len([m for m in cazuri.mesaje if m["autor"] == "banca"]) == 1
    assert cazuri.cazuri[id_caz]["stare"] == "client_a_raspuns"


@pytest.mark.anyio
async def test_banca_nu_intreaba_de_mai_mult_de_cinci_ori():
    """Altfel un om cu contul blocat ar ramane intr-o bucla fara iesire."""
    from app.services.caz_service import MAX_RELUARI

    serviciu, cazuri, _ = _serviciu()
    id_caz = await _pana_la_raspuns(serviciu, cazuri)

    # Raspunde de sase ori, mereu pe langa subiect.
    for _ in range(6):
        if cazuri.cazuri[id_caz]["stare"] != "asteptam_clientul":
            break
        await serviciu.primeste_raspuns(id_caz, CLIENT, "Am platit doar facturile.")

    intrebari = [m for m in cazuri.mesaje if m["autor"] == "banca"]
    assert len(intrebari) == MAX_RELUARI

    epuizat = [m for m in cazuri.mesaje if m["structura"].get("tip") == "epuizat"]
    assert len(epuizat) == 1
    assert "sucursala" in epuizat[0]["text"]
    assert epuizat[0]["structura"]["incercari"] == MAX_RELUARI


@pytest.mark.anyio
async def test_oprirea_reluarilor_nu_atinge_contul():
    """„Contul ramane blocat" inseamna neatins, nu blocat de sistem."""
    serviciu, cazuri, analize = _serviciu()
    id_caz = await _pana_la_raspuns(serviciu, cazuri)

    for _ in range(6):
        if cazuri.cazuri[id_caz]["stare"] != "asteptam_clientul":
            break
        await serviciu.primeste_raspuns(id_caz, CLIENT, "Am platit doar facturile.")

    # Depozitul de analize nu a primit nicio comanda de blocare — singurele
    # scrieri prin el sunt notificarile.
    assert not hasattr(analize, "blocari")
    conturi = await analize.conturi(CLIENT)
    assert conturi[0]["blocat_administrativ"] is True


# -- ce afla clientul la final -------------------------------------------------


@pytest.mark.anyio
async def test_la_inchidere_clientul_afla_starea_reala_a_contului():
    """Nu decizia administratorului, ci starea din baza in acel moment.

    Cazul se inchide cu 'deblocat', dar butonul de deblocare e alt ecran si
    poate sa nu fi fost apasat inca. Un mesaj care ar spune „contul a fost
    deblocat" l-ar trimite pe om sa fie refuzat la casa.
    """
    serviciu, cazuri, analize = _serviciu()
    id_caz = await _pana_la_raspuns(serviciu, cazuri)

    await serviciu.inchide(id_caz, ADMIN, "deblocat")

    ultima = analize.notificari[-1]
    assert ultima[1] == "Verificarea s-a incheiat"
    # Contul e inca blocat in dublura, deci tonul nu e de deblocare.
    assert ultima[2] == "atentionare"


@pytest.mark.anyio
async def test_clientul_cu_contul_activ_afla_ca_poate_plati():
    cazuri = CazuriFalse()
    analize = AnalizeFalse(blocat=False)
    serviciu = CazService(cazuri, analize, ProfiluriFalse(), redactor=RedactorFals())
    id_caz = await _pana_la_raspuns(serviciu, cazuri)

    await serviciu.inchide(id_caz, ADMIN, "fara_masuri")

    assert analize.notificari[-1][2] == "deblocare"
