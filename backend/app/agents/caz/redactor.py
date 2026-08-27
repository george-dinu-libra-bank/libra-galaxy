"""Agentul care scrie mesajul catre client.

Nu trimite nimic. Propune un text, pe care administratorul il citeste, il
modifica daca vrea si abia apoi il trimite — de aceea `propus_de_agent` si
`editat_de_om` sunt coloane in `caz_mesaj`: peste sase luni, la o contestatie,
intrebarea „cine a scris asta" trebuie sa aiba raspuns in date.
"""

import logging

from app.agents.caz.fapte import FapteCaz
from app.agents.caz.prompt import instructiuni
from app.agents.specs import CAZ_REDACTOR
from app.providers.base import ChatMessage, ChatProvider

logger = logging.getLogger(__name__)

REGULI = """
Scrii un singur mesaj, de la banca pentru client, gata de trimis.

Forma:
- incepe cu „Buna ziua, <prenume>," — daca prenumele lipseste, „Buna ziua,";
- doua-trei propozitii care spun ce s-a observat, cu datele si sumele exacte
  din lista de mai jos, fara sa le rotunjesti si fara sa adaugi altele;
- daca contul e blocat, spune limpede ca a fost blocat preventiv, ca masura de
  siguranta, si ca ramane asa pana se lamureste situatia;
- pune intrebarile primite, in ordinea data, ca text curgator sau ca lista
  scurta — cum se citeste mai firesc;
- incheie spunand ca asteptati raspunsul lui.

Ton: al unui om care lucreaza la banca si vorbeste cu un client ingrijorat. Nu
esti nici anchetator, nici robot de marketing. Fara formule pompoase, fara
„va informam ca prin prezenta".

Nu semnezi cu un nume de persoana. Daca semnezi, „Echipa Galaxy Bank".

Nu ceri niciodata parola, PIN-ul, numarul complet al cardului, CVV-ul sau un
cod primit prin SMS. Banca nu cere asa ceva, iar un mesaj care ar cere devine
chiar tiparul pe care il combatem.
""".strip()

# Peste plafonul asta clientul nu mai citeste, iar coloana `text` din caz_mesaj
# se opreste oricum la 4000.
MAX_CARACTERE = 2200


class RedactorCaz:
    """Propune textul mesajului catre client."""

    spec = CAZ_REDACTOR

    def __init__(self, chat: ChatProvider) -> None:
        self._chat = chat

    async def propune(self, fapte: FapteCaz) -> str:
        mesaje = [
            ChatMessage(role="system", content=instructiuni(self.spec, REGULI)),
            ChatMessage(role="user", content=f"Faptele cazului:\n\n{fapte.rezumat()}"),
        ]

        raspuns = await self._chat.complete(mesaje)
        text = (raspuns.text or "").strip()

        if not text:
            # Nu inventam un mesaj de rezerva „de la banca". Administratorul
            # scrie el, in caseta care oricum ii sta la dispozitie.
            logger.warning("redactorul a intors text gol pentru un caz")
            return ""

        return text[:MAX_CARACTERE]
