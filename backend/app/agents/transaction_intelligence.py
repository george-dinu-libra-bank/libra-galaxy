from __future__ import annotations

from app.agents.base import (
    ActiunePropusa,
    AgentAnswer,
    AttachmentContext,
    build_system_prompt,
    build_user_message,
    confidence_from_tool_results,
)
from app.agents.specs import TRANSACTION_INTELLIGENCE
from app.context.builder import AssembledContext
from app.core.security import Principal
from app.providers.base import ChatMessage, ChatProvider
from app.tools.base import SelectedTool, ToolResult
from app.tools.categorii_tranzactii import extrage_suma


MAX_PASI = 3

# Rand gol intre paragrafele sesizarii compuse determinist.
SEPARATOR = chr(10) + chr(10)

# Adaugat la promptul comun doar cand contul chiar e blocat.
#
# Promptul de baza ii interzice sa "inventeze functionalitati" si sa "propuna
# alternative imaginate" — pe buna dreptate. Fara randurile astea, modelul citea
# si tool-ul real ca pe ceva neoferit de aplicatie si refuza sa-l foloseasca.
# Interdictia ramane; se adauga doar faptul ca instrumentul chiar exista.
INSTRUCTIUNI_CONT_BLOCAT = "\n".join((
    "",
    "",
    "CONTUL ACESTUI CLIENT ESTE BLOCAT DE BANCA.",
    "Spune-i intai motivul, daca il stii din mesajele bancii, si da-i numarul de",
    "telefon potrivit pentru situatia lui.",
    "Ai la dispozitie un instrument real, pregateste_sesizare, prin care poti compune",
    "o sesizare scrisa catre banca. NU e o functionalitate imaginata: exista si ai",
    "voie sa o folosesti. Cheam-o cand clientul vrea sa scrie bancii, cere lamuriri",
    "suplimentare, sau nu se multumeste cu telefonul.",
    "Nu trimite nimic si nu spune ca ai trimis: instrumentul doar pregateste textul,",
    "iar clientul il trimite apasand un buton pe care il vede sub raspunsul tau.",
))


class TransactionIntelligenceAgent:
    spec = TRANSACTION_INTELLIGENCE

    def select_tools(self, user_text: str, intent: str) -> list[SelectedTool]:
        if intent == "cont_blocat":
            # Motivul blocarii sta in notificarea scrisa de analist, nu in
            # starea conturilor: `get_accounts` spune CA e blocat, mesajul
            # bancii spune DE CE. Fara al doilea, raspunsul ar fi o
            # generalitate politicoasa exact cand omul are nevoie de un fapt.
            return [
                SelectedTool("get_bank_messages", {}, "ce i-a comunicat banca si de ce"),
                SelectedTool("get_accounts", {}, "care conturi sunt blocate acum"),
                SelectedTool("get_cards", {}, "starea cardurilor"),
                SelectedTool(
                    "search_bank_knowledge",
                    {"query": "cont blocat card blocat contact suport telefon escaladare"},
                    "numarul de telefon potrivit si pasii oficiali",
                ),
            ]

        if intent == "card_question":
            return [
                SelectedTool("get_cards", {}, "detalii despre cardurile proprii"),
                SelectedTool("get_accounts", {}, "cardurile nu au sold propriu, banii sunt in conturi"),
            ]
        if intent == "categorize_receipt_intent":
            # Suma extrasa determinist din text — la fel ca la credit_advisor,
            # nu lasam modelul sa umple argumentul tool-ului. Fara o suma
            # gasita, tool-ul intoarce candidates=[] si modelul (ghidat de
            # prohibited din specs.py) trebuie sa ceara suma explicit.
            suma = extrage_suma(user_text)
            return [
                SelectedTool(
                    "find_transaction_for_receipt", {"suma": suma} if suma is not None else {},
                    "utilizatorul vrea sa lege un atasament de o plata reala",
                ),
            ]
        return [
            SelectedTool("get_recent_transactions", {"limit": 30}, "tranzactii recente pentru analiza"),
            SelectedTool("get_spending_summary", {"days": 30}, "rezumat de cheltuieli pentru context"),
        ]

    async def respond(
        self,
        principal: Principal,
        user_text: str,
        context: AssembledContext,
        tool_results: list[ToolResult],
        chat_provider: ChatProvider,
        attachments: list[AttachmentContext] = (),
    ) -> AgentAnswer:
        system_prompt = build_system_prompt(self.spec, context)
        unelte = _unelte_sesizare() if _e_cont_blocat(tool_results) else None

        # Promptul comun ii interzice sa "inventeze functionalitati" si sa
        # "propuna alternative imaginate" — pe buna dreptate. Fara randurile de
        # mai jos, modelul citea si tool-ul real ca pe ceva neoferit de
        # aplicatie si refuza sa-l foloseasca. Interdictia ramane; se adauga
        # doar faptul ca uneltele astea chiar exista.
        if unelte is not None:
            system_prompt += INSTRUCTIUNI_CONT_BLOCAT

        istoric = [
            ChatMessage(role="system", content=system_prompt),
            build_user_message(user_text, attachments),
        ]

        # Bucla de tool-calling ruleaza doar pe traseul de cont blocat, unde
        # modelul chiar are ceva de compus: rezumatul sesizarii, in cuvintele
        # clientului. In rest, un singur apel — restul intentiilor primesc date
        # deterministe si n-au nevoie ca modelul sa ceara nimic.
        completion, sesizare = await self._raspunde_cu_unelte(chat_provider, istoric, unelte)

        # Daca modelul n-a cerut tool-ul — se intampla, promptul comun il invata
        # sa fie prudent — sesizarea se compune din fapte. Butonul trebuie sa
        # existe cand contul e blocat, nu doar cand modelul s-a gandit la el:
        # altfel omul ramane sa scrie singur ce sistemul stia oricum.
        if unelte is not None and sesizare is None:
            sesizare = _sesizare_din_fapte(user_text, tool_results)

        return AgentAnswer(
            text=completion.text, citations=[], confidence=confidence_from_tool_results(tool_results),
            actiune=sesizare,
            tokens_in=completion.tokens_in, tokens_out=completion.tokens_out, tokens_cached=completion.tokens_cached,
        )


    async def _raspunde_cu_unelte(
        self,
        chat_provider: ChatProvider,
        istoric: list[ChatMessage],
        unelte: list[dict] | None,
    ) -> tuple[object, ActiunePropusa | None]:
        """Cere raspunsul, executand tool-urile pe care le cere modelul.

        Singurul tool oferit aici — `pregateste_sesizare` — nu atinge nimic: doar
        compune un text. Executia lui e locala si se opreste la a-l valida, deci
        bucla n-are cum sa produca efecte in afara conversatiei.

        Plafon de pasi ca peste tot in proiect: un model care intra in cerc nu
        trebuie sa poata consuma o tura intreaga.
        """
        # Fara unelte, apelul ramane exact cum era inainte, cu un singur
        # argument. `complete(mesaje, tools)` e o extindere optionala a
        # contractului, si oricine implementeaza ChatProvider — inclusiv
        # dublurile din teste — trebuie sa poata ramane la forma veche.
        if unelte is None:
            return await chat_provider.complete(istoric), None

        completion = await chat_provider.complete(istoric, unelte)
        sesizare: ActiunePropusa | None = None

        for _ in range(MAX_PASI):
            if not completion.apeluri:
                break

            istoric.append(
                ChatMessage(role="assistant", content=completion.text or "", tool_calls=completion.apeluri)
            )

            for apel in completion.apeluri:
                if apel.nume == "pregateste_sesizare":
                    sesizare = _extrage_sesizare(apel) or sesizare
                    raspuns = (
                        "Sesizarea a fost pregatita si i se arata clientului cu un buton. "
                        "Spune-i sa o trimita apasand butonul. Nu afirma ca a fost trimisa."
                        if sesizare
                        else "Rezumatul e prea scurt. Scrie ce s-a intamplat, in 2-5 propozitii."
                    )
                else:
                    raspuns = f"Tool-ul '{apel.nume}' nu e disponibil aici."

                istoric.append(ChatMessage(role="tool", content=raspuns, tool_call_id=apel.id))

            completion = await chat_provider.complete(istoric, unelte)

        return completion, sesizare



# Descrierea vazuta de model. Aceleasi cuvinte ca in tools/suport_tools.py, dar
# aici trebuie sa fie in forma OpenAI, nu in ToolDefinition-ul nostru.
def _unelte_sesizare() -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": "pregateste_sesizare",
                "description": (
                    "Pregateste o sesizare scrisa catre banca, pe care clientul o trimite el, "
                    "apasand un buton. NU trimite nimic si nu rezolva nimic. Foloseste-l DOAR "
                    "daca clientul cere ajutor in scris sau nu se multumeste cu numarul de "
                    "telefon. Scrie rezumatul la persoana intai, ca si cum l-ar scrie clientul."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "subiect": {
                            "type": "string",
                            "description": "Cateva cuvinte, ex. 'Cont blocat fara explicatie'.",
                        },
                        "rezumat": {
                            "type": "string",
                            "description": (
                                "Ce s-a intamplat si ce cere clientul, la persoana intai, "
                                "in 2-5 propozitii."
                            ),
                        },
                    },
                    "required": ["subiect", "rezumat"],
                },
            },
        }
    ]


def _e_cont_blocat(tool_results: list[ToolResult]) -> bool:
    """Daca omul chiar are un cont oprit de banca.

    Fara verificarea asta, uneltele s-ar oferi si cuiva care intreaba din
    curiozitate ce inseamna un cont blocat — iar modelul ar putea sa-i pregateasca
    o sesizare despre o problema pe care n-o are.
    """
    for rezultat in tool_results:
        if rezultat.tool_name != "get_accounts" or not rezultat.success:
            continue
        for cont in (rezultat.data or {}).get("accounts", []):
            if cont.get("is_blocked"):
                return True
    return False


def _extrage_sesizare(apel) -> ActiunePropusa | None:
    subiect = str(apel.argumente.get("subiect") or "").strip()
    rezumat = str(apel.argumente.get("rezumat") or "").strip()

    if len(subiect) < 3 or len(rezumat) < 10:
        return None

    return ActiunePropusa(
        tip="sesizare_suport",
        eticheta=subiect[:200],
        rezumat=rezumat[:4000],
        context={"subiect": subiect[:200]},
    )


def _mesajul_bancii(tool_results: list[ToolResult]) -> str:
    """Ultima notificare de blocare, fara nota interna a analistului.

    Nota aceea ajunge la client (i-o trimitem noi, in notificare), dar nu are ce
    cauta intr-o scrisoare scrisa de el: nimeni nu citeaza inapoi bancii
    „Observatia analistului: suspect de frauda". Ce se pastreaza e explicatia
    oficiala.
    """
    for rezultat in tool_results:
        if rezultat.tool_name != "get_bank_messages" or not rezultat.success:
            continue
        for mesaj in (rezultat.data or {}).get("messages", []):
            if mesaj.get("kind") != "blocare":
                continue
            text = str(mesaj.get("body") or "").strip()
            taietura = text.find("Observa\u021bia analistului")
            if taietura == -1:
                taietura = text.find("Observatia analistului")
            return (text[:taietura] if taietura > 0 else text).strip()
        break
    return ""


def _sesizare_din_fapte(user_text: str, tool_results: list[ToolResult]) -> ActiunePropusa | None:
    """Sesizarea scrisa din ce se stie, fara model.

    E o scrisoare pe care o semneaza clientul, deci suna a scrisoare: formula de
    adresare, un motiv, o cerere limpede. Contine doar lucruri verificabile —
    ce a comunicat banca si ce a intrebat el.

    Cu diacritice, spre deosebire de comentariile si identificatorii din cod:
    aici textul e citit de un om si trimis in numele lui.
    """
    parti = [
        "Stimat\u0103 echip\u0103 Galaxy Bank,",
        "V\u0103 scriu \u00een leg\u0103tur\u0103 cu blocarea contului meu, despre care am fost "
        "\u00een\u0219tiin\u021bat prin aplica\u021bie.",
    ]

    mesaj = _mesajul_bancii(tool_results)
    if mesaj:
        parti.append(f"Motivul comunicat a fost urm\u0103torul: \u201e{mesaj}\u201d")

    intrebare = (user_text or "").strip()
    if intrebare:
        parti.append(
            "A\u0219 dori s\u0103 l\u0103muresc urm\u0103torul aspect: " + intrebare
        )

    parti.append(
        "V\u0103 rog s\u0103 \u00eemi comunica\u021bi ce pa\u0219i trebuie s\u0103 urmez "
        "pentru deblocarea contului \u0219i \u00een ce interval pot primi un r\u0103spuns."
    )
    parti.append("V\u0103 mul\u021bumesc.")

    return ActiunePropusa(
        tip="sesizare_suport",
        eticheta="Cont blocat",
        rezumat=SEPARATOR.join(parti)[:4000],
        context={"subiect": "Cont blocat", "compus": "determinist"},
    )
