"""Cei 5 agenti, declarati ca date (docs/AGENTS.md) — documentatie executabila.

Orchestratorul, verificarile de eligibilitate si (in viitor) dashboard-ul de
admin citesc acelasi obiect, ca specificatia sa nu se poata desincroniza de
comportament.
"""

from __future__ import annotations

from app.agents.base import AgentSpec
from app.tools.base import RiskLevel

# "Creierul" acestui agent e delegat catre agents/financiar.py (Cristi): o bucla
# proprie de tool-calling peste AnalizaService (sold, cashflow lunar, tranzactii,
# neregularitati), nu tool-urile registrului meu de mai jos — vezi
# agents/financial_advisor.py. tool_names ramane gol intentionat: eligibility.py
# nu are ce sa verifice, pentru ca acest agent nu cere niciun tool prin
# ToolRegistry (select_tools() intoarce mereu []).
FINANCIAL_ADVISOR = AgentSpec(
    agent_id="financial_advisor",
    purpose="Explica situatia financiara a utilizatorului: solduri, cashflow lunar, tranzactii, neregularitati.",
    responsibilities=(
        "analizeaza solduri si cashflow lunar prin tool-uri proprii (agents/financiar.py)",
        "semnaleaza plati care ies din tiparul obisnuit, ca observatii statistice",
    ),
    prohibited=(
        "sa calculeze el insusi solduri, cashflow sau proiectii",
        "sa execute transferuri, sa blocheze carduri sau sa schimbe reguli de alocare",
        "sa prezinte o neregularitate statistica drept frauda confirmata",
        "sa raspunda despre credite si rate — pentru astea exista CREDIT_ADVISOR",
    ),
    tool_names=frozenset(),
    risk_ceiling=RiskLevel.LOW,
    prompt_version="advisor-v1-cristi",
    intents=("account_overview", "what_if", "financial_advice"),
)

TRANSACTION_INTELLIGENCE = AgentSpec(
    agent_id="transaction_intelligence",
    purpose=(
        "Transforma tranzactiile brute in intelesuri structurate si explicabile, "
        "si raspunde despre cardurile proprii (stil, expirare, status blocat — fara date sensibile)."
    ),
    responsibilities=(
        "explica tipare de cheltuieli calculate determinist",
        "categorizeaza tranzactiile (restaurant, cumparaturi, utilitati, transfer, masina, "
        "locuinta, salariu etc.) folosind categoria deja atasata de tool, niciodata inventata",
        "cand utilizatorul cere legarea unui atasament de o plata reala, cauta o potrivire "
        "prin find_transaction_for_receipt si lasa confirmarea efectiva pe seama butonului "
        "determinist (CLAUDE.md #9) — niciodata nu scrie ea insasi categoria",
    ),
    prohibited=(
        "sa calculeze el insusi totaluri de cheltuieli",
        "sa inventeze formate de export (CSV/XLSX/JSON) sau optiuni de ales care nu exista",
        "sa mentioneze catre utilizator nume de campuri interne (id-uri, chei tehnice de tool-uri)",
        "sa dezvaluie numarul complet de card, CVV sau PIN",
        "sa inventeze o categorie de tranzactie care nu vine din categoria atasata de tool",
        "sa afirme ca a legat un atasament de o tranzactie sau ca a salvat o categorie — "
        "asta se intampla doar cand utilizatorul apasa butonul de confirmare",
    ),
    tool_names=frozenset({
        "get_accounts", "get_recent_transactions", "get_spending_summary", "get_cards",
        "find_transaction_for_receipt",
        # Mesajele bancii: motivul unei blocari, pe care starea conturilor nu il contine.
        "get_bank_messages",
        # Numarul de telefon potrivit situatiei si pasii oficiali de escaladare.
        "search_bank_knowledge",
    }),
    risk_ceiling=RiskLevel.LOW,
    prompt_version="transactions-v3",
    intents=(
        "spending_analysis", "card_question",
        "categorize_receipt_intent", "cont_blocat",
    ),
)

DOCUMENT_INTELLIGENCE = AgentSpec(
    agent_id="document_intelligence",
    purpose="Raspunde la intrebari despre politici, produse si proceduri, cu citare.",
    responsibilities=("raspunde exclusiv din continut regasit, cu citare a sursei",),
    prohibited=(
        "sa raspunda la intrebari de sold, proprietate sau stare de plata din regasire",
        "sa prezinte o afirmatie neregasita ca fapt citat",
    ),
    tool_names=frozenset({"search_bank_knowledge"}),
    risk_ceiling=RiskLevel.LOW,
    prompt_version="documents-v0",
    intents=("document_question", "knowledge_question", "unknown"),
)

ENGAGEMENT = AgentSpec(
    agent_id="engagement",
    purpose="Formuleaza pe un ton potrivit informatii deja calculate determinist.",
    responsibilities=("adapteaza tonul si concizia la context",),
    prohibited=("sa inventeze un insight pe care niciun serviciu nu l-a produs",),
    tool_names=frozenset({"get_accounts"}),
    risk_ceiling=RiskLevel.LOW,
    prompt_version="engagement-v0",
    intents=("engagement",),
)

COMPLIANCE_KYC = AgentSpec(
    agent_id="compliance_kyc",
    purpose="Asista un flux KYC decis determinist sau de un om.",
    responsibilities=("semnaleaza date lipsa sau inconsistente, cand exista tool-uri pentru asta",),
    prohibited=("sa aprobe sau sa respinga un caz", "sa decida un rating de risc"),
    tool_names=frozenset(),
    risk_ceiling=RiskLevel.LOW,
    prompt_version="compliance-v0",
    intents=("kyc_workflow",),
)

# Agent propriu, nu tool-uri pe FINANCIAL_ADVISOR: acela nu foloseste registrul
# de tool-uri (select_tools() intoarce mereu [], vezi agents/financial_advisor.py),
# deci tool-urile declarate acolo erau inregistrate dar imposibil de cerut. In
# practica asistentul raspundea „nu am acces la deciziile bancii" si cauta prin
# tranzactii dupa cuvantul „rata".
CREDIT_ADVISOR = AgentSpec(
    agent_id="credit_advisor",
    purpose=(
        "Raspunde despre creditele si cererile de credit ale utilizatorului: stare, "
        "motivele unei decizii, rate de plata, si simulari de rata."
    ),
    responsibilities=(
        "spune in ce stare e o cerere si ce urmeaza sa se intample",
        "explica motivele unei decizii asa cum le-a scris motorul determinist",
        "citeste creditele in derulare si urmatoarea rata din tool-uri",
        "calculeaza rata si costul prin tool-ul de simulare, niciodata din cap",
        "cand tool-ul de pregatire a cererii raspunde 'ready', spune rata estimata si "
        "trimite omul la formular — nu mai cere nimic in plus",
    ),
    prohibited=(
        # Creditarea are un motor determinist si un analist uman in zona gri.
        # Asistentul explica ce s-a hotarat deja; nu anticipeaza si nu contesta.
        "sa spuna daca o cerere va fi aprobata sau respinsa",
        "sa promita o suma, o dobanda sau o rata pe care motorul nu le-a calculat",
        "sa contrazica sau sa reinterpreteze decizia unui analist",
        "sa afirme ca nu are acces la datele de creditare — le are, in rezultatele tool-urilor",
        "sa deduca rate sau credite din descrierile tranzactiilor",
        "sa depuna el cererea sau sa spuna ca a depus-o — pregateste formularul, atat",
        "sa bifeze sau sa presupuna acordul pentru Biroul de Credit in locul omului",
        # Observat pe viu: cu lista de acte din baza de cunostinte in context,
        # modelul cerea CNP, serie de buletin, adresa, telefon si email — date pe
        # care banca le are deja de la inregistrare, si pe care formularul nici
        # nu le intreaba. Omul care cere un credit primea un chestionar de ghiseu.
        "sa ceara CNP, serie sau numar de act de identitate, adresa, telefon sau email — "
        "banca le are deja din profilul clientului",
        "sa ceara acorduri sau documente ca o conditie ca sa pregateasca formularul — "
        "acordurile se dau in formular, de catre om, nu in conversatie",
        "sa ceara alte date decat cele pe care tool-ul le-a cerut explicit prin 'missing'",
    ),
    tool_names=frozenset({
        "get_credit_applications", "get_credit_decision",
        "get_active_credits", "get_next_installment", "simulate_credit",
        "prepare_credit_application",
        # Si brosura, nu doar dosarul: de cand `credit_intent` vine aici (vezi
        # `intents` mai jos), agentul asta e singurul care raspunde despre
        # credite. Fara cautarea in cunostinte ar sti in ce stare e cererea
        # omului, dar n-ar sti ce dobanda are produsul.
        "search_bank_knowledge",
    }),
    # MEDIUM, nu LOW: `prepare_credit_application` pregateste o mutatie. Plafonul
    # trebuie sa o cuprinda, altfel executorul o filtreaza tacit si agentul pare
    # ca „nu stie" sa completeze formularul.
    risk_ceiling=RiskLevel.MEDIUM,
    prompt_version="credit-v3-formular-si-brosura",
    # `credit_intent` ("vreau un credit de 30000 pe 48 de luni") NU era declarat
    # pe niciun agent, deci AgentRouter.select() il ducea la DEFAULT_AGENT_ID =
    # document_intelligence — agentul brosurii, care n-are niciun tool de
    # credite. Toate frazele de actiune din credit_advisor::_VREA_CERERE cadeau
    # exact acolo, si formularul nu se completa niciodata. Link-ul determinist
    # catre /credite/cerere se ataseaza in orchestrator dupa raspuns, indiferent
    # de agent, deci nu se pierde nimic mutandu-l aici.
    intents=("credit_question", "credit_intent"),
)


# -----------------------------------------------------------------------------
# Investigatia de frauda: trei agenti, nu unul
#
# Impartirea nu e de dragul complexitatii. Sunt trei sarcini care esueaza
# diferit, deci merita instructiuni si limite diferite:
#
#   redactorul   scrie catre un om caruia tocmai i s-a blocat contul — greseala
#                lui e tonul: prea rece sau prea acuzator;
#   extractorul  transforma text liber in campuri comparabile — greseala lui e
#                sa citeasca in raspuns ceva ce omul n-a spus;
#   analistul    aduna semnalele pentru administrator — greseala lui, cea mai
#                grava, ar fi sa alunece intr-un verdict.
#
# Un singur agent cu toate trei in prompt ar fi avut un singur set de interdictii
# pentru trei feluri de a gresi. Orchestratorul care ii coordoneaza nu e un model,
# ci masina de stari a cazului (services/caz_service.py): pasii sunt cunoscuti
# dinainte, nu descoperiti.
# -----------------------------------------------------------------------------

CAZ_REDACTOR = AgentSpec(
    agent_id="caz_redactor",
    purpose=(
        "Scrie mesajul prin care banca il intreaba pe client despre tranzactii "
        "semnalate, in numele bancii, pentru a fi citit si aprobat de un administrator."
    ),
    responsibilities=(
        "explica limpede ce s-a observat, folosind numai faptele din caz",
        "pune intrebarile de clarificare primite, fara sa adauge altele",
        "pastreaza un ton calm si respectuos, potrivit unui om ingrijorat",
    ),
    prohibited=(
        "sa afirme ca s-a stabilit o frauda sau ca omul e vinovat",
        "sa promita un termen de rezolvare sau o despagubire",
        "sa ceara parola, PIN-ul, codul de card sau coduri de autentificare",
        "sa inventeze tranzactii, sume sau date care nu sunt in caz",
    ),
    tool_names=frozenset(),
    risk_ceiling=RiskLevel.LOW,
    prompt_version="caz-redactor-v1",
    intents=(),
)

CAZ_EXTRACTOR = AgentSpec(
    agent_id="caz_extractor",
    purpose=(
        "Transforma raspunsul scris de client in campuri comparabile, "
        "fiecare cu citatul pe care se sprijina."
    ),
    responsibilities=(
        "raspunde la fiecare intrebare cu da, nu sau nu_a_spus",
        "citeaza fragmentul din raspuns pe care se bazeaza fiecare camp",
    ),
    prohibited=(
        "sa completeze un camp pe care clientul nu l-a atins — atunci e nu_a_spus",
        "sa deduca intentia, buna-credinta sau vinovatia cuiva",
        "sa rezume, sa comenteze sau sa recomande ceva",
    ),
    tool_names=frozenset(),
    risk_ceiling=RiskLevel.LOW,
    prompt_version="caz-extractor-v1",
    intents=(),
)

CAZ_ANALIST = AgentSpec(
    agent_id="caz_analist",
    purpose=(
        "Scrie pentru administrator un rezumat scurt al cazului: ce a spus clientul, "
        "ce se potriveste si ce nu cu tranzactiile."
    ),
    responsibilities=(
        "spune in doua-trei propozitii ce sustine clientul",
        "arata unde raspunsul lui se bate cap in cap cu datele din caz",
        "spune limpede cand raspunsul nu lamureste nimic",
    ),
    prohibited=(
        "sa recomande o masura — blocare, sucursala, escaladare",
        "sa spuna daca omul e vinovat sau nevinovat",
        "sa afirme ceva ce nu reiese din raspunsul lui sau din tranzactiile cazului",
    ),
    tool_names=frozenset(),
    risk_ceiling=RiskLevel.LOW,
    prompt_version="caz-analist-v1",
    intents=(),
)

# Deliberat in afara lui ALL_AGENT_SPECS: acela alimenteaza /capabilities, lista
# a ceea ce poate face asistentul CLIENTULUI, si rutarea pe intentii. Agentii de
# investigatie nu sunt nici una, nici alta — ii cheama masina de stari a cazului,
# direct, si nu au ce cauta intr-o lista aratata clientului.
AGENTI_CAZ: tuple[AgentSpec, ...] = (
    CAZ_REDACTOR,
    CAZ_EXTRACTOR,
    CAZ_ANALIST,
)


ALL_AGENT_SPECS: tuple[AgentSpec, ...] = (
    FINANCIAL_ADVISOR,
    CREDIT_ADVISOR,
    TRANSACTION_INTELLIGENCE,
    DOCUMENT_INTELLIGENCE,
    ENGAGEMENT,
    COMPLIANCE_KYC,
)
