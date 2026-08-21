# Layer-ul de agenti

## Diagrama, tradusa in cod

```
POST /api/v1/agents/chat
  |
  v
Orchestrator                      app/agents/orchestrator.py
  |-- deleaga_financiar()      -> Agent Financial Advisor   (implementat)
  |-- deleaga_actiuni()        -> Agent Actiuni             (indisponibil)
  |-- deleaga_intrebari_banca()-> Agent RAG Q&A             (indisponibil)
  '-- deleaga_documente()      -> Agent Cititor Doc/Bon     (indisponibil)
```

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

## Ce urmeaza

- **Agent Actiuni** cere intai `TransferService`, cu validare de sold si limite, idempotenta,
  tranzactie atomica si audit (cap. 10). Agentul doar propune; executia ramane in serviciu,
  dupa confirmare explicita in interfata.
- **RAG Q&A** cere o baza de cunostinte si o cautare peste ea: `pgvector` cu embeddings, sau
  cautare full-text in Postgres daca nu vrem inca un furnizor.
- **Cititor Doc/Bon** cere incarcare in Supabase Storage si citire cu Claude ca document.
- **Agregarile** se fac acum in Python. Cand volumul creste, locul lor e o view sau un RPC
  in Postgres; semnaturile din `AnalizaService` raman aceleasi.
