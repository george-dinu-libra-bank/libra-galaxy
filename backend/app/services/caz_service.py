"""Investigatia de frauda: cine scrie ce si cand.

Asta e orchestratorul celor trei agenti, si nu e un model. Pasii unui caz sunt
cunoscuti dinainte — banca intreaba, clientul raspunde, administratorul decide —
si nu au de ce sa fie descoperiti la fiecare rulare de catre un LLM caruia i s-ar
da lista agentilor. Un model care alege singur ordinea ar face fluxul
nereproductibil exact in zona unde cineva ramane fara acces la banii lui.

Agentii sunt chemati din pasii de mai jos, fiecare la momentul lui:

    deschide            → cazul exista, inca nu s-a scris nimic
    pregateste_mesaj    → REDACTORUL propune textul catre client
    trimite_mesaj       → administratorul l-a citit si il trimite
    primeste_raspuns    → EXTRACTORUL citeste raspunsul, ANALISTUL il rezuma
    inchide             → administratorul alege urmarea

Ce NU face serviciul asta: nu blocheaza si nu deblocheaza conturi. Blocarea
traieste pe `conturi_bancare`, e aparata de trigger-ul din 0030 si se schimba
prin apasarea explicita a administratorului, in alta parte a panoului. Un caz
poate exista fara blocare si un cont poate fi blocat fara caz; daca inchiderea
cazului ar debloca automat, masura ar deveni efectul secundar al unui formular.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.agents.caz import AnalistCaz, ExtractorCaz, RedactorCaz
from app.agents.caz.fapte import FapteCaz, RaspunsClient, TranzactieCaz
from app.core.errors import ResourceNotFoundError, ValidationError
from app.ml.caracteristici import comerciant_pentru_om
from app.repositories.admin_repository import AdminRepository, AnalizaRepository
from app.repositories.caz_repository import STARI_INCHISE, CazRepository

logger = logging.getLogger(__name__)

MIN_MOTIV = 3
MAX_MOTIV = 2000
MAX_TEXT_MESAJ = 4000
MAX_INTREBARI = 8
REZULTATE = ("fara_masuri", "deblocat", "sucursala", "anaf")

# De cate ori intreaba banca in scris inainte sa renunte. Se numara mesajele
# bancii de pe fir, inclusiv primul — deci patru reluari dupa intrebarea
# initiala. Plafonul exista ca sa nu tinem un om cu contul blocat intr-o bucla
# de intrebari din care nu are cum sa iasa.
MAX_RELUARI = 5

# Ce i se spune redactorului cand reia. Fara asta ar scrie iar mesajul de
# deschidere, ca si cum omul n-ar fi raspuns niciodata.
NOTA_RELUARE = (
    "Clientul a raspuns deja o data, dar raspunsul lui nu a atins intrebarile de mai jos. "
    "Scrie un mesaj scurt care ii multumeste ca a raspuns, ii spune ca mai avem nevoie de "
    "o lamurire, si pune DOAR intrebarile ramase. Nu relua lista de plati in intregime si "
    "nu-l certa ca nu a raspuns."
)

# Ce urmare duce cazul in ce stare finala. „Escalat" e altceva decat „rezolvat":
# un caz predat conformitatii nu s-a terminat, doar a iesit din mainile
# administratorului asta.
STARE_FINALA = {
    "fara_masuri": "rezolvat",
    "deblocat": "rezolvat",
    "sucursala": "inchis",
    "anaf": "escalat",
}

# Tranzitiile permise. Scrise ca date, nu ca `if`-uri imprastiate: cine vrea sa
# stie ce poate urma dupa ce se uita aici, nu prin cinci metode.
TRANZITII: dict[str, tuple[str, ...]] = {
    "nou": ("in_analiza", "asteptam_clientul", *STARI_INCHISE),
    "in_analiza": ("asteptam_clientul", *STARI_INCHISE),
    "asteptam_clientul": ("client_a_raspuns", *STARI_INCHISE),
    "client_a_raspuns": ("in_analiza", "asteptam_clientul", *STARI_INCHISE),
    "rezolvat": (),
    "escalat": (),
    "inchis": (),
}


@dataclass(slots=True)
class MesajPropus:
    """Ce a scris redactorul, inainte ca vreun om sa-l fi vazut."""

    text: str
    intrebari: tuple[str, ...]
    scris_de_agent: bool


class CazService:
    def __init__(
        self,
        cazuri: CazRepository,
        analize: AnalizaRepository,
        profiluri: AdminRepository,
        redactor: RedactorCaz | None = None,
        extractor: ExtractorCaz | None = None,
        analist: AnalistCaz | None = None,
    ) -> None:
        self._cazuri = cazuri
        # `analize` da notificarile si conturile, `profiluri` da numele. Amandoua
        # primesc clientul de service-role: pasii de mai jos sunt chemati si de
        # client (raspunsul lui), care nu are drepturi de administrator, dar
        # pentru care tot trebuie sa stim daca ii e contul blocat.
        self._analize = analize
        self._profiluri = profiluri
        # Agentii sunt optionali: fara provider de model configurat, fluxul merge
        # mai departe fara ei — administratorul scrie mesajul singur si citeste
        # raspunsul cu ochii lui. Investigatia nu depinde de un LLM.
        self._redactor = redactor
        self._extractor = extractor
        self._analist = analist

    # -- 1. deschiderea ------------------------------------------------------

    async def deschide(
        self,
        id_administrator: UUID | str,
        id_utilizator: UUID | str,
        motiv: str,
        gravitate: int | None = None,
        numar_semnalari: int | None = None,
        tranzactii: list[dict] | None = None,
    ) -> dict:
        motiv = (motiv or "").strip()
        if not (MIN_MOTIV <= len(motiv) <= MAX_MOTIV):
            raise ValidationError("Cazul are nevoie de un motiv de deschidere.")

        existent = await self._cazuri.deschis_pentru(id_utilizator)
        if existent:
            # Nu e o eroare: administratorul a nimerit peste un caz pe care il
            # deschisese un coleg. Il primeste pe acela, in loc sa porneasca un
            # al doilea fir catre acelasi om.
            return existent

        rand = await self._cazuri.creeaza(
            {
                "id_administrator": str(id_administrator),
                "id_utilizator": str(id_utilizator),
                "motiv_deschidere": motiv,
                "gravitate": gravitate,
                "numar_semnalari": numar_semnalari,
            }
        )
        if rand is None:
            raise ValidationError("Nu am putut deschide cazul.")

        if tranzactii:
            try:
                await self._cazuri.leaga_tranzactii(rand["id"], _fara_duplicate(tranzactii))
            except Exception:
                # Cazul e deja creat. Daca legarea platilor pica, mai bine o
                # investigatie fara lista de plati decat un ecran de eroare
                # peste un rand care exista oricum in baza — administratorul o
                # vede in coada si poate merge mai departe.
                logger.exception("nu am putut lega platile de cazul %s", rand["id"])

        return rand

    # -- 2. redactorul propune -----------------------------------------------

    async def pregateste_mesaj(
        self, id_caz: UUID | str, intrebari: list[str], nota_administrator: str = ""
    ) -> MesajPropus:
        """Cere redactorului un text. NU il salveaza si NU il trimite.

        Separarea e intentionata: ce iese de aici e o propunere pe ecranul
        administratorului, pe care el o poate rescrie in intregime. Abia
        `trimite_mesaj` scrie ceva in dosar.
        """
        caz = await self._caz_sau_eroare(id_caz)
        curate = _curata_intrebari(intrebari)
        if not curate:
            raise ValidationError("Trimite cel putin o intrebare pentru client.")

        if self._redactor is None:
            return MesajPropus(text="", intrebari=curate, scris_de_agent=False)

        fapte = await self._fapte(caz, curate, nota_administrator)
        try:
            text = await self._redactor.propune(fapte)
        except Exception:
            # Caseta ii ramane administratorului goala, si scrie el. Mai bine
            # decat un ecran de eroare peste un caz deja deschis.
            logger.exception("redactorul a esuat pentru cazul %s", id_caz)
            text = ""

        return MesajPropus(text=text, intrebari=curate, scris_de_agent=bool(text))

    # -- 3. administratorul trimite ------------------------------------------

    async def trimite_mesaj(
        self,
        id_caz: UUID | str,
        id_administrator: UUID | str,
        text: str,
        intrebari: list[str],
        propus_de_agent: bool = False,
        editat_de_om: bool = False,
    ) -> dict:
        caz = await self._caz_sau_eroare(id_caz)
        _verifica_tranzitie(caz["stare"], "asteptam_clientul")

        text = (text or "").strip()
        if not (1 <= len(text) <= MAX_TEXT_MESAJ):
            raise ValidationError("Mesajul catre client nu are o lungime valida.")

        curate = _curata_intrebari(intrebari)
        if not curate:
            raise ValidationError("Mesajul trebuie sa contina cel putin o intrebare.")

        mesaj = await self._cazuri.adauga_mesaj(
            {
                "id_caz": str(id_caz),
                "autor": "banca",
                "id_autor": str(id_administrator),
                "text": text,
                # Intrebarile stau pe mesajul care le-a pus, nu intr-o tabela
                # separata: extractorul le ia de aici cand vine raspunsul, si
                # se vede negru pe alb la ce raspundea omul.
                "structura": {"intrebari": list(curate)},
                "propus_de_agent": propus_de_agent,
                "editat_de_om": editat_de_om,
            }
        )
        if mesaj is None:
            raise ValidationError("Nu am putut trimite mesajul.")

        await self._cazuri.schimba_starea(id_caz, "asteptam_clientul")
        await self._anunta_clientul(caz["id_utilizator"], id_caz)
        return mesaj

    # -- 4. clientul raspunde ------------------------------------------------

    async def primeste_raspuns(
        self, id_caz: UUID | str, id_utilizator: UUID | str, text: str
    ) -> dict:
        """Salveaza raspunsul clientului, apoi il citeste si il rezuma.

        Ordinea conteaza: textul omului se scrie in dosar INAINTE de a chema
        vreun agent. Daca extractorul sau analistul pica, raspunsul e deja
        acolo, si administratorul il citeste singur.
        """
        caz = await self._caz_sau_eroare(id_caz)

        if str(caz["id_utilizator"]) != str(id_utilizator):
            # Nu spunem „cazul nu e al tau": ar confirma ca exista. Pentru
            # cineva care nu e proprietar, cazul pur si simplu nu exista.
            raise ResourceNotFoundError("Cazul nu exista.")

        _verifica_tranzitie(caz["stare"], "client_a_raspuns")

        text = (text or "").strip()
        if not (1 <= len(text) <= MAX_TEXT_MESAJ):
            raise ValidationError("Raspunsul nu are o lungime valida.")

        mesaj = await self._cazuri.adauga_mesaj(
            {
                "id_caz": str(id_caz),
                "autor": "client",
                "id_autor": str(id_utilizator),
                "text": text,
            }
        )
        if mesaj is None:
            raise ValidationError("Nu am putut salva raspunsul.")

        await self._cazuri.schimba_starea(id_caz, "client_a_raspuns")

        # De aici incolo totul e in plus. Raspunsul omului e deja in dosar si
        # starea e deja mutata; daca un agent arunca, cererea lui a reusit
        # oricum. Fara plasa asta, ar primi 500 dupa ce a fost salvat, ar
        # reincerca, si reincercarea ar pica pe tranzitie — cu raspunsul lui
        # ajuns deja la banca.
        try:
            await self._citeste_si_rezuma(caz, id_caz, text)
        except Exception:
            logger.exception("agentii nu au putut prelucra raspunsul din cazul %s", id_caz)

        return mesaj

    async def _citeste_si_rezuma(self, caz: dict, id_caz: UUID | str, text: str) -> None:
        intrebari = await self._intrebarile_puse(id_caz)
        campuri: tuple = ()
        if self._extractor is not None and intrebari:
            campuri = await self._extractor.extrage(intrebari, text)

        if campuri:
            # `caz_mesaj` e append-only (trigger-ul din 0051), deci citirea
            # structurata nu se poate lipi pe mesajul clientului. Merge intr-un
            # rand propriu, de la 'sistem' — si asa e mai onest: se vede ca e
            # o citire facuta ulterior, nu ceva ce a scris omul.
            await self._cazuri.adauga_mesaj(
                {
                    "id_caz": str(id_caz),
                    "autor": "sistem",
                    "text": "Citirea structurata a raspunsului.",
                    "structura": {
                        "tip": "extragere",
                        "campuri": [
                            {"intrebare": c.intrebare, "valoare": c.valoare, "citat": c.citat}
                            for c in campuri
                        ],
                    },
                    "propus_de_agent": True,
                }
            )

        if self._analist is not None:
            fapte = await self._fapte(caz, intrebari, "")
            rezumat = await self._analist.rezuma(
                fapte, RaspunsClient(text=text, campuri=campuri)
            )
            if rezumat:
                await self._cazuri.adauga_mesaj(
                    {
                        "id_caz": str(id_caz),
                        "autor": "sistem",
                        "text": rezumat,
                        "structura": {
                            "tip": "analiza",
                            # Intrebarile la care omul nu a raspuns, gata de reluat.
                            # Ecranul administratorului le incarca singur in caseta
                            # de compunere, ca sa nu le caute el prin fir.
                            "fara_raspuns": list(_fara_raspuns(intrebari, campuri)),
                        },
                        "propus_de_agent": True,
                    }
                )

        await self._reia_sau_opreste(caz, id_caz, _fara_raspuns(intrebari, campuri))

    # -- 4b. reluarea automata -----------------------------------------------

    async def _reia_sau_opreste(
        self, caz: dict, id_caz: UUID | str, fara_raspuns: tuple[str, ...]
    ) -> None:
        """Cand raspunsul lasa intrebari deschise, banca le pune din nou.

        Reluarea pleaca singura catre client, fara ca administratorul sa o
        citeasca inainte — e singurul loc din tot fluxul unde se intampla asta,
        si e o decizie explicita: intrebarile sunt aceleasi pe care omul le-a
        primit deja, agentul nu adauga altele, iar tot ce poate face mesajul e
        sa ceara o lamurire. Nicio masura asupra contului nu se ia pe drumul
        asta.

        Dupa MAX_RELUARI incercari se opreste. Un sistem care ar intreba la
        nesfarsit ar tine un om cu contul blocat intr-o bucla din care nu are
        cum sa iasa; de la un punct incolo, raspunsul nu mai vine in scris.
        """
        if not fara_raspuns:
            return

        intrebari_puse = await self._numar_intrebari(id_caz)

        if intrebari_puse >= MAX_RELUARI:
            await self._opreste_reluarile(id_caz, fara_raspuns, intrebari_puse)
            return

        if self._redactor is None:
            # Fara agent nu se poate compune nimic; ramane pe ecranul
            # administratorului, cu intrebarile deja incarcate in caseta.
            return

        fapte = await self._fapte(caz, fara_raspuns, NOTA_RELUARE)
        text = await self._redactor.propune(fapte)
        if not text:
            return

        await self._cazuri.adauga_mesaj(
            {
                "id_caz": str(id_caz),
                "autor": "banca",
                # Fara id_autor: niciun om nu a scris si nu a citit mesajul asta
                # inainte sa plece. Coloanele de mai jos o spun pe fata, iar
                # dosarul ramane onest la o eventuala contestatie.
                "text": text,
                "structura": {"intrebari": list(fara_raspuns), "reluare": True},
                "propus_de_agent": True,
                "editat_de_om": False,
            }
        )

        await self._cazuri.schimba_starea(id_caz, "asteptam_clientul")
        await self._anunta_clientul(caz["id_utilizator"], id_caz)

    async def _opreste_reluarile(
        self, id_caz: UUID | str, fara_raspuns: tuple[str, ...], incercari: int
    ) -> None:
        """Consemneaza ca discutia in scris s-a terminat fara raspuns.

        Textul e scris de cod, nu de analist. Interdictia din specificatia lui
        („sa recomande o masura — blocare, sucursala, escaladare") ramane
        intacta: recomandarea de mai jos nu e judecata unui model asupra unui
        om, ci regula fluxului dupa un numar de incercari care se poate numara.

        Contul nu se atinge. Ramane exact cum era — daca administratorul l-a
        blocat, ramane blocat; nimic de aici nu blocheaza si nu deblocheaza.
        Inchiderea cu 'sucursala' e tot apasarea lui.
        """
        ramase = "; ".join(fara_raspuns)
        await self._cazuri.adauga_mesaj(
            {
                "id_caz": str(id_caz),
                "autor": "sistem",
                "text": (
                    f"Clientul a fost intrebat de {incercari} ori si raspunsurile nu au "
                    f"lamurit: {ramase}. Discutia in scris nu mai avanseaza — clientul "
                    f"ar trebui chemat la sucursala, cu actul de identitate. Contul ii "
                    f"ramane in starea in care este acum; nimic nu s-a schimbat automat."
                ),
                "structura": {
                    "tip": "epuizat",
                    "incercari": incercari,
                    "fara_raspuns": list(fara_raspuns),
                },
            }
        )

    async def _numar_intrebari(self, id_caz: UUID | str) -> int:
        """De cate ori a intrebat banca pe firul asta."""
        mesaje = await self._cazuri.mesajele(id_caz)
        return sum(1 for m in mesaje if m["autor"] == "banca")

    # -- 5. administratorul incheie ------------------------------------------

    async def inchide(
        self,
        id_caz: UUID | str,
        id_administrator: UUID | str,
        rezultat: str,
        nota: str = "",
    ) -> dict:
        """Incheie cazul cu urmarea aleasa de administrator.

        Nu atinge blocarea contului. Daca urmarea e `deblocat`, deblocarea
        propriu-zisa e tot o apasare a lui, in ecranul contului — aici doar se
        consemneaza ce a decis.
        """
        caz = await self._caz_sau_eroare(id_caz)

        if rezultat not in REZULTATE:
            raise ValidationError(f"Urmarea '{rezultat}' nu exista.")

        stare = STARE_FINALA[rezultat]
        _verifica_tranzitie(caz["stare"], stare)

        nota = (nota or "").strip()
        if nota:
            await self._cazuri.adauga_mesaj(
                {
                    "id_caz": str(id_caz),
                    "autor": "sistem",
                    "id_autor": str(id_administrator),
                    "text": nota[:MAX_TEXT_MESAJ],
                    "structura": {"tip": "inchidere", "rezultat": rezultat},
                    "editat_de_om": True,
                }
            )

        rand = await self._cazuri.schimba_starea(id_caz, stare, rezultat=rezultat, inchide=True)
        if rand is None:
            raise ValidationError("Nu am putut inchide cazul.")

        await self._anunta_inchiderea(caz["id_utilizator"], id_caz, rezultat)
        return rand

    async def _anunta_inchiderea(
        self, id_utilizator: str, id_caz: UUID | str, rezultat: str
    ) -> None:
        """Ii spune clientului ca s-a terminat si CUM ii e contul acum.

        Starea se citeste din baza in acest moment, nu se deduce din `rezultat`.
        Diferenta conteaza: `rezultat='deblocat'` inseamna ca administratorul a
        decis deblocarea, dar apasarea propriu-zisa e alt buton, in ecranul
        contului, si poate sa nu se fi intamplat inca. Un mesaj care ar spune
        „contul a fost deblocat" pe baza deciziei ar trimite omul sa plateasca
        si sa fie refuzat la casa.
        """
        blocat = await self._cont_blocat(id_utilizator)

        if blocat:
            stare_cont = (
                "Contul tau este in continuare blocat. Daca ai nevoie de lamuriri, "
                "ne poti scrie din aplicatie."
            )
        else:
            stare_cont = (
                "Contul tau este activ: poti folosi din nou cardurile si transferurile."
            )

        urmare = {
            "fara_masuri": "Am verificat platile semnalate si nu am gasit nimic de indreptat.",
            "deblocat": "Am incheiat verificarea platilor semnalate.",
            "sucursala": (
                "Pentru restul lamuririlor te asteptam la o sucursala, cu actul de "
                "identitate."
            ),
            "anaf": (
                "Verificarea a fost preluata de echipa noastra de conformitate, care "
                "revine catre tine."
            ),
        }[rezultat]

        try:
            await self._analize.scrie_notificare(
                id_utilizator,
                "Verificarea s-a incheiat",
                f"{urmare}\n\n{stare_cont}\n\n[investigatie:{id_caz}]",
                "deblocare" if not blocat else "atentionare",
            )
        except Exception:
            # Cazul e deja inchis; esecul notificarii nu il redeschide, dar il
            # lasa pe om sa nu stie ca s-a terminat.
            logger.exception("nu am putut anunta inchiderea cazului %s", id_caz)

    # -- citiri --------------------------------------------------------------

    async def coada(self, doar_deschise: bool = True) -> list[dict]:
        return await self._cazuri.coada(doar_deschise)

    async def dosar(self, id_caz: UUID | str) -> dict:
        caz = await self._caz_sau_eroare(id_caz)
        return {
            "caz": caz,
            "tranzactii": await self._cazuri.tranzactiile(id_caz),
            "mesaje": await self._cazuri.mesajele(id_caz),
        }

    async def dosarul_clientului(self, id_caz: UUID | str, id_utilizator: UUID | str) -> dict:
        caz = await self._caz_sau_eroare(id_caz)
        if str(caz["id_utilizator"]) != str(id_utilizator):
            raise ResourceNotFoundError("Cazul nu exista.")

        # Clientul vede firul, nu si dosarul intern: mesajele de la 'sistem'
        # (citirea structurata, analiza, nota de inchidere) sunt scrise pentru
        # administrator si raman la el.
        mesaje = [m for m in await self._cazuri.mesajele(id_caz) if m["autor"] != "sistem"]
        return {"caz": caz, "mesaje": mesaje}

    async def ale_utilizatorului(self, id_utilizator: UUID | str) -> list[dict]:
        return await self._cazuri.ale_utilizatorului(id_utilizator)

    # -- ajutoare ------------------------------------------------------------

    async def _caz_sau_eroare(self, id_caz: UUID | str) -> dict:
        caz = await self._cazuri.caz(id_caz)
        if caz is None:
            raise ResourceNotFoundError("Cazul nu exista.")
        return caz

    async def _intrebarile_puse(self, id_caz: UUID | str) -> tuple[str, ...]:
        """Intrebarile din ultimul mesaj al bancii — cele la care tocmai s-a raspuns."""
        for mesaj in reversed(await self._cazuri.mesajele(id_caz)):
            if mesaj["autor"] != "banca":
                continue
            intrebari = (mesaj.get("structura") or {}).get("intrebari")
            if isinstance(intrebari, list):
                return tuple(str(i) for i in intrebari if str(i).strip())
            return ()
        return ()

    async def _fapte(self, caz: dict, intrebari: tuple[str, ...], nota: str) -> FapteCaz:
        randuri = await self._cazuri.tranzactiile(caz["id"])
        return FapteCaz(
            prenume_client=await self._prenume(caz["id_utilizator"]),
            motiv_deschidere=caz["motiv_deschidere"],
            gravitate=caz.get("gravitate"),
            numar_semnalari=caz.get("numar_semnalari"),
            tranzactii=tuple(_tranzactie(r) for r in randuri if r.get("tranzactii")),
            intrebari=intrebari,
            cont_blocat=await self._cont_blocat(caz["id_utilizator"]),
            note_administrator=nota,
        )

    async def _prenume(self, id_utilizator: str) -> str:
        try:
            profil = await self._profiluri.profil(id_utilizator)
        except Exception:
            logger.exception("nu am putut citi profilul pentru cazul unui client")
            return ""
        nume = str((profil or {}).get("nume") or "").strip()
        return _prenume_din(nume)

    async def _cont_blocat(self, id_utilizator: str) -> bool:
        try:
            conturi = await self._analize.conturi(id_utilizator)
            return any(bool(c.get("blocat_administrativ")) for c in conturi)
        except Exception:
            # Daca nu stim sigur, spunem ca nu e blocat: un mesaj care anunta
            # gresit o blocare care nu exista sperie un om degeaba.
            logger.exception("nu am putut citi starea contului pentru un caz")
            return False

    async def _anunta_clientul(self, id_utilizator: str, id_caz: UUID | str) -> None:
        try:
            await self._analize.scrie_notificare(
                id_utilizator,
                "Banca iti cere o lamurire",
                "Am observat cateva plati pe contul tau si avem nevoie de raspunsul tau. "
                "Deschide mesajul din aplicatie ca sa vezi despre ce e vorba.\n\n"
                # Marcajul e tiparul deja folosit de notificarile de credit
                # (frontend/src/lib/notificari-credit.ts): tabela `notificari` e
                # comuna intregii aplicatii, iar o coloana de legatura folosita
                # de un singur flux ar fi insemnat sa largesc schema degeaba.
                # Interfata il scoate din text inainte sa-l arate omului.
                f"[investigatie:{id_caz}]",
                "atentionare",
            )
        except Exception:
            # Mesajul e deja in dosar; esecul notificarii nu il pierde, doar il
            # lasa pe om sa nu stie ca a primit ceva.
            logger.exception("nu am putut notifica clientul despre cazul %s", id_caz)


def _tranzactie(rand: dict) -> TranzactieCaz:
    t = rand["tranzactii"]
    moment = datetime.fromisoformat(str(t["creat_la"]).replace("Z", "+00:00"))
    return TranzactieCaz(
        data=moment.date(),
        suma=float(t.get("suma") or 0),
        valuta=str(t.get("valuta") or "RON"),
        # Fara codul de referinta: „Kaufland ref 99929175" nu ajuta pe nimeni
        # sa-si aminteasca plata, dar face fraza de doua ori mai lunga.
        comerciant=comerciant_pentru_om(t.get("descriere")),
        motiv=str(rand.get("motiv") or "semnalata de sistem"),
    )


def _fara_raspuns(intrebari: tuple[str, ...], campuri: tuple) -> tuple[str, ...]:
    """Intrebarile la care raspunsul clientului nu a spus nimic.

    „Am platit doar facturile" e un raspuns, dar nu la intrebarea daca a facut
    el cele zece plati — extractorul il marcheaza `nu_a_spus`, si atunci
    intrebarea trebuie pusa din nou.

    Cand extractorul n-a intors nimic (a picat, sau nu e configurat), se
    considera ca NICIO intrebare n-a primit raspuns. Alegerea e deliberata:
    varianta cealalta ar fi fost sa presupunem ca s-a raspuns la tot, iar un caz
    s-ar fi inchis cu intrebari nelamurite doar fiindca un model a esuat.
    """
    if not campuri:
        return intrebari

    lamurite = {c.intrebare for c in campuri if c.valoare != "nu_a_spus"}
    return tuple(i for i in intrebari if i not in lamurite)


def _prenume_din(nume: str) -> str:
    """Prenumele dintr-un nume complet, dupa conventia aplicatiei.

    Formularul de inregistrare cere „Nume si prenume", in ordinea asta, iar
    `lib/validare.ts` refuza un nume dintr-un singur cuvant — deci prenumele e
    ULTIMUL cuvant, nu primul. Luand primul cuvant, scrisoarea catre client a
    inceput cu „Buna ziua, Oancea", adica exact cu numele de familie, ca o
    somatie.

    Ramane o presupunere, nu o certitudine: cineva poate scrie oricum in
    formular. De aceea, cand nu se poate deduce nimic, `FapteCaz` are un salut
    fara nume — mai bine „Buna ziua," decat un nume gresit.
    """
    bucati = nume.split()
    return bucati[-1] if bucati else ""


def _fara_duplicate(tranzactii: list[dict]) -> list[dict]:
    """`caz_tranzactie` are cheie primara (id_caz, id_tranzactie).

    Doua randuri cu aceeasi plata ar face insertul sa pice in intregime, iar
    detectorul poate semnala aceeasi tranzactie din doua motive diferite — de
    exemplu si ca suma neobisnuita, si ca parte dintr-o rafala. Se pastreaza
    primul motiv, care e cel mai grav: constatarile vin ordonate dupa scor.
    """
    vazute: set[str] = set()
    curate: list[dict] = []
    for t in tranzactii:
        cheie = str(t.get("id_tranzactie") or "")
        if not cheie or cheie in vazute:
            continue
        vazute.add(cheie)
        curate.append(t)
    return curate


def _curata_intrebari(intrebari: list[str] | tuple[str, ...] | None) -> tuple[str, ...]:
    if not intrebari:
        return ()
    curate = [str(i).strip() for i in intrebari if str(i).strip()]
    return tuple(curate[:MAX_INTREBARI])


def _verifica_tranzitie(din: str, spre: str) -> None:
    permise = TRANZITII.get(din)
    if permise is None:
        raise ValidationError(f"Starea '{din}' nu exista.")
    if spre not in permise:
        # Cel mai des: doi administratori pe acelasi caz, sau un client care
        # trimite de doua ori de pe acelasi ecran.
        raise ValidationError(f"Cazul e in starea '{din}' si nu mai poate trece in '{spre}'.")
