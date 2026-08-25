# Layer-ul de agenti

## Diagrama, tradusa in cod

```
POST /api/v1/assistant/messages
  |
  v
Orchestrator                      app/orchestration/orchestrator.py
  |  intentie -> risc -> tool-uri eligibile -> context -> agent -> validare
  |
  |-- financial_advisor        -> solduri, cashflow, CREDITE   (implementat)
  |-- transaction_intelligence -> tipare de cheltuieli         (implementat)
  |-- document_intelligence    -> RAG peste galaxy-bank-knowledge (implementat)
  |-- engagement               -> formulare pe ton potrivit    (implementat)
  '-- compliance_kyc           -> asista un flux KYC decis deja (implementat)
```

**Atentie la doua orchestratoare in paralel.** Ruta veche
`POST /api/v1/agents/chat` (`app/agents/orchestrator.py` + `baza.py` +
`registru.py` + `financiar.py`) nu mai e chemata de frontend — acesta foloseste
exclusiv `/assistant`. E cod mort in afara de `registru.construieste_analiza`,
folosit inca de `routes/alerte.py`. REGULI.md #2 spune ce urmeaza: se
consolideaza pe unul singur.

Diagrama de mai sus a descris pana in 2026-08-25 o lume in care RAG Q&A si
Cititorul de documente erau „indisponibile". Amandoi exista si ruleaza —
`knowledge_chunks` are peste 200 de fragmente indexate.

Delegarea se face **agent-ca-tool**: fiecare specialist e expus orchestratorului ca un tool
cu schema proprie. Cand e chemat, ruleaza propria bucla de tool use si intoarce un rezultat.

De ce asa si nu un clasificator care ruteaza catre un singur agent: o intrebare mixta
("cat am cheltuit luna asta si blocheaza-mi cardul") cere doi agenti in aceeasi tura.
Un router alege unul singur si pierde jumatate din cerere.

Orchestratorul **nu vede** tool-urile de date ale specialistilor, doar raspunsul lor.
Contextul ramane mic si fiecare agent isi pastreaza propriile granite.

## Fisiere

| Fisier | Rol |
|---|---|
| `app/infrastructure/llm.py` | accesul la model, in spatele unei interfete |
| `app/agents/baza.py` | contractul (`Agent`, `RezultatAgent`, `AgentModel`) si bucla de tool use |
| `app/agents/orchestrator.py` | bucla principala si tool-urile de delegare |
| `app/agents/registru.py` | singurul loc unde se decide ce agenti exista |
| `app/agents/financiar.py` | Financial Advisor |
| `app/agents/actiuni.py`, `rag.py`, `document.py` | agentii inca neimplementati |
| `app/tools/unealta.py` | ce este un tool, independent de furnizor |
| `app/tools/financiar_tools.py` | tool-urile de citire |
| `app/services/analiza_service.py` | read models: sold, cashflow, tranzactii, neregularitati |
| `app/ml/` | detectia platilor atipice |

## Reguli care nu se incalca

1. **`user_id` nu e parametru de tool.** Tool-urile sunt inchideri peste contextul
   autentificat. Modelul nu poate cere datele altui utilizator nici daca i se sugereaza
   asta in mesaj. (ARCHITECTURE.md cap. 7)
2. **Citirile trec prin clientul Supabase al utilizatorului**, cu tokenul lui, deci RLS
   ramane bariera reala din baza de date, nu codul de aici.
3. **`service_role` nu ajunge niciodata intr-un tool** apelat de model. Sta in
   `backend/.env` si se foloseste doar in scripturi si servicii privilegiate.
4. **Niciun agent nu are SQL arbitrar.** Doar tool-uri cu contract. (cap. 8)
5. **Numarul de card, CVV si data expirarii** nu ies din repository: nu sunt in lista de
   coloane selectate.
6. **Nimeni nu muta bani prin asistent** cat timp Agentul Actiuni e indisponibil.

## Cum adaugi un agent

1. Scrii `app/agents/<nume>.py` cu `NUME`, `DESCRIERE`, `INSTRUCTIUNI` si un `construieste()`.
2. Scrii tool-urile in `app/tools/<nume>_tools.py`, ca inchideri peste `user_id`.
3. Il adaugi in lista din `app/agents/registru.py`.

`DESCRIERE` e textul pe care il citeste orchestratorul cand decide pe cine cheama. Scrie-o
pentru el, nu pentru documentatie: ce stie agentul sa faca, in cuvinte pe care le-ar folosi
un utilizator.

## Detectia neregularitatilor

Doua straturi in `app/ml/neregularitati.py`:

1. **Baza statistica** — mediana si deviatia absoluta mediana per comerciant. Merge din prima
   zi, fara antrenare, si e explicabila: "de obicei platesti 40 RON aici, acum 380".
   Prinde: suma atipica, dubla debitare, comerciant nou cu suma mare.
2. **Model antrenat** — `IsolationForest` peste trasaturile din `caracteristici.py`.
   Se antreneaza cu `python -m app.ml.antrenare` si se salveaza in `app/ml/model.joblib`.
   Daca artefactul lipseste, ramane doar stratul 1 si aplicatia merge normal.

Constatarile sunt **statistice, nu fraude dovedite**. Instructiunile agentului si textele
din tool spun explicit asta, ca sa nu ajunga la utilizator ca acuzatii.

Expuse in doua locuri:
- tool `obtine_neregularitati()`, pentru agent;
- `GET /api/v1/alerte`, direct pentru interfata — **nu trece prin niciun model de limbaj**,
  deci merge si fara `ANTHROPIC_API_KEY`.

## Zona de administrator

Rolul sta in `public.user_roles` (`user_id`, `role`), nu in token: un rol pus in JWT ar
ramane valabil pana expira tokenul, inclusiv dupa ce i-a fost luat cuiva dreptul. Se
verifica la fiecare cerere cu `cere_administrator` din `app/api/dependencies.py`.

Doua zone, amandoua sub aceeasi verificare:

| Ruta | Ce face |
|---|---|
| `GET /api/v1/admin/conturi-semnalate` | conturile cu plati atipice |
| `GET /api/v1/admin/raport/{id}` `+/pdf` `+/csv` | raportul de analiza, descarcabil |
| `GET /api/identity/admin/pending` | verificarile care asteapta o hotarare omeneasca |
| `GET /api/identity/admin/case/{id}` | un caz, cu URL-uri semnate catre cele doua poze |
| `POST /api/identity/admin/review` | aproba sau respinge |

Reguli care nu se incalca aici:

1. **Verificarea de rol e pe server, pe fiecare ruta.** Butonul ascuns in interfata nu e o
   bariera; oricine poate chema ruta direct.
2. **Service-role ocoleste RLS.** Citirile administratorului merg cu el (trec peste toate
   conturile), deci autorizarea nu mai vine din baza de date — vine din dependinta, si
   trebuie sa fie acolo fara exceptie.
3. **Pozele raman private.** Se afiseaza prin `create_signed_url` cu durata scurta,
   niciodata `getPublicUrl`.
4. **Fiecare citire lasa o urma** in `public.acces_administrator`: cine s-a uitat la datele
   cui, si cand. Tabela se scrie, nu se modifica si nu se sterge.
5. **Adminul schimba doar decizia.** Dovezile — poze, CNP citit, scor, prag — sunt inghetate
   de un trigger la UPDATE. Altfel un raport de revizuire n-ar mai putea fi verificat.

### Scorul de potrivire a fetelor e o DISTANTA

`identity_verifications.similarity_score` se numeste asa din motive istorice, dar contine
distanta cosinus intoarsa de DeepFace: **mai mic inseamna mai asemanator**, iar potrivirea
trece cand `distanta <= prag` (vezi `infrastructure/face_match.py`).

In API si in interfata se numeste `distanta_fete`, insotita de `prag` si `sub_prag`. Daca ar
fi aratata ca "scor de similaritate", cine revizuieste ar citi 0.37 fata de 0.68 ca esec si
ar respinge un cont bun.

## Configurare

| Variabila | Implicit | Ce face |
|---|---|---|
| `LLM_PROVIDER` | `azure` | furnizorul activ |
| `AZURE_AI_ENDPOINT` | gol | endpoint-ul Foundry |
| `AZURE_AI_AUTH` | `key` | `key` sau `identity` (Entra) |
| `AZURE_AI_API_KEY` | gol | doar pentru `AZURE_AI_AUTH=key` |
| `AZURE_AI_CHAT_DEPLOYMENT` | `gpt-5-mini` | deployment-ul de chat |
| `AZURE_AI_EMBEDDING_DEPLOYMENT` | `text-embedding-3-small` | pentru RAG, cand va exista |
| `AGENT_MAX_TOKENS` | `4000` | plafonul de iesire |
| `AGENT_MAX_PASI` | `10` | plafon de siguranta pentru bucla |

## Furnizorul de model

Activ: **Azure AI Foundry**, deployment `gpt-5-mini`, prin `azure-ai-inference`.

Doua moduri de autentificare, `AZURE_AI_AUTH`:

- `identity` — Entra, prin `DefaultAzureCredential`. Cere `az login` pe masina sau managed
  identity cand aplicatia ruleaza in Azure. **Nicio cheie nu ajunge in vreun fisier.**
  Nu functioneaza in containerul de dev: acolo nu exista nici `az`, nici managed identity.
- `key` — cheia din `.env`. Merge oriunde, inclusiv in container.

De aceea exista doua feluri de a porni local:

| Comanda | Backend | Frontend | Auth Azure |
|---|---|---|---|
| `scripts\dev-local.ps1` | pe masina, cu reincarcare la salvare | container | Entra, fara cheie |
| `scripts\dev-up-cloud.ps1` | container | container | cheie |

Varianta cu backend-ul pe masina e de preferat cand lucrezi la agenti: pornire instant,
reincarcare la salvare si fara secrete pe disc. Frontend-ul ramane in container fiindca
cere Node.js.

Accesul e in spatele interfetei `ClientModel` din `app/infrastructure/llm.py`, cu un singur
tip de raspuns (`RaspunsModel`: text plus tool-uri cerute). Agentii nu stiu ce furnizor e
dedesubt, deci schimbarea inseamna o clasa noua acolo si o linie in `.env`.

Bucla de tool use e scrisa de mana in `ruleaza_bucla` (`app/agents/baza.py`): cere un raspuns,
executa tool-urile cerute, trimite rezultatele inapoi, repeta pana modelul nu mai cere nimic
sau pana la plafon. Doua lucruri tratate explicit acolo, pentru ca modelele le fac in practica:
un tool inventat si argumente invalide primesc un rezultat de eroare in loc sa darame requestul.

Doua observatii din testele pe `gpt-5-mini`, deja reflectate in instructiuni: tinde sa insire
ce NU poate afla, si tinde sa ceara clarificari in loc sa foloseasca valorile implicite ale
tool-urilor. Daca schimbi modelul, reciteste instructiunile din `orchestrator.py` si
`financiar.py` — sunt scrise impotriva acestor doua obiceiuri.

## Pipeline AI de credite (`app/credit/ai/`)

Separat de layer-ul de agenti de mai sus — nu ruleaza in `orchestrator.py` si nu vorbeste cu
utilizatorul. E un pipeline in patru etape care ruleaza **pe langa** motorul determinist de
scoring din `app/credit/` (reguli.py, scorecard.py), niciodata in locul lui.

**Principiul care nu se incalca: strict consultativ.** Nicio etapa nu scrie in
`credit_cereri.status/scor/dti/venit_folosit` si nu insereaza in `credit_verificari_venit` —
scorul ramane reproductibil, ca inainte. Rezultatele merg in trei tabele proprii
(`credit_ai_rulari`, `credit_ai_etape`, `credit_ai_semnale`, migratia 0018), citite doar de
zona de administrare.

| Etapa | Model? | Ce face |
|---|---|---|
| `documente` | da | citeste adeverinta cu un model, in paralel cu regex-ul din `adeverinta.py`; cand difera, diferenta e ea insasi un semnal |
| `coerenta` | **nu** | pur, determinist, testat ca `reguli.py` — coroboreaza declarat/tranzactii/document/istoricul de documente; document reutilizat intre cereri, venit umflat, angajator nepotrivit, incasari "pregatitoare" chiar inainte de cerere |
| `brief` | da | sinteza pentru analistul din zona gri (status `analiza_manuala`): riscuri, atenuari, intrebari de pus, o recomandare cu incredere — niciodata o decizie |
| `explicatie` | da | rescrie `explicatie_determinista` mai cald pentru client, fara sa adauge fapte; singura care ruleaza **sincron**, in `credit_service.evalueaza()` (hook `explica=`), nu prin `CreditAiPipeline` |

Etapele 1-3 sunt orchestrate de `CreditAiPipeline.ruleaza()` (`app/credit/ai/pipeline.py`),
declansat ca task de fundal (`BackgroundTasks`) dupa `evalueaza`/`incarca_document`/
`confirma_document`, plus catch-up lazy la deschiderea dosarului — niciodata pe drumul critic
al unui raspuns. O rulare reusita se refoloseste cat timp datele de intrare nu s-au schimbat
(`intrare_hash`, sha256); butonul "Ruleaza din nou" din dashboard sare peste refolosire.

O etapa care esueaza (Foundry cazut, JSON invalid) se marcheaza `esuat` si pipeline-ul
continua cu urmatoarea — niciodata nu darama fluxul de credit. `coerenta` n-are nevoie de
model, deci tot produce semnale chiar si atunci.

Verificat live (2026-08-24): deployment-ul `gpt-5-mini` din Foundry accepta
`response_format={"type": "json_schema", "strict": true}` (`StructuredChatProvider.complete_json`,
`providers/foundry.py`) — folosit doar de etapele `documente` si `brief`; `explicatie` ramane pe
`ChatProvider.complete()` obisnuit, fiindca produce text, nu campuri.

Vizibil in dashboard: panoul din `/admin/credite/{id}` (semnale, ce a citit modelul, brief),
badge-uri in lista de cereri, si `/admin/credite/ai` (rulari/esecuri pe etapa, cost estimat,
rata de acord AI vs. decizia finala a omului — view-ul SQL `credit_ai_acord`).

## Creditele in asistent (`app/tools/credit_tools.py`)

Pana in 2026-08-25 asistentul nu stia nimic despre creditare: niciun tool,
niciun intent, niciunul din cei cinci agenti. „De ce mi-a fost respinsa
cererea?" cadea pe intentia `unknown`, ajungea la `document_intelligence` si
primea un raspuns din baza de cunostinte despre produsul Galaxy Flex Personal —
corect in general, dar despre altcineva.

Cinci tool-uri, toate `READ_ONLY`/`COMPUTE` si `LOW`, atasate lui
`financial_advisor` (creditele *sunt* situatia financiara a omului; un al
saselea agent ar fi taiat in doua exact contextul de care are nevoie ca sa
raspunda la „imi permit rata asta?"):

| Tool | Ce intoarce |
|---|---|
| `get_credit_applications` | cererile clientului, cu starea si ce urmeaza |
| `get_credit_decision` | scor, DTI, motivele scrise de motor |
| `get_active_credits` | creditele in derulare, cu sold |
| `get_next_installment` | urmatoarea rata neplatita, pe fiecare credit |
| `simulate_credit` | rata, DAE si costul, **prin `app/credit/amortizare`** |

`simulate_credit` e cel care conteaza: cifra vine din acelasi motor ca fluxul
real de creditare, deci rata pe care o spune asistentul e chiar rata pe care ar
primi-o. Un numar produs de model ar fi o promisiune pe care banca n-o poate
onora — aceeasi disciplina ca la pipeline-ul AI de credite: modelul formuleaza,
motorul calculeaza.

`prohibited` din `FINANCIAL_ADVISOR` primeste trei interdictii noi: sa nu spuna
daca o cerere va fi aprobata, sa nu promita o suma sau o dobanda pe care motorul
nu le-a calculat, si sa nu contrazica decizia unui analist.

**Intentia `credit_question`** (`orchestration/intent.py`) sta inaintea lui
`document_question`, altfel „comision"/„termeni" ar fura intrebarile de credit
catre RAG. Dar radacina simpla „credit" **nu** e in lista: „e o oferta buna la
credit ipotecar?" e o intrebare despre produs, la care raspunde baza de
cunostinte. Intra doar formularile personale sau actionabile („creditul meu",
„cererea mea", „ce rata am", „respins"). Exista un test care apara distinctia.

## Ce urmeaza

- **Agent Actiuni** cere intai `TransferService`, cu validare de sold si limite, idempotenta,
  tranzactie atomica si audit (cap. 10). Agentul doar propune; executia ramane in serviciu,
  dupa confirmare explicita in interfata.
- **RAG Q&A** cere o baza de cunostinte si o cautare peste ea: `pgvector` cu embeddings, sau
  cautare full-text in Postgres daca nu vrem inca un furnizor.
- **Cititor Doc/Bon** cere incarcare in Supabase Storage si citire cu Claude ca document.
- **Agregarile** se fac acum in Python. Cand volumul creste, locul lor e o view sau un RPC
  in Postgres; semnaturile din `AnalizaService` raman aceleasi.
