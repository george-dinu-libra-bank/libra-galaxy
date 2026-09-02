# HARTA — ce este construit în Galaxy Bank și unde stă

> **Ce e documentul ăsta și ce nu e.**
>
> E o hartă **descriptivă**: ce există în repo acum, unde, și cum se leagă. Celelalte
> patru documente din rădăcină sunt **prescriptive** — spun ce e voie:
> [ARCHITECTURE.md](ARCHITECTURE.md) (regulile de arhitectură), [DESIGN.md](DESIGN.md)
> (interfața), [GUARDRAILS.md](GUARDRAILS.md) (asistentul), [REGULI.md](REGULI.md)
> (lecțiile verificate live). Unde regula contează, trimit la ele; nu le rescriu.
>
> Secțiunile 1–3 și 10 sunt cele bune de prezentat. Secțiunile 11 și 12 sunt pentru un
> agent care intră în cod.
>
> Inventarul din secțiunea 12 e generat din ce scrie **fiecare fișier despre el însuși**
> (docstring / comentariul de sus), nu din presupuneri după nume. Unde fișierul nu spune
> nimic, scrie explicit „fără descriere proprie" — un gol vizibil e mai onest decât o
> descriere inventată, care ar arăta la fel de sigură ca restul.

---

## 1. Ce e Galaxy Bank

O aplicație de internet banking completă, construită ca proiect de învățare pe
infrastructură reală: clientul își vede conturile și cardurile, trimite bani, schimbă
valută, ține pungi comune cu prietenii, cere credite și vorbește cu un asistent AI care
îi răspunde din documentația băncii. În spate există o zonă de administrare unde un
analist verifică identități, se uită la plăți atipice, decide cereri de credit, blochează
conturi și pune popriri.

Două lucruri o fac mai puțin obișnuită decât pare:

1. **Regulile bancare stau în baza de date, nu în aplicație.** Mișcarea banilor se face
   prin funcții PostgreSQL (`core_banking` și rudele ei), iar interdicțiile sunt
   *triggere*, nu verificări în TypeScript. Un buton dezactivat e o sugestie; o excepție
   din bază e o regulă. Consecința practică: cine cheamă API-ul direct, ocolind
   interfața, se lovește de exact aceleași bariere.
2. **Partea de AI nu are voie să atingă baza direct.** Agenții văd doar *unelte*
   declarate explicit, deterministe, care în marea lor majoritate doar citesc.

Totul e scris în **română** — nume de funcții, coloane, componente, comentarii. Nu e o
ciudățenie de stil: face codul citibil de către cei care cunosc domeniul bancar românesc,
și e o convenție ținută consecvent (vezi secțiunea 9).

---

## 2. Harta în 30 de secunde

```text
                          CLIENT (browser)
                                 |
                    +------------+------------+
                    |   Next.js 16 (React)    |   :3000
                    |   App Router, RSC       |
                    +----+---------------+----+
                         |               |
       Supabase SDK      |               |   backendFetch (JWT-ul userului)
       (operatiuni       |               |
        simple, RLS)     |               v
                         |     +-------------------+
                         |     |  FastAPI (Python) |   :8000
                         |     +---------+---------+
                         |               |
                         |     +---------+---------+
                         |     | Servicii | Agenti |
                         |     +---------+---------+
                         |               |
                         |          Unelte (tools)
                         |               |
                         |        Repositories
                         v               v
                    +---------------------------+
                    |   Supabase PostgreSQL     |
                    |   RLS + triggere + RPC    |
                    +---------------------------+
```

**Două drumuri legitime de la Next.js la date**, și amândouă sunt intenționate
(ARCHITECTURE.md §2):

| Drum | Când | Exemplu real |
|---|---|---|
| Next.js → Supabase SDK → Postgres | operațiuni simple, ale utilizatorului, apărate de RLS | citirea conturilor proprii ([lib/data/conturi.ts](frontend/src/lib/data/conturi.ts)) |
| Next.js → FastAPI → serviciu/agent → unealtă/repository → Postgres | logică de business, operațiuni privilegiate, AI | decizia analistului pe o poprire ([lib/actions/admin-popriri.ts](frontend/src/lib/actions/admin-popriri.ts)) |

**Unde stă adevărul, pe scurt:** banii și interdicțiile în Postgres; regulile de business
în FastAPI; reasoning-ul în agenții Python; interfața în Next.js. Niciun secret în browser.

---

## 3. Cum pornește

`docker compose up --build` din rădăcină pornește tot. Nimeni nu instalează Node sau
Python local (REGULI.md §5) — dacă `npm` nu există pe mașina ta, e normal; comenzile se
dau în container: `docker exec libra-frontend npm run typecheck`.

| Serviciu | Container | Port | Ce rulează |
|---|---|---|---|
| Frontend | `libra-frontend` | 3000 | `next dev` |
| Backend | `libra-backend` | 8000 | `uvicorn --reload` |

- `./start.ps1` / `./start.sh` verifică Docker, creează `.env` din `.env.example` dacă
  lipsește, apoi ridică stiva.
- Baza de date **nu** e locală: e un proiect Supabase în cloud (`LibraGalaxy`,
  regiunea `eu-west-1`).
- `galaxy-bank-knowledge/` e montat **read-only** în backend — RAG-ul îl citește, nu
  scrie niciodată în el.

**Capcana zilnică pe Windows** (REGULI.md §8): `next dev` nu prinde modificările din
`frontend/src` prin bind mount. Servește build-ul vechi din cache și pare că n-ai
schimbat nimic. După orice modificare de componentă: `docker compose restart frontend`.
Backendul, cu `uvicorn --reload`, le prinde corect — de-aia diferența e ușor de ratat.

---

## 4. Frontend (Next.js)

`frontend/src/app` — App Router, cu trei grupuri de rute care au cadre diferite:

| Grup | Ce e | Sesiune |
|---|---|---|
| `(app)` | aplicația clientului: dashboard, transfer, carduri, credite, grupuri, istoric, asistent, setări | da |
| `(ecommerce)` | magazinul demonstrativ, care cere plăți cu carduri Galaxy | nu |
| `admin` | zona analistului | da + rol de administrator |

**Separarea care contează cel mai mult** e între `lib/data/` și `lib/actions/`:

- **`lib/data/*`** — citiri. Rulează pe server, întorc date pentru randare.
- **`lib/actions/*`** — mutații (`"use server"`). Fiecare își verifică **singură** drepturile
  la intrare: o server action e un endpoint ca oricare altul, apelabil direct, nu doar
  un handler de buton.

Ambele straturi convertesc codurile de eroare din baza de date în propoziții pentru om.
Dicționarele sunt în [transfer.ts](frontend/src/lib/actions/transfer.ts),
[grupuri.ts](frontend/src/lib/actions/grupuri.ts),
[schimb-valutar.ts](frontend/src/lib/actions/schimb-valutar.ts) și
[services/plati.ts](frontend/src/lib/services/plati.ts) — patru locuri, fiindcă patru
fluxuri diferite ating aceleași funcții de bani. Când adaugi un cod nou de eroare în
Postgres, toate patru trebuie să îl cunoască, altfel unul dintre fluxuri arată „a apărut
o eroare neașteptată" pentru o situație perfect normală. Codurile de drepturi de grup
(`CHELTUIALA_INTERZISA`, `LIMITA_GRUP_DEPASITA`) sunt un exemplu proaspăt: plata dintr-un
grup trece prin `actions/transfer.ts`, nu prin `actions/grupuri.ts`, deci acolo trebuie să
fie traducerea care contează.

---

## 5. Backend (FastAPI)

Lanțul e strict: **rută → serviciu → repository → Supabase**.

- **`api/routes/`** — HTTP și atât: validare, verificare de rol, traducerea excepțiilor
  în coduri de stare. Fără reguli bancare.
- **`services/`** — logica de business (credite, rapoarte, analize, identitate).
- **`repositories/`** — singurul strat care vorbește cu Supabase. Fiecare interogare
  sincronă e rulată prin `anyio.to_thread.run_sync`, fiindcă `supabase-py` e sincron.

**Care client Supabase se folosește nu e un detaliu, e o decizie de securitate:**

| Dependință | Client | Când |
|---|---|---|
| `get_user_supabase` | tokenul utilizatorului | citiri apărate de RLS — dacă i se ia rolul, următoarea cerere nu mai întoarce nimic |
| `get_admin_supabase` | `service_role` | scrieri în tabele fără politici de insert, și RPC-urile privilegiate. Trece peste RLS, deci ruta **își verifică singură** drepturile |

`cere_administrator` e prima barieră; RLS-ul e a doua, și aceea e cea care contează.

---

## 6. Baza de date

45 de tabele, toate cu RLS activat (verificat în baza reală, nu numărate din fișiere). Sursa de adevăr pentru bani.

**Trei lucruri de știut înainte să atingi ceva aici:**

1. **`supabase_migrations` e GOL în cloud.** Fișierele din `supabase/migrations/` descriu
   *intenția*, nu istoricul aplicat, și cele două chiar au divergat (`0008` nu e aplicat).
   **Verifică schema reală** cu `list_tables` prin MCP înainte să te bazezi pe un fișier
   (REGULI.md §3).
2. **Numerotarea migrațiilor e strict aditivă**, iar numărul următor liber se verifică pe
   `origin/main` proaspăt fetch-uit — coliziunea s-a întâmplat deja pe trei numere deodată.
3. **Barierele sunt triggere, nu cod.** Un trigger pe `conturi_bancare` prinde *orice*
   drum prin care scade soldul, inclusiv cele scrise mâine, fără să rescrie funcțiile de
   bani. Două astfel de bariere există azi:

| Trigger | Migrație | Ce oprește |
|---|---|---|
| `conturi_before_update_blocare` | [0030](supabase/migrations/0030_blocare_cont.sql) | **tot** ce pleacă dintr-un cont blocat administrativ |
| `conturi_before_update_poprire` | [0047](supabase/migrations/0047_poprire.sql) | ieșirile care ar coborî soldul cumulat sub **suma poprită** |

Poprirea are trei operațiuni, și confuzia dintre ultimele două costă bani:

| Operațiune | Ce face | Ce NU face |
|---|---|---|
| `incaseaza_poprirea` | virează către creditor, în tranșe | — |
| `ridica_poprirea` | oprește poprirea; banii rămași se eliberează | **nu** aduce înapoi ce s-a virat deja |
| `storneaza_incasarea` ([0048](supabase/migrations/0048_poprire_stornare.sql)) | aduce banii virați înapoi în contul clientului | **nu** oprește poprirea |

O poprire pusă din greșeală și deja încasată se repară cu amândouă, în ordinea:
întâi stornarea (vin banii), apoi ridicarea (nu-i mai ține nimeni). Dacă stornezi fără
să ridici, banii întorși redevin indisponibili pe loc — corect, fiindcă datoria a
redevenit neplătită.

Ordinea lor nu e întâmplătoare: Postgres rulează triggerele BEFORE în ordinea alfabetică a
numelui, iar `...blocare` vine înaintea lui `...poprire`, ca un cont blocat să fie refuzat
cu motivul lui adevărat.

**A treia barieră nu e un trigger, și are un motiv.** Drepturile de cheltuială dintr-un
grup ([0053](supabase/migrations/0053_drepturi_grup.sql)) nu depind doar de rândul atins,
ci de **cine** cheltuiește — iar ambele funcții care scot bani din punga comună rulează și
sub `service_role`, unde `auth.uid()` e null. Un trigger pe `groups` n-ar avea de unde să
afle utilizatorul. Deci verificarea trăiește într-o funcție comună,
`verifica_drept_cheltuiala_grup`, chemată explicit — **și** din `core_banking_groups`
(direcția `plata`), **și** din `transfer_semnalat` (ramura de grup), în amândouă *după*
`for update` pe rândul grupului, ca două plăți simultane să nu treacă peste același rest de
plafon. Cine adaugă un al treilea drum prin care scade `groups.sold` trebuie să o cheme și
el: aici compilatorul nu ajută, spre deosebire de un trigger.

Plafonul e lunar și se numără din `tranzactii` (`id_group_send` + `id_user_send`, luna
curentă, fără `anulata`), nu dintr-un contor ținut de mână — un contor s-ar putea
desincroniza de istoric, iar istoricul e oricum sursa de adevăr. Rândurile `flagged` **se**
numără: banii au plecat deja din grup, chiar dacă așteaptă un administrator.

**Funcțiile de bani** (`core_banking`, `core_banking_groups`, `schimba_valuta_suma`, plata
cu cardul, operațiunile de credit) fac totul într-o singură tranzacție, cu `for update` pe
rândurile atinse. Ridică coduri scurte (`FONDURI_INSUFICIENTE`, `CONT_BLOCAT`,
`POPRIRE_ACTIVA`) pe care aplicația le traduce.

**Vocabular închis:** `notificari.tip` acceptă doar `info | atentionare | blocare |
deblocare`. Un al cincilea cuvânt inventat dă rollback la operațiunea întreagă, iar
insertul e ultimul pas — deci banii se mișcă, apoi totul se dă înapoi. S-a întâmplat;
vezi [0042](supabase/migrations/0042_notificari_tip_valid.sql).

---

## 7. AI

**Pipeline-ul unui mesaj**, în ordinea reală din
[orchestration/orchestrator.py](backend/app/orchestration/orchestrator.py):

```text
mesaj -> guardrail de intrare -> clasificare intentie -> risc -> alegere agent
      -> selectie unelte -> executie unelte -> context -> model -> redactare -> raspuns
```

Ce e **determinist** aici (adică nu depinde de model, și e testat ca atare): guardrail-ul
de intrare, clasificarea intenției, rutarea către agent, riscul, eligibilitatea uneltelor
și redactarea de la ieșire. Modelul scrie propoziții; nu decide cine are voie ce.

- **`tools/`** — singura punte agent → aplicație. Deterministe, aproape toate doar citesc.
- **`rag/`** — indexează `galaxy-bank-knowledge/` în
  `knowledge_chunks` — 74 de fișiere Markdown, din care 72 indexabile (`DOCUMENT-INDEX.md` și
  `README.md` sunt excluse explicit) — cu chunk-uri adresate prin conținut (sha256), deci reindexarea e
  incrementală. Regăsirea aplică filtrele *înainte* de similaritate.
- **`memory/`** — memorie per utilizator, expirabilă, **niciodată** sursă de adevăr pentru
  solduri sau tranzacții.

---

## 8. Fluxuri cap-coadă

### 8.1 Un transfer de bani

```text
transfer-form.tsx
  -> actions/transfer.ts        validari ieftine + contEsteBlocat() pentru un mesaj omenesc
  -> rpc("core_banking")        verifica, debiteaza, crediteaza, scrie istoricul — o tranzactie
       |- trigger blocare       (0030) refuza daca contul e blocat administrativ
       |- trigger poprire       (0047) refuza daca ar coboare sub suma poprita
  -> MESAJE_CORE_BANKING        codul devine propozitie
  -> revalidatePath(...)        dashboard, carduri, istoric, transfer
```

Verificarea din TypeScript (`contEsteBlocat`) e o **comoditate, nu bariera** — există ca
omul să primească un mesaj clar înainte, nu ca să oprească ceva. Bariera e în bază.

### 8.2 O cerere de credit

```text
/credite/cerere -> FastAPI /api/v1/credite -> credit_service
  -> credit/reguli.py       criterii hard: ce respinge fara discutie
  -> credit/venit.py        venitul dedus din incasarile reale
  -> credit/scorecard.py    punctajul de bonitate
  -> credit/ai/pipeline.py + etape/   semnale CONSULTATIVE pentru analist
  -> decizia analistului in /admin/credite
```

Partea de AI e strict consultativă: nicio coloană din `credit_ai_*` nu e citită de motorul
de scoring. Etapa `coerenta` nu folosește deloc model — e deterministă.

### 8.3 Verificarea de identitate

Buletin + selfie → calitatea pozei verificată local → Azure Document Intelligence (OCR) →
DeepFace pentru potrivirea fețelor → `identity_service` → coada din `/admin`, unde un om
poate forța sau restabili. Istoricul încercărilor stă în `identity_verifications`;
`profiles.verification_status` reflectă ultima.

### 8.4 Asistentul

Vezi pipeline-ul din secțiunea 7. Uneltele citesc din conturile și tranzacțiile reale ale
celui care întreabă — niciodată ale altcuiva, niciodată numărul complet de card sau CVV-ul.

### 8.5 Ciclul de viață al unui cont

```text
deschidere (max 10/om)
  -> blocare administrativa (0030)      tot ce pleaca se opreste
  -> poprire (0047)                     o suma devine indisponibila, pe toate conturile
       |- incasare                     banii pleaca la creditor, in transe
       |- stornare (0048)              reverse: banii virati se intorc in cont
       |- ridicare                     poprirea inceteaza
  -> inchiderea contului (0040)         banii se muta, cardurile se inchid, contul ramane in istoric
  -> plecarea din banca (0036-0038)     consolidare, apoi stergerea clientului
```

„Închis, nu șters" e o decizie explicită: `inchis_la` în loc de `delete`, ca istoricul să
păstreze numele contului și ca o greșeală să poată fi reparată (`redeschide_cont`).

---

## 9. Convenții

- **Româna peste tot** — nume de funcții, coloane, componente, comentarii, mesaje. Fără
  diacritice în SQL și în comentariile din cod; cu diacritice în textele pentru utilizator.
- **Migrațiile poartă motivul, nu doar SQL-ul.** Antetul fiecărei migrații explică ce
  problemă reală rezolvă și ce alternativă a fost respinsă. Când citești una, citește
  antetul întâi.
- **O server action își verifică singură drepturile**, chiar dacă ecranul din care e
  chemată o face deja.
- **Un `{ date, eroare }` din care nu destructurezi `eroare` e o minciună tăcută** — o
  listă goală și o listă care n-a putut fi încărcată trebuie să arate diferit
  (REGULI.md §8).
- **Sumele sunt `numeric(14,2)`** și circulă ca text până la afișare; aritmetica se face
  în bani (întregi) acolo unde se poate.

---

## 10. Ce NU e construit (și discrepanțe reale)

De citit înainte de o prezentare, ca să nu promiți ce nu există.

**Limite funcționale asumate:**

- **Poprirea nu cunoaște veniturile neurmăribile** — cota de 1/3 din salariu, pensiile sub
  plafon, ordinea de prioritate între mai mulți creditori, expirarea automată. Sunt decizii
  juridice, nu tehnice, și nu s-au inventat în cod.
- Nu există integrare reală cu ANAF / e-Poprire, cu Biroul de Credit (există un substitut,
  `credit_bureau_simulat`), și nici cu un sistem interbancar: „banca" e închisă în ea însăși.
- Magazinul din `(ecommerce)` e o demonstrație pentru fluxul de plată, nu un magazin.

**Discrepanțe între ce spune codul și ce există** — semnalate, nu rezolvate tacit:

1. **Codul citează șase documente care nu există în repo.** Docstring-urile trimit la
   `docs/AI_ARCHITECTURE.md`, `docs/SECURITY.md`, `docs/API_CONVENTIONS.md`,
   `docs/DATABASE.md`, `PROJECT_CONTEXT.md`, `CLAUDE.md` și `PATTERN_ADOPTION.md`. Singurul
   care există e [docs/AGENTS.md](docs/AGENTS.md). Regulile citate sunt respectate în cod,
   dar nu se pot verifica împotriva sursei.
2. **Două stive de agenți în paralel**, exact ce interzice REGULI.md §2: `agents/base.py`
   lângă `agents/baza.py`, `agents/orchestrator.py` lângă `orchestration/orchestrator.py`,
   iar `infrastructure/config.py` e explicit un shim de compatibilitate peste
   `core/config.py`. Consolidarea e o decizie deschisă.
3. **`DOCUMENT-INDEX.md` e incomplet** — nu listează `conturi/inchidere-cont.md` și
   `conturi/inchidere-cont-bancar.md`. Nu are efect asupra asistentului: RAG-ul citește
   folderul și exclude explicit indexul ([rag/registry.py](backend/app/rag/registry.py)).
   E un artefact pentru oameni, rămas în urmă.
4. **`conturi_opreste_iesirile_daca_blocat()` (0030) e apelabilă prin `/rest/v1/rpc/`** de
   oricine, ca funcție `SECURITY DEFINER` — raportată de `get_advisors`. Nu poate face rău
   (o funcție de trigger fără context de trigger crapă), dar nu are ce căuta în API.
   Echivalenta ei din 0047 a fost revocată; asta nu, fiind altă migrație.

---

## 11. Pentru un agent Claude care intră aici

**Citește în ordinea asta:** [REGULI.md](REGULI.md) (lecțiile plătite deja) →
[ARCHITECTURE.md](ARCHITECTURE.md) (ce e voie) → documentul de față (ce există) →
[GUARDRAILS.md](GUARDRAILS.md) și [DESIGN.md](DESIGN.md) dacă atingi asistentul sau
interfața.

**Greșelile deja documentate, ca să nu le repeți:**

| Capcană | Unde scrie |
|---|---|
| Migrație numerotată după branch-ul local, nu după `origin/main` | REGULI.md §3 |
| Te bazezi pe fișierul de migrație în loc de schema reală | REGULI.md §3 |
| Cauți un bug de frontend fără să repornești containerul | REGULI.md §8 |
| `maybeSingle()` pe `user_roles` (aruncă la două rânduri) | REGULI.md §8 |
| Presupui că RLS de select și de update coincid | REGULI.md §8 |
| Tipezi ca `str` un `numeric` venit prin PostgREST (RPC îl dă **float**) | [0047](supabase/migrations/0047_poprire.sql), `PoprireResponse` |
| Inventezi o valoare pentru `notificari.tip` | [0042](supabase/migrations/0042_notificari_tip_valid.sql) |
| Pui bariera în TypeScript în loc de bază | [0030](supabase/migrations/0030_blocare_cont.sql) |

**Ordinea de verificare, de la ieftin la scump** (REGULI.md §7): `pytest` →
`npm run typecheck` (în container) → apel live cu credențiale reale → container construit
și pornit, cu request real prin el. Nu se declară nimic „gata" doar din citirea codului.

**Git rămâne al omului** — Claude nu rulează `git add` / `commit` / `push` (REGULI.md §9).

---

## 12. Inventar de fișiere

Un rând per fișier sursă, cu descrierea pe care și-o dă el însuși.

### Backend — rute HTTP si compunerea aplicatiei

| Fișier | Ce face |
|---|---|
| [dependencies.py](backend/app/api/dependencies.py) | Compunerea aplicatiei: cladeste orchestratorul o singura data, din setari validate. |
| [routes/admin.py](backend/app/api/routes/admin.py) | Zona administratorului: conturile semnalate si rapoartele lor. |
| [routes/admin_identity.py](backend/app/api/routes/admin_identity.py) | Revizuirea manuala a verificarilor de identitate. |
| [routes/agents.py](backend/app/api/routes/agents.py) | _(fără descriere proprie în fișier)_ |
| [routes/alerte.py](backend/app/api/routes/alerte.py) | _(fără descriere proprie în fișier)_ |
| [routes/assistant.py](backend/app/api/routes/assistant.py) | _(fără descriere proprie în fișier)_ |
| [routes/credite.py](backend/app/api/routes/credite.py) | Rutele de creditare, sub /api/v1. |
| [routes/health.py](backend/app/api/routes/health.py) | GET /health — nume de deployment si flag configurat/neconfigurat, niciodata chei (docs/SECURITY.md #4). |
| [routes/identity.py](backend/app/api/routes/identity.py) | _(fără descriere proprie în fișier)_ |
| [routes/profiles.py](backend/app/api/routes/profiles.py) | _(fără descriere proprie în fișier)_ |

### Backend — nucleu (config, erori, logging, securitate)

| Fișier | Ce face |
|---|---|
| [config.py](backend/app/core/config.py) | Singurul modul care citeste variabile de mediu (ARCHITECTURE.md #14, SECURITY.md #4). |
| [envelope.py](backend/app/core/envelope.py) | Plicul de raspuns standard (docs/API_CONVENTIONS.md #1). |
| [errors.py](backend/app/core/errors.py) | Ierarhie de erori -> cod stabil -> status HTTP (docs/API_CONVENTIONS.md #2). |
| [logging.py](backend/app/core/logging.py) | Logging JSON structurat, cu id-uri de corelare si redactare (docs/SECURITY.md #3). |
| [redaction.py](backend/app/core/redaction.py) | Mascare de date sensibile. |
| [security.py](backend/app/core/security.py) | Principal si verificarea JWT-ului real emis de Supabase Auth (docs/SECURITY.md #1). |

### Backend — infrastructura (retea, storage, OCR, model)

| Fișier | Ce face |
|---|---|
| [attachment_storage.py](backend/app/infrastructure/attachment_storage.py) | Upload/download in bucket-ul privat Supabase Storage — singurul loc care vorbeste cu Storage. |
| [audit.py](backend/app/infrastructure/audit.py) | Urma pe care o lasa agentii. |
| [calitate_poza.py](backend/app/infrastructure/calitate_poza.py) | Verificarea calitatii unei poze inainte sa ajunga la DeepFace sau la OCR. |
| [citire_adeverinta.py](backend/app/infrastructure/citire_adeverinta.py) | Citirea unei adeverinte de venit incarcate — de la octeti la cifre. |
| [cnp.py](backend/app/infrastructure/cnp.py) | Gasirea unui CNP intr-un text citit de masina. |
| [config.py](backend/app/infrastructure/config.py) | Compat: re-exporta app.core.config, ca modulele care inca importa de aici (agents/{orchestrator,baza,financiar,registru}.py, llm.py, api/routes/{agents,alerte,profiles}.py) sa nu ceara editat un impor... |
| [document_text.py](backend/app/infrastructure/document_text.py) | Text dintr-un fisier incarcat, indiferent daca e poza sau PDF — fara retea. |
| [export_storage.py](backend/app/infrastructure/export_storage.py) | Upload/URL semnat pentru fisiere generate de aplicatie (nu incarcate de utilizator). |
| [face_match.py](backend/app/infrastructure/face_match.py) | _(fără descriere proprie în fișier)_ |
| [llm.py](backend/app/infrastructure/llm.py) | Accesul la model, in spatele unei interfete. |
| [ocr.py](backend/app/infrastructure/ocr.py) | _(fără descriere proprie în fișier)_ |
| [rate_limit.py](backend/app/infrastructure/rate_limit.py) | _(fără descriere proprie în fișier)_ |
| [supabase.py](backend/app/infrastructure/supabase.py) | _(fără descriere proprie în fișier)_ |
| [supabase_client.py](backend/app/infrastructure/supabase_client.py) | Singurul modul care importa supabase-py (paralela cu regula Mongo din docs/DATABASE.md). |

### Backend — furnizori externi (Azure, Foundry)

| Fișier | Ce face |
|---|---|
| [base.py](backend/app/providers/base.py) | _(fără descriere proprie în fișier)_ |
| [document_intelligence.py](backend/app/providers/document_intelligence.py) | Azure AI Document Intelligence (REST) — OCR pe documente incarcate. |
| [foundry.py](backend/app/providers/foundry.py) | Microsoft Foundry — o singura implementare, fara fallback. |
| [voice.py](backend/app/providers/voice.py) | Azure AI Speech (REST) — transcribe si synthesize, canal separat de Foundry (PROJECT_CONTEXT.md #33). |

### Backend — acces la date (singurul strat care atinge Supabase)

| Fișier | Ce face |
|---|---|
| [admin_repository.py](backend/app/repositories/admin_repository.py) | _(fără descriere proprie în fișier)_ |
| [attachment_repository.py](backend/app/repositories/attachment_repository.py) | _(fără descriere proprie în fișier)_ |
| [banking_read_repository.py](backend/app/repositories/banking_read_repository.py) | _(fără descriere proprie în fișier)_ |
| [card_repository.py](backend/app/repositories/card_repository.py) | _(fără descriere proprie în fișier)_ |
| [cont_repository.py](backend/app/repositories/cont_repository.py) | _(fără descriere proprie în fișier)_ |
| [conversation_repository.py](backend/app/repositories/conversation_repository.py) | _(fără descriere proprie în fișier)_ |
| [credit_ai_repository.py](backend/app/repositories/credit_ai_repository.py) | Accesul la datele pipeline-ului AI de credite (0018_credit_ai_pipeline.sql). |
| [credit_repository.py](backend/app/repositories/credit_repository.py) | Accesul la datele de creditare. |
| [embedding_cache_repository.py](backend/app/repositories/embedding_cache_repository.py) | _(fără descriere proprie în fișier)_ |
| [identity_repository.py](backend/app/repositories/identity_repository.py) | _(fără descriere proprie în fișier)_ |
| [knowledge_repository.py](backend/app/repositories/knowledge_repository.py) | _(fără descriere proprie în fișier)_ |
| [memory_repository.py](backend/app/repositories/memory_repository.py) | _(fără descriere proprie în fișier)_ |
| [message_repository.py](backend/app/repositories/message_repository.py) | _(fără descriere proprie în fișier)_ |
| [profile_repository.py](backend/app/repositories/profile_repository.py) | _(fără descriere proprie în fișier)_ |
| [summary_repository.py](backend/app/repositories/summary_repository.py) | _(fără descriere proprie în fișier)_ |
| [telemetry_repository.py](backend/app/repositories/telemetry_repository.py) | _(fără descriere proprie în fișier)_ |
| [tranzactie_repository.py](backend/app/repositories/tranzactie_repository.py) | _(fără descriere proprie în fișier)_ |

### Backend — logica de business

| Fișier | Ce face |
|---|---|
| [admin_identity_service.py](backend/app/services/admin_identity_service.py) | Cazurile de verificare a identitatii, pentru administrator. |
| [analiza_cont_service.py](backend/app/services/analiza_cont_service.py) | Hotararea administratorului asupra unui cont semnalat. |
| [analiza_service.py](backend/app/services/analiza_service.py) | Read models: sume agregate, nu tabele brute (cap. |
| [credit_explicatie.py](backend/app/services/credit_explicatie.py) | Motivarea deciziei, in limbaj natural. |
| [credit_service.py](backend/app/services/credit_service.py) | Orchestrarea creditarii: simulare, cerere, verificari, decizie, acordare, rate. |
| [identity_service.py](backend/app/services/identity_service.py) | _(fără descriere proprie în fișier)_ |
| [profile_service.py](backend/app/services/profile_service.py) | _(fără descriere proprie în fișier)_ |
| [raport_service.py](backend/app/services/raport_service.py) | Raportul de analiza pentru un cont semnalat. |
| [sinteza.py](backend/app/services/sinteza.py) | Paragraful de sinteza al raportului, scris de model. |
| [transaction_export_service.py](backend/app/services/transaction_export_service.py) | Export determinist al tranzactiilor proprii, ca PDF (docs/AI_ARCHITECTURE.md). |

### AI — orchestrare, intentie, rutare, guardrails

| Fișier | Ce face |
|---|---|
| [input_guardrail.py](backend/app/orchestration/input_guardrail.py) | Detectie determinista de prompt injection / suprascriere de instructiuni / extractie de secrete, inainte ca mesajul sa ajunga la vreun agent sau LLM (GUARDRAILS.md #3.1, #10, #18, Scenariul C). |
| [intent.py](backend/app/orchestration/intent.py) | Clasificare de intentie determinista, RO/EN, insensibila la diacritice (docs/AI_ARCHITECTURE.md #2). |
| [orchestrator.py](backend/app/orchestration/orchestrator.py) | Pipeline-ul complet (docs/AI_ARCHITECTURE.md #2, PROJECT_CONTEXT.md #16). |
| [output_guardrail.py](backend/app/orchestration/output_guardrail.py) | Redactare determinista a raspunsului final — plasa de siguranta daca modelul nu respecta instructiunile din prompt (GUARDRAILS.md #14, #23). |
| [risk.py](backend/app/orchestration/risk.py) | Risc derivat din intentie, niciodata din formularea mesajului (docs/AI_ARCHITECTURE.md #2). |
| [routing.py](backend/app/orchestration/routing.py) | Rutare determinista intentie -> agent (docs/AGENTS.md #4). |

### AI — agenti

| Fișier | Ce face |
|---|---|
| [actiuni.py](backend/app/agents/actiuni.py) | Agent Actiuni — executa operatiuni cerute de utilizator. |
| [base.py](backend/app/agents/base.py) | Contractul unui agent (docs/AGENTS.md) — nu se apeleaza intre ei, nu depasesc tool-urile declarate. |
| [baza.py](backend/app/agents/baza.py) | Contractul comun al agentilor si bucla de tool use. |
| [compliance_kyc.py](backend/app/agents/compliance_kyc.py) | Rutabil, fara tool-uri (docs/AGENTS.md #3) — nu exista inca date/servicii KYC deterministe in spatele lui, deci raspunde onest ca nu poate ajuta, in loc sa simuleze o capabilitate. |
| [credit_advisor.py](backend/app/agents/credit_advisor.py) | Agentul de creditare — dosarul omului, nu brosura produsului. |
| [document.py](backend/app/agents/document.py) | Agent Cititor Doc/Bon — extrage date dintr-un bon sau o factura. |
| [document_intelligence.py](backend/app/agents/document_intelligence.py) | Agentul care trebuie sa citeze o sursa pentru orice afirmatie — de aceea e ruta implicita pentru intentii neclasificate (docs/AGENTS.md #4). |
| [engagement.py](backend/app/agents/engagement.py) | _(fără descriere proprie în fișier)_ |
| [financial_advisor.py](backend/app/agents/financial_advisor.py) | Adaptor peste financial advisor-ul lui Cristi (agents/financiar.py). |
| [financiar.py](backend/app/agents/financiar.py) | _(fără descriere proprie în fișier)_ |
| [orchestrator.py](backend/app/agents/orchestrator.py) | Orchestratorul din diagrama. |
| [rag.py](backend/app/agents/rag.py) | Agent RAG Q&A — raspunde despre produsele si regulile bancii. |
| [registru.py](backend/app/agents/registru.py) | Asambleaza agentii pentru un request. |
| [specs.py](backend/app/agents/specs.py) | Cei 5 agenti, declarati ca date (docs/AGENTS.md) — documentatie executabila. |
| [transaction_intelligence.py](backend/app/agents/transaction_intelligence.py) | _(fără descriere proprie în fișier)_ |

### AI — unelte (singura punte agent -> aplicatie)

| Fișier | Ce face |
|---|---|
| [banking_tools.py](backend/app/tools/banking_tools.py) | Tool-uri deterministe peste conturi/tranzactii reale — niciodata scriere. |
| [base.py](backend/app/tools/base.py) | Definitia unui tool (docs/AI_ARCHITECTURE.md #3, ARCHITECTURE.md #12) — singura punte agent -> aplicatie. |
| [card_tools.py](backend/app/tools/card_tools.py) | Tool determinist peste cardurile reale — niciodata numarul complet sau CVV-ul. |
| [categorii_tranzactii.py](backend/app/tools/categorii_tranzactii.py) | Categorisire determinista a tranzactiilor, dupa descriere/contraparte — aceeasi ratiune ca orchestration/intent.py: o tabela de cuvinte-cheie e gratuita, instanta, reproductibila si testabila unitar, ... |
| [credit_tools.py](backend/app/tools/credit_tools.py) | Tool-uri de creditare pentru asistent — citire si calcul determinist, niciodata scriere. |
| [eligibility.py](backend/app/tools/eligibility.py) | Eligibilitate decisa in afara modelului, reverificata la executie (docs/SECURITY.md #2). |
| [executor.py](backend/app/tools/executor.py) | Executie paralela cu timeout, barieta pentru mutatii (docs/AI_ARCHITECTURE.md #3). |
| [financiar_tools.py](backend/app/tools/financiar_tools.py) | Tool-urile agentului Financial Advisor. |
| [knowledge_tools.py](backend/app/tools/knowledge_tools.py) | _(fără descriere proprie în fișier)_ |
| [registry.py](backend/app/tools/registry.py) | _(fără descriere proprie în fișier)_ |
| [scenario_tools.py](backend/app/tools/scenario_tools.py) | Simulare what-if determinista — aritmetica in bani (integer), nu in virgula mobila. |
| [unealta.py](backend/app/tools/unealta.py) | Ce este un tool, independent de furnizorul de model. |

### AI — RAG (indexare si regasire peste galaxy-bank-knowledge)

| Fișier | Ce face |
|---|---|
| [chunking.py](backend/app/rag/chunking.py) | Strategii de chunking (docs/AI_ARCHITECTURE.md #7) — nu o singura fereastra pentru orice document. |
| [indexing.py](backend/app/rag/indexing.py) | Reindexare incrementala (docs/AI_ARCHITECTURE.md #7, PATTERN_ADOPTION.md). |
| [registry.py](backend/app/rag/registry.py) | Citeste galaxy-bank-knowledge/ — niciodata nu scrie in acest folder (interzis explicit de utilizator). |
| [retrieval.py](backend/app/rag/retrieval.py) | Regasire cu filtre aplicate inainte de similaritate (docs/AI_ARCHITECTURE.md #7). |

### AI — memorie si compresie de conversatie

| Fișier | Ce face |
|---|---|
| [compression.py](backend/app/memory/compression.py) | Compresie determinista, incrementala pe `summary_watermark` (docs/AI_ARCHITECTURE.md #6). |
| [extraction.py](backend/app/memory/extraction.py) | Extractie determinista de memorie inter-sesiuni (docs/AI_ARCHITECTURE.md #6). |

### Creditare — reguli, scorecard, amortizare, venit

| Fișier | Ce face |
|---|---|
| [adeverinta.py](backend/app/credit/adeverinta.py) | Citirea unei adeverinte de venit — text brut in cifre pe care le poate folosi banca. |
| [ai/contracte.py](backend/app/credit/ai/contracte.py) | Cele patru etape ale pipeline-ului AI de credite, declarate ca date — tiparul din `agents/specs.py`. |
| [ai/etape/brief.py](backend/app/credit/ai/etape/brief.py) | Etapa 'brief' — sinteza pentru analistul din zona gri. |
| [ai/etape/coerenta.py](backend/app/credit/ai/etape/coerenta.py) | Etapa 'coerenta' — coroboreaza sursele intre ele, fara niciun model. |
| [ai/etape/documente.py](backend/app/credit/ai/etape/documente.py) | Etapa 'documente' — citeste adeverinta cu un model, in paralel cu regex-ul. |
| [ai/etape/explicatie.py](backend/app/credit/ai/etape/explicatie.py) | Etapa 'explicatie' — rescrie textul determinist pentru client, mai cald. |
| [ai/pipeline.py](backend/app/credit/ai/pipeline.py) | CreditAiPipeline — compune etapele 1-3 (documente, coerenta, brief). |
| [ai/prompturi.py](backend/app/credit/ai/prompturi.py) | Prompturile pipeline-ului AI de credite, cu versiuni explicite. |
| [amortizare.py](backend/app/credit/amortizare.py) | Amortizarea cu anuitate constanta: rata, graficul, DAE, rambursarea anticipata. |
| [reguli.py](backend/app/credit/reguli.py) | Criteriile hard de eligibilitate — ce respinge o cerere fara discutie. |
| [scorecard.py](backend/app/credit/scorecard.py) | Punctajul de bonitate — nuanta de dupa criteriile hard. |
| [venit.py](backend/app/credit/venit.py) | Venitul dedus din incasarile reale ale utilizatorului. |

### ML — detectia platilor neregulate

| Fișier | Ce face |
|---|---|
| [antrenare.py](backend/app/ml/antrenare.py) | Antreneaza modelul de neregularitati si salveaza artefactul. |
| [caracteristici.py](backend/app/ml/caracteristici.py) | Transforma randurile brute in trasaturi. |
| [neregularitati.py](backend/app/ml/neregularitati.py) | Detectia platilor neregulate. |

### AI — construirea contextului

| Fișier | Ce face |
|---|---|
| [builder.py](backend/app/context/builder.py) | Un singur ContextBuilder pentru toti agentii (docs/AI_ARCHITECTURE.md #5). |

### Atasamente

| Fișier | Ce face |
|---|---|
| [extraction.py](backend/app/attachments/extraction.py) | Extragere de text din PDF — determinista, nu OCR/vision (CLAUDE.md #16). |
| [service.py](backend/app/attachments/service.py) | Fluxul de upload: valideaza, urca in Storage, extrage text (doar PDF), salveaza metadata. |

### Contracte de intrare/iesire (Pydantic)

| Fișier | Ce face |
|---|---|
| [admin.py](backend/app/schemas/admin.py) | _(fără descriere proprie în fișier)_ |
| [agents.py](backend/app/schemas/agents.py) | _(fără descriere proprie în fișier)_ |
| [analiza.py](backend/app/schemas/analiza.py) | _(fără descriere proprie în fișier)_ |
| [assistant.py](backend/app/schemas/assistant.py) | _(fără descriere proprie în fișier)_ |
| [common.py](backend/app/schemas/common.py) | _(fără descriere proprie în fișier)_ |
| [credit.py](backend/app/schemas/credit.py) | Contractele HTTP pentru creditare. |
| [credit_ai.py](backend/app/schemas/credit_ai.py) | Contractele HTTP pentru pipeline-ul AI de credite (zona de administrare). |
| [identity.py](backend/app/schemas/identity.py) | _(fără descriere proprie în fișier)_ |
| [profiles.py](backend/app/schemas/profiles.py) | _(fără descriere proprie în fișier)_ |

### Telemetrie

| Fișier | Ce face |
|---|---|
| [metrics.py](backend/app/telemetry/metrics.py) | Numarare de tokeni cu fallback si estimare de cost (docs/AI_ARCHITECTURE.md #10). |

### Rapoarte (PDF/CSV)

| Fișier | Ce face |
|---|---|
| [csv_raport.py](backend/app/rapoarte/csv_raport.py) | Raportul ca CSV — datele, pentru prelucrare mai departe. |
| [pdf_export_tranzactii.py](backend/app/rapoarte/pdf_export_tranzactii.py) | Extras de tranzactii, ca PDF, pentru exportul cerut de utilizator din chat-ul asistentului. |
| [pdf_raport.py](backend/app/rapoarte/pdf_raport.py) | Raportul ca PDF. |

### Scripturi de intretinere

| Fișier | Ce face |
|---|---|
| [reindex_knowledge.py](backend/app/scripts/reindex_knowledge.py) | Reindexeaza galaxy-bank-knowledge/ in knowledge_chunks — incremental, prin plan_reindex. |
| [seed_credit_demo.py](backend/app/scripts/seed_credit_demo.py) | Pregateste un utilizator existent ca sa poata fi testat fluxul de creditare. |
| [verifica_flux_credit.py](backend/app/scripts/verifica_flux_credit.py) | Ruleaza tot lantul de creditare pe baza reala si tipareste fiecare pas. |

### Frontend — rute si pagini (App Router)

| Fișier | Ce face |
|---|---|
| [(app)/asistent/page.tsx](frontend/src/app/%28app%29/asistent/page.tsx) | Ecranul asistentului: reasoning-ul sta in orchestratorul Python din spatele FastAPI (ARCHITECTURE.md 3.5 si 15) — pagina doar afiseaza conversatia si trimite mesaje catre backend. |
| [(app)/beneficiari/page.tsx](frontend/src/app/%28app%29/beneficiari/page.tsx) | _(fără descriere proprie în fișier)_ |
| [(app)/carduri/page.tsx](frontend/src/app/%28app%29/carduri/page.tsx) | _(fără descriere proprie în fișier)_ |
| [(app)/credite/[id]/page.tsx](frontend/src/app/%28app%29/credite/[id]/page.tsx) | _(fără descriere proprie în fișier)_ |
| [(app)/credite/cerere/page.tsx](frontend/src/app/%28app%29/credite/cerere/page.tsx) | _(fără descriere proprie în fișier)_ |
| [(app)/credite/page.tsx](frontend/src/app/%28app%29/credite/page.tsx) | _(fără descriere proprie în fișier)_ |
| [(app)/credite/simulare/page.tsx](frontend/src/app/%28app%29/credite/simulare/page.tsx) | _(fără descriere proprie în fișier)_ |
| [(app)/dashboard/page.tsx](frontend/src/app/%28app%29/dashboard/page.tsx) | Stilul unei dale din grila — impartit intre linkuri si declansatorul de drawer. |
| [(app)/grupuri/[id]/page.tsx](frontend/src/app/%28app%29/grupuri/[id]/page.tsx) | Un grup: soldul comun, membrii cu drepturile lor si conversatia. |
| [(app)/grupuri/page.tsx](frontend/src/app/%28app%29/grupuri/page.tsx) | Lista grupurilor din care faci parte. |
| [(app)/istoric/page.tsx](frontend/src/app/%28app%29/istoric/page.tsx) | _(fără descriere proprie în fișier)_ |
| [(app)/layout.tsx](frontend/src/app/%28app%29/layout.tsx) | Cadrul comun al ecranelor autentificate (dashboard, istoric, transfer, carduri, beneficiari, setari): verifica sesiunea o singura data, monteaza navigarea de jos si ascultatorul de realtime. |
| [(app)/setari/page.tsx](frontend/src/app/%28app%29/setari/page.tsx) | _(fără descriere proprie în fișier)_ |
| [(app)/transfer/page.tsx](frontend/src/app/%28app%29/transfer/page.tsx) | _(fără descriere proprie în fișier)_ |
| [(ecommerce)/layout.tsx](frontend/src/app/%28ecommerce%29/layout.tsx) | Cadrul magazinului (grup de rute separat de (app)): fara verificare de sesiune, fara bara de jos — e o vitrina publica, nu partea bancara. |
| [(ecommerce)/shop/[slug]/page.tsx](frontend/src/app/%28ecommerce%29/shop/[slug]/page.tsx) | _(fără descriere proprie în fișier)_ |
| [(ecommerce)/shop/page.tsx](frontend/src/app/%28ecommerce%29/shop/page.tsx) | _(fără descriere proprie în fișier)_ |
| [admin/conturi/page.tsx](frontend/src/app/admin/conturi/page.tsx) | _(fără descriere proprie în fișier)_ |
| [admin/credite/[id]/page.tsx](frontend/src/app/admin/credite/[id]/page.tsx) | Din ce s-a compus punctajul. |
| [admin/credite/acordate/page.tsx](frontend/src/app/admin/credite/acordate/page.tsx) | _(fără descriere proprie în fișier)_ |
| [admin/credite/ai/page.tsx](frontend/src/app/admin/credite/ai/page.tsx) | Randuri per (zi, etapa) — 'coerenta' ar trebui sa fie mereu 100% reusita, fiindca e determinista: orice esec acolo e un bug, nu un raspuns rau de la Foundry. |
| [admin/credite/page.tsx](frontend/src/app/admin/credite/page.tsx) | _(fără descriere proprie în fișier)_ |
| [admin/layout.tsx](frontend/src/app/admin/layout.tsx) | Cadrul zonei de administrare. |
| [admin/page.tsx](frontend/src/app/admin/page.tsx) | _(fără descriere proprie în fișier)_ |
| [admin/tranzactii/[id]/page.tsx](frontend/src/app/admin/tranzactii/[id]/page.tsx) | _(fără descriere proprie în fișier)_ |
| [admin/tranzactii/page.tsx](frontend/src/app/admin/tranzactii/page.tsx) | _(fără descriere proprie în fișier)_ |
| [admin/verificari/[id]/page.tsx](frontend/src/app/admin/verificari/[id]/page.tsx) | _(fără descriere proprie în fișier)_ |
| [api/backend/[...path]/route.ts](frontend/src/app/api/backend/[...path]/route.ts) | _(fără descriere proprie în fișier)_ |
| [api/health/route.ts](frontend/src/app/api/health/route.ts) | _(fără descriere proprie în fișier)_ |
| [api/payments/[id]/route.ts](frontend/src/app/api/payments/[id]/route.ts) | GET /api/payments/<id> — starea unei plati, pentru ecranul de checkout. |
| [api/payments/approve/route.ts](frontend/src/app/api/payments/approve/route.ts) | POST /api/payments/approve — utilizatorul confirma plata din aplicatie. |
| [api/payments/decline/route.ts](frontend/src/app/api/payments/decline/route.ts) | POST /api/payments/decline — utilizatorul respinge plata din aplicatie. |
| [api/payments/route.ts](frontend/src/app/api/payments/route.ts) | POST /api/payments — magazinul cere o plata cu datele unui card Libra. |
| [auth/callback/route.ts](frontend/src/app/auth/callback/route.ts) | Tinta linkurilor din emailurile Supabase (confirmare cont, resetare parola). |
| [layout.tsx](frontend/src/app/layout.tsx) | _(fără descriere proprie în fișier)_ |
| [login/page.tsx](frontend/src/app/login/page.tsx) | _(fără descriere proprie în fișier)_ |
| [page.tsx](frontend/src/app/page.tsx) | _(fără descriere proprie în fișier)_ |
| [register/page.tsx](frontend/src/app/register/page.tsx) | _(fără descriere proprie în fișier)_ |

### Frontend — componente

| Fișier | Ce face |
|---|---|
| [admin/blocare-cont.tsx](frontend/src/components/admin/blocare-cont.tsx) | Blocarea si deblocarea conturilor, dintr-un rand din lista de conturi. |
| [admin/cereri-inchidere.tsx](frontend/src/components/admin/cereri-inchidere.tsx) | Cererile de inchidere a unui CONT BANCAR, pentru analist. |
| [admin/cereri-stergere.tsx](frontend/src/components/admin/cereri-stergere.tsx) | Cererile de inchidere a contului, pentru analist. |
| [admin/decizia-cazului.tsx](frontend/src/components/admin/decizia-cazului.tsx) | Aproba sau respinge. |
| [admin/decizia-cererii.tsx](frontend/src/components/admin/decizia-cererii.tsx) | Ce face analistul cu un dosar aflat in lucru. |
| [admin/decizia-contului.tsx](frontend/src/components/admin/decizia-contului.tsx) | Ce poate face un administrator cu un cont semnalat. |
| [admin/document-adeverinta.tsx](frontend/src/components/admin/document-adeverinta.tsx) | Adeverinta, langa cifra citita din ea. |
| [admin/etichete-caz.tsx](frontend/src/components/admin/etichete-caz.tsx) | Cele doua dovezi, rezumate: potrivirea fetelor si CNP-ul. |
| [admin/fir-dosar.tsx](frontend/src/components/admin/fir-dosar.tsx) | Firul dosarului, pe partea analistului. |
| [admin/forteaza-verificare.tsx](frontend/src/components/admin/forteaza-verificare.tsx) | Marcheaza manual un cont ca verificat, fara nicio dovada (OCR/selfie). |
| [admin/jurnal-cerere.tsx](frontend/src/components/admin/jurnal-cerere.tsx) | Jurnalul dosarului — cine l-a atins, ce a facut, si cand. |
| [admin/lista-cereri-credit.tsx](frontend/src/components/admin/lista-cereri-credit.tsx) | Filtrele care conteaza pentru un analist, in ordinea in care le-ar folosi: intai ce are de lucru, apoi ce a iesit din mana lui, apoi restul. |
| [admin/lista-conturi-semnalate.tsx](frontend/src/components/admin/lista-conturi-semnalate.tsx) | Culorile pornesc de la gravitatea din tipuri-admin, ca sa nu existe doua praguri. |
| [admin/nav-admin.tsx](frontend/src/components/admin/nav-admin.tsx) | _(fără descriere proprie în fișier)_ |
| [admin/pipeline-ai.tsx](frontend/src/components/admin/pipeline-ai.tsx) | Panoul consultativ din dosarul cererii — semnalele de coerenta, ce a citit modelul din document, si un brief pentru zona gri. |
| [admin/poprire-cont.tsx](frontend/src/components/admin/poprire-cont.tsx) | Instituirea unei popriri, dintr-un rand din lista de conturi. |
| [admin/popriri.tsx](frontend/src/components/admin/popriri.tsx) | Popririle instituite, cu ce se poate face cu ele. |
| [admin/poze-caz.tsx](frontend/src/components/admin/poze-caz.tsx) | Buletinul si selfie-ul, unul langa altul. |
| [admin/raport-cont.tsx](frontend/src/components/admin/raport-cont.tsx) | Culoarea porneste de la gravitatea din tipuri-admin: un singur set de praguri. |
| [admin/restabileste-biometrie.tsx](frontend/src/components/admin/restabileste-biometrie.tsx) | Restabileste referinta biometrica a unui cont, cu o poza noua — pentru cazul in care pozele din storage au disparut (sterse din greseala) si login-ul biometric a ramas fara nimic de comparat. |
| [asistent/bula-mesaj.tsx](frontend/src/components/asistent/bula-mesaj.tsx) | Caile interne din raspuns devin linkuri pe care se poate apasa. |
| [asistent/fereastra-chat.tsx](frontend/src/components/asistent/fereastra-chat.tsx) | _(fără descriere proprie în fișier)_ |
| [asistent/lista-conversatii-drawer.tsx](frontend/src/components/asistent/lista-conversatii-drawer.tsx) | Istoricul conversatiilor — un istoric nu are nevoie de URL propriu, doar drawer (DESIGN.md 8.1). |
| [auth/auth-shell.tsx](frontend/src/components/auth/auth-shell.tsx) | Titlul mic din bara hero. |
| [auth/buletin-capture.tsx](frontend/src/components/auth/buletin-capture.tsx) | Vezi selfie-capture.tsx: blocarea e moale, ca sa nu ramana nimeni infundat. |
| [auth/face-login-capture.tsx](frontend/src/components/auth/face-login-capture.tsx) | Doar camera pentru login biometric (fara upload din galerie, ca la selfie-ul de la inregistrare) — o poza statica ar submina scopul. |
| [auth/info-drawere.tsx](frontend/src/components/auth/info-drawere.tsx) | Explicatiile si textele legale stau in drawere, nu in pagini separate (DESIGN.md 8.1) — utilizatorul nu isi pierde datele completate. |
| [auth/login-form.tsx](frontend/src/components/auth/login-form.tsx) | _(fără descriere proprie în fișier)_ |
| [auth/register-form.tsx](frontend/src/components/auth/register-form.tsx) | _(fără descriere proprie în fișier)_ |
| [auth/resetare-parola-drawer.tsx](frontend/src/components/auth/resetare-parola-drawer.tsx) | Resetarea parolei nu merita o pagina proprie (DESIGN.md 8.1) — un singur camp si un buton, deci sta intr-un drawer peste ecranul de login. |
| [auth/selfie-capture.tsx](frontend/src/components/auth/selfie-capture.tsx) | De la a cata incercare esuata ii oferim si scaparea "Continua oricum". |
| [beneficiari/lista-beneficiari.tsx](frontend/src/components/beneficiari/lista-beneficiari.tsx) | _(fără descriere proprie în fișier)_ |
| [carduri/adauga-card-drawer.tsx](frontend/src/components/carduri/adauga-card-drawer.tsx) | Un card nou: contul din care plateste, tipul si tematica. |
| [carduri/lista-carduri.tsx](frontend/src/components/carduri/lista-carduri.tsx) | _(fără descriere proprie în fișier)_ |
| [credite/cerere-wizard.tsx](frontend/src/components/credite/cerere-wizard.tsx) | Cererea de credit, în patru pași. |
| [credite/cereri-in-curs.tsx](frontend/src/components/credite/cereri-in-curs.tsx) | Cererile care nu s-au terminat încă: ofertele de semnat și dosarele în analiză. |
| [credite/conversatie-cerere.tsx](frontend/src/components/credite/conversatie-cerere.tsx) | Firul de discutie de pe un dosar de credit. |
| [credite/detaliu-credit.tsx](frontend/src/components/credite/detaliu-credit.tsx) | Detaliul unui credit: cât mai e de plătit, când, și cum se poate stinge mai devreme. |
| [credite/discutie-drawer.tsx](frontend/src/components/credite/discutie-drawer.tsx) | Firul, ca popup — nu inline in cardul cererii. |
| [credite/incarca-adeverinta.tsx](frontend/src/components/credite/incarca-adeverinta.tsx) | Încărcarea adeverinței de venit, în pasul de decizie. |
| [credite/simulator.tsx](frontend/src/components/credite/simulator.tsx) | Calculatorul de rată. |
| [dashboard/avatar-utilizator.tsx](frontend/src/components/dashboard/avatar-utilizator.tsx) | Poza de profil din header-ul dashboardului. |
| [dashboard/banda-poprire.tsx](frontend/src/components/dashboard/banda-poprire.tsx) | „O parte din bani sunt indisponibili, si de ce." Sta deasupra listei de conturi, nu pe fiecare rand: poprirea e pe OM, nu pe cont (0047), si repetata pe patru conturi ar sugera patru popriri. |
| [dashboard/deschide-cont-drawer.tsx](frontend/src/components/dashboard/deschide-cont-drawer.tsx) | Sugestii uzuale, ca sa nu ramana campul gol la prima deschidere. |
| [dashboard/lista-conturi.tsx](frontend/src/components/dashboard/lista-conturi.tsx) | Conturile bancare ale utilizatorului, cu soldul fiecaruia. |
| [dashboard/meniu-cont.tsx](frontend/src/components/dashboard/meniu-cont.tsx) | Meniul unui cont bancar — trei puncte pe cardul lui. |
| [dashboard/mesaje-banca.tsx](frontend/src/components/dashboard/mesaje-banca.tsx) | Mesajele bancii catre client, pe dashboard. |
| [dashboard/schimb-valutar-drawer.tsx](frontend/src/components/dashboard/schimb-valutar-drawer.tsx) | Schimbul valutar: alegi contul, apoi suma si valuta in care o vrei. |
| [dashboard/sold-animat.tsx](frontend/src/components/dashboard/sold-animat.tsx) | easeOutCubic — porneste repede si se aseaza lin pe suma finala. |
| [dashboard/ultimele-tranzactii.tsx](frontend/src/components/dashboard/ultimele-tranzactii.tsx) | Rezumatul de pe dashboard: ultimele cateva miscari, cu poza celuilalt participant. |
| [dashboard/verifica-identitate-banner.tsx](frontend/src/components/dashboard/verifica-identitate-banner.tsx) | Contul exista deja fara buletin (userul a ales sa-l trimita mai tarziu la inregistrare, vezi register-form.tsx). |
| [grupuri/conversatie-grup.tsx](frontend/src/components/grupuri/conversatie-grup.tsx) | Conversatia din grup: mesajele existente si campul de scris. |
| [grupuri/creeaza-grup-drawer.tsx](frontend/src/components/grupuri/creeaza-grup-drawer.tsx) | Sugestii uzuale, ca sa nu ramana campul gol la prima deschidere. |
| [grupuri/depune-in-grup-drawer.tsx](frontend/src/components/grupuri/depune-in-grup-drawer.tsx) | Punerea de bani in soldul comun al grupului: din ce cont si cat. |
| [grupuri/drepturi-membru-drawer.tsx](frontend/src/components/grupuri/drepturi-membru-drawer.tsx) | Drepturile unui membru asupra soldului comun, asa cum le vede creatorul: daca poate scoate bani si care ii e plafonul lunar. |
| [grupuri/iesi-din-grup-drawer.tsx](frontend/src/components/grupuri/iesi-din-grup-drawer.tsx) | Iesirea din grup, cu confirmare. |
| [grupuri/intra-in-grup-drawer.tsx](frontend/src/components/grupuri/intra-in-grup-drawer.tsx) | Intrarea intr-un grup cu cod de acces. |
| [grupuri/lista-grupuri.tsx](frontend/src/components/grupuri/lista-grupuri.tsx) | Grupurile utilizatorului, cu soldul comun si numarul de membri. |
| [grupuri/partajeaza-grup-drawer.tsx](frontend/src/components/grupuri/partajeaza-grup-drawer.tsx) | Invitatia intr-un grup: codul de acces si linkul care il contine. |
| [grupuri/vizibilitate-tranzactii.tsx](frontend/src/components/grupuri/vizibilitate-tranzactii.tsx) | Comutatorul creatorului pentru vizibilitatea miscarilor de bani in conversatia grupului. |
| [istoric/filtre-drawer.tsx](frontend/src/components/istoric/filtre-drawer.tsx) | _(fără descriere proprie în fișier)_ |
| [istoric/lista-tranzactii.tsx](frontend/src/components/istoric/lista-tranzactii.tsx) | _(fără descriere proprie în fișier)_ |
| [plati/confirma-plata-drawer.tsx](frontend/src/components/plati/confirma-plata-drawer.tsx) | 92 -> "1:32" |
| [realtime/ascultator-realtime.tsx](frontend/src/components/realtime/ascultator-realtime.tsx) | Tine ecranele autentificate la zi: asculta canalul privat, cere re-randarea Server Components si, cand intra bani, scoate notificarea si porneste ploaia de confetti. |
| [realtime/ploaie-confetti.tsx](frontend/src/components/realtime/ploaie-confetti.tsx) | Cate bucati cad. |
| [realtime/toast-incasare.tsx](frontend/src/components/realtime/toast-incasare.tsx) | Notificarea de incasare. |
| [setari/editeaza-telefon-drawer.tsx](frontend/src/components/setari/editeaza-telefon-drawer.tsx) | _(fără descriere proprie în fișier)_ |
| [setari/inchide-contul.tsx](frontend/src/components/setari/inchide-contul.tsx) | Inchiderea relatiei cu banca — in Setari, nu pe dashboard. |
| [setari/securitate-drawer.tsx](frontend/src/components/setari/securitate-drawer.tsx) | Tot ce tine de securitatea contului, intr-un singur drawer deschis din randul "Securitate": pornirea/oprirea login-ului biometric, schimbarea parolei si dispozitivele conectate. |
| [setari/setari-client.tsx](frontend/src/components/setari/setari-client.tsx) | URL public din Supabase Storage (lib/actions/profil.ts), null fara poza. |
| [shell/bottom-nav.tsx](frontend/src/components/shell/bottom-nav.tsx) | Navigatia principala a ecranelor autentificate. |
| [shell/fundal-spatial.tsx](frontend/src/components/shell/fundal-spatial.tsx) | Cerul instelat din spatele aplicatiei — in ambele teme (vezi .fundal-spatial in globals.css). |
| [shop/cumpara-drawer.tsx](frontend/src/components/shop/cumpara-drawer.tsx) | 4111111111111111 -> "4111 1111 1111 1111", maxim 16 cifre. |
| [shop/produs-card.tsx](frontend/src/components/shop/produs-card.tsx) | _(fără descriere proprie în fișier)_ |
| [shop/produs-vizual.tsx](frontend/src/components/shop/produs-vizual.tsx) | Latimea reala a vizualului in layout, ca Next sa serveasca poza potrivita. |
| [shop/shop-header.tsx](frontend/src/components/shop/shop-header.tsx) | Antetul magazinului — separat de barul de navigare al aplicatiei bancare. |
| [transfer/alege-beneficiar-drawer.tsx](frontend/src/components/transfer/alege-beneficiar-drawer.tsx) | Beneficiarul se confirma pe server: IBAN-ul trebuie sa fie al unui cont Libra real. |
| [transfer/alege-cont-drawer.tsx](frontend/src/components/transfer/alege-cont-drawer.tsx) | Un rand din lista de surse — cont propriu sau sold de grup. |
| [transfer/confirma-transfer-drawer.tsx](frontend/src/components/transfer/confirma-transfer-drawer.tsx) | _(fără descriere proprie în fișier)_ |
| [transfer/transfer-form.tsx](frontend/src/components/transfer/transfer-form.tsx) | Cont preselectat (ex. |
| [ui/avatar-profil.tsx](frontend/src/components/ui/avatar-profil.tsx) | Poza unei persoane — utilizatorul curent in header sau contrapartea unei tranzactii. |
| [ui/banda.tsx](frontend/src/components/ui/banda.tsx) | Banda de mesaj la nivel de formular (DESIGN.md 7 si 9). |
| [ui/bulina.tsx](frontend/src/components/ui/bulina.tsx) | Semnalul „ai ceva necitit", intr-un singur loc. |
| [ui/button.tsx](frontend/src/components/ui/button.tsx) | _(fără descriere proprie în fișier)_ |
| [ui/camp.tsx](frontend/src/components/ui/camp.tsx) | Adauga butonul de afisare/ascundere a parolei. |
| [ui/checkbox.tsx](frontend/src/components/ui/checkbox.tsx) | _(fără descriere proprie în fișier)_ |
| [ui/clopotel-notificari.tsx](frontend/src/components/ui/clopotel-notificari.tsx) | Clopotelul cu notificarile utilizatorului. |
| [ui/comutator.tsx](frontend/src/components/ui/comutator.tsx) | Comutator pornit/oprit (DESIGN.md 7). |
| [ui/drawer.tsx](frontend/src/components/ui/drawer.tsx) | Wrapper peste vaul, stilizat conform DESIGN.md (sectiunea 8). |
| [ui/logo.tsx](frontend/src/components/ui/logo.tsx) | Sigla Galaxy Bank. |
| [ui/notificari.tsx](frontend/src/components/ui/notificari.tsx) | Zona de notificari. |

### Frontend — server actions (mutatii)

| Fișier | Ce face |
|---|---|
| [admin-analiza.ts](frontend/src/lib/actions/admin-analiza.ts) | Consemneaza hotararea administratorului asupra unui cont semnalat. |
| [admin-credite.ts](frontend/src/lib/actions/admin-credite.ts) | Verificarea de rol se face si aici, nu doar pe ecranul din care se apeleaza: o actiune de server e un endpoint ca oricare altul, care poate fi chemat direct. |
| [admin-inchideri.ts](frontend/src/lib/actions/admin-inchideri.ts) | Deciziile analistului pe cererile de inchidere a unui cont bancar. |
| [admin-popriri.ts](frontend/src/lib/actions/admin-popriri.ts) | Popririle, dinspre analist. |
| [admin-stergeri.ts](frontend/src/lib/actions/admin-stergeri.ts) | Deciziile analistului pe cererile de inchidere a contului. |
| [admin-verificari.ts](frontend/src/lib/actions/admin-verificari.ts) | Aproba sau respinge un caz de verificare. |
| [asistent.ts](frontend/src/lib/actions/asistent.ts) | Sterge o conversatie (si mesajele/atasamentele ei, prin cascade in baza de date). |
| [auth.ts](frontend/src/lib/actions/auth.ts) | Mesaj de succes afisat in loc de redirect (ex. |
| [carduri.ts](frontend/src/lib/actions/carduri.ts) | Un numar de card de 16 cifre, valid Luhn. |
| [conturi.ts](frontend/src/lib/actions/conturi.ts) | Cate conturi poate avea un om — destul pentru orice folosire reala. |
| [credite.ts](frontend/src/lib/actions/credite.ts) | Mutatiile de creditare. |
| [dispozitive.ts](frontend/src/lib/actions/dispozitive.ts) | Singura actiune din zona de dispozitive apelabila din browser. |
| [grupuri.ts](frontend/src/lib/actions/grupuri.ts) | Mesajele pentru utilizator, dupa codul ridicat de functiile din 0008_grupuri.sql: codul ajunge in `message`, textul lung in `details`. Tot aici, drepturile membrilor si vizibilitatea tranzactiilor (0053). |
| [identitate.ts](frontend/src/lib/actions/identitate.ts) | Verificarea identitatii (OCR buletin + comparare fete cu DeepFace) traieste intr-un serviciu FastAPI separat — vezi ARCHITECTURE.md §3.4 si backend/. |
| [inchidere-cont.ts](frontend/src/lib/actions/inchidere-cont.ts) | Cererea clientului de a-si inchide un CONT BANCAR (nu relatia cu banca). |
| [notificari.ts](frontend/src/lib/actions/notificari.ts) | Marcheaza o notificare drept citita. |
| [profil.ts](frontend/src/lib/actions/profil.ts) | Poza de profil. |
| [schimb-valutar.ts](frontend/src/lib/actions/schimb-valutar.ts) | Codurile ridicate de public.schimba_valuta_cont/schimba_valuta_suma (0013, 0019_schimb_valutar_suma.sql). |
| [stergere-cont.ts](frontend/src/lib/actions/stergere-cont.ts) | Cererea de inchidere a contului. |
| [transfer.ts](frontend/src/lib/actions/transfer.ts) | Rotunjeste la banut, ca sa nu ramana resturi din aritmetica in virgula mobila. |

### Frontend — citiri

| Fișier | Ce face |
|---|---|
| [admin-credite.ts](frontend/src/lib/data/admin-credite.ts) | Cererile care asteapta decizia unui om. |
| [admin-inchideri.ts](frontend/src/lib/data/admin-inchideri.ts) | Aducerea cererilor de inchidere a unui cont bancar. |
| [admin-popriri.ts](frontend/src/lib/data/admin-popriri.ts) | Popririle, pentru panoul analistului. |
| [admin-stergeri.ts](frontend/src/lib/data/admin-stergeri.ts) | Aducerea cererilor de inchidere a relatiei cu banca. |
| [admin-tranzactii.ts](frontend/src/lib/data/admin-tranzactii.ts) | _(fără descriere proprie în fișier)_ |
| [admin-verificari.ts](frontend/src/lib/data/admin-verificari.ts) | _(fără descriere proprie în fișier)_ |
| [asistent.ts](frontend/src/lib/data/asistent.ts) | Afisat in loc de sursa exacta — vezi agents/base.py:confidence_from_tool_results. |
| [backend.ts](frontend/src/lib/data/backend.ts) | Apelul catre FastAPI, cu tokenul Supabase al utilizatorului curent. |
| [carduri.ts](frontend/src/lib/data/carduri.ts) | Oprit de banca. |
| [conturi.ts](frontend/src/lib/data/conturi.ts) | Ultimele 4 cifre, pentru liste: „•••• 4821". |
| [credite.ts](frontend/src/lib/data/credite.ts) | Citirile de creditare. |
| [curs-valutar.ts](frontend/src/lib/data/curs-valutar.ts) | Aducerea cursurilor valutare si scrierea lor in public.curs_valutar (0013_schimb_valutar.sql). |
| [dispozitive.ts](frontend/src/lib/data/dispozitive.ts) | Evidenta dispozitivelor de pe care s-a intrat in cont. |
| [grupuri.ts](frontend/src/lib/data/grupuri.ts) | Grupul, membrii lui si drepturile fiecaruia asupra soldului comun. |
| [notificari.ts](frontend/src/lib/data/notificari.ts) | Mesajele bancii pentru clientul curent. |
| [plati.ts](frontend/src/lib/data/plati.ts) | Platile proprii care inca asteapta un raspuns, cea mai veche prima. |
| [popriri.ts](frontend/src/lib/data/popriri.ts) | Poprirea, asa cum o vede clientul. |
| [produse.ts](frontend/src/lib/data/produse.ts) | Poza produsului din /public/produse. |
| [transfer.ts](frontend/src/lib/data/transfer.ts) | Datele ecranului de transfer. |
| [tranzactii.ts](frontend/src/lib/data/tranzactii.ts) | Celalalt participant: destinatarul la „trimisa", expeditorul la „primita". |

### Frontend — servicii

| Fișier | Ce face |
|---|---|
| [plati.ts](frontend/src/lib/services/plati.ts) | Logica platilor de card confirmate din aplicatie. |

### Frontend — clienti Supabase

| Fișier | Ce face |
|---|---|
| [client.ts](frontend/src/lib/supabase/client.ts) | Client Supabase pentru componente client. |
| [configurat.ts](frontend/src/lib/supabase/configurat.ts) | _(fără descriere proprie în fișier)_ |
| [middleware.ts](frontend/src/lib/supabase/middleware.ts) | Rute pe care middleware-ul nu le redirectioneaza catre /login. |
| [realtime.ts](frontend/src/lib/supabase/realtime.ts) | Aboneaza un canal Realtime cu JWT-ul sesiunii si il tine autentificat cand token-ul se reimprospateaza. |
| [server.ts](frontend/src/lib/supabase/server.ts) | Client Supabase pentru Server Components, Route Handlers si Server Actions. |

### Frontend — utilitare comune

| Fișier | Ce face |
|---|---|
| [admin.ts](frontend/src/lib/admin.ts) | Valoarea din `public.user_roles.role` care da drepturi de administrator. |
| [api.ts](frontend/src/lib/api.ts) | _(fără descriere proprie în fișier)_ |
| [backend.ts](frontend/src/lib/backend.ts) | Cheama FastAPI direct, din componente si actiuni de server. |
| [calitate-poza.ts](frontend/src/lib/calitate-poza.ts) | Indiciu de lumina calculat direct pe fluxul camerei, inainte de captura. |
| [camera.ts](frontend/src/lib/camera.ts) | Oglindeste previzualizarea si poza finala (potrivit pentru selfie-uri). |
| [cont-blocat.ts](frontend/src/lib/cont-blocat.ts) | Daca administratorul a blocat vreun cont al acestui om. |
| [dispozitive.test.ts](frontend/src/lib/dispozitive.test.ts) | Ruleaza cu runnerul din Node, fara nicio dependenta noua: docker compose exec frontend node --test --experimental-strip-types \ src/lib/dispozitive.test.ts Ce se testeaza e ORDINEA regulilor din dispo... |
| [dispozitive.ts](frontend/src/lib/dispozitive.ts) | Traduce un User-Agent in ceva ce poate citi un om: "Chrome pe Windows". |
| [env.ts](frontend/src/lib/env.ts) | Adevarat doar daca exista credentiale Supabase reale in mediu. |
| [iban.ts](frontend/src/lib/iban.ts) | Generare de IBAN romanesc (ISO 13616) pentru contul curent deschis la inregistrare. |
| [imagine.ts](frontend/src/lib/imagine.ts) | Latura avatarului salvat — mai mult nu se vede pe niciun ecran. |
| [mock-data.ts](frontend/src/lib/mock-data.ts) | Date simulate — nu exista inca tabele Supabase pentru conturi (IBAN) si beneficiari externi (doar `profiles`, `carduri`, `tranzactii`; vezi lib/data/carduri.ts si lib/data/tranzactii.ts pentru datele ... |
| [momente.ts](frontend/src/lib/momente.ts) | Formatarea momentelor, la fel pe server si in browser. |
| [notificari-credit.ts](frontend/src/lib/notificari-credit.ts) | Legatura dintre o notificare si dosarul de credit despre care vorbeste. |
| [plati.ts](frontend/src/lib/plati.ts) | Vocabularul comun al platilor: stari, forma randului si maparea catre interfata. |
| [stari-cerere.ts](frontend/src/lib/stari-cerere.ts) | Starile unei cereri decise de banca, si cum arata ele pe ecran. |
| [stil-card.ts](frontend/src/lib/stil-card.ts) | Gradientul vizual pentru fiecare tematica de card. |
| [tema.ts](frontend/src/lib/tema.ts) | Normalizeaza valoarea bruta a cookie-ului la o tema valida. |
| [tipuri-admin.ts](frontend/src/lib/tipuri-admin.ts) | Formele de date ale zonei de administrare, si etichetele lor. |
| [utils.ts](frontend/src/lib/utils.ts) | Compune clase Tailwind, ultima castiga in caz de conflict. |
| [validare.ts](frontend/src/lib/validare.ts) | Validari pentru formularele de autentificare. |
| [valute.ts](frontend/src/lib/valute.ts) | Valutele si conversia — fara nicio dependinta de server. |

### Frontend — hooks

| Fișier | Ce face |
|---|---|
| [use-canal-utilizator.ts](frontend/src/hooks/use-canal-utilizator.ts) | Un transfer produce doua mesaje in aceeasi milisecunda (soldul si tranzactia). |
| [use-plati-in-asteptare.ts](frontend/src/hooks/use-plati-in-asteptare.ts) | Coada de plati proprii care asteapta un raspuns. |
| [use-stare-plata.ts](frontend/src/hooks/use-stare-plata.ts) | Urmareste o SINGURA plata, dupa id, pe ecranul de checkout al magazinului. |

### Baza de date — migratii

| Fișier | Ce face |
|---|---|
| [0000_instantaneu_inainte_de_credite.sql](supabase/migrations/0000_instantaneu_inainte_de_credite.sql) | Libra — INSTANTANEU al bazei de date inainte de migrarea 0009 (creditare) Generat automat din catalogul Postgres pe 2026-08-20, direct din proiectul Supabase lldcoqbkonbnqhbqrbjr. |
| [0001_profiles.sql](supabase/migrations/0001_profiles.sql) | Libra — profiluri de utilizator create automat la inregistrare La INSERT in auth.users, un trigger copiaza datele din raw_user_meta_data (nume, cnp, telefon, iban_cont) impreuna cu email-ul din auth.u... |
| [0002_carduri_tranzactii.sql](supabase/migrations/0002_carduri_tranzactii.sql) | Libra — carduri si tranzactii Fiecare profil poate avea unul sau mai multe carduri. |
| [0003_card_style.sql](supabase/migrations/0003_card_style.sql) | Libra — tematica cardului (card_style) Adauga coloana card_style pe public.carduri (peste schema din 0002_carduri_tranzactii.sql). |
| [0004_ai_asistent.sql](supabase/migrations/0004_ai_asistent.sql) | Libra — asistent AI: conversatii, memorie, RAG, telemetrie Aditiva: nu atinge profiles/conturi_bancare/tranzactii/groups. |
| [0005_ai_asistent_atasamente_voce.sql](supabase/migrations/0005_ai_asistent_atasamente_voce.sql) | Libra — atasamente (PDF/poze) si canal vocal pentru asistent Aditiva la 0004_ai_asistent.sql. |
| [0006_ai_asistent_nivel_incredere.sql](supabase/migrations/0006_ai_asistent_nivel_incredere.sql) | Libra — nivel de incredere pe mesajele asistentului Aditiva la 0004/0005. |
| [0007_identity_verification.sql](supabase/migrations/0007_identity_verification.sql) | Libra — verificare identitate la inregistrare (buletin OCR + selfie DeepFace) Inlocuieste introducerea manuala a CNP-ului: userul incarca o poza a buletinului (CNP-ul se citeste automat prin OCR in se... |
| [0009_credite.sql](supabase/migrations/0009_credite.sql) | Libra — creditarea (Galaxy Flex Personal) Pana acum banca putea vorbi despre credite (corpusul din galaxy-bank-knowledge e indexat si asistentul il citeaza), dar nu putea da unul. |
| [0010_credite_operatiuni.sql](supabase/migrations/0010_credite_operatiuni.sql) | Libra — operatiunile pe credit: acordare, incasare de rate, rambursare Trei functii, toate dupa tiparul lui public.core_banking: SECURITY DEFINER, search_path gol, coduri de eroare in `raise exception... |
| [0011_admin_verificare_manuala.sql](supabase/migrations/0011_admin_verificare_manuala.sql) | Libra — verificarea manuala (fara dovezi) si urma completa de admin Doua lucruri, aditive: 1. |
| [0012_verificare_amanata.sql](supabase/migrations/0012_verificare_amanata.sql) | Libra — buletinul devine optional la inregistrare Selfie-ul ramane obligatoriu (e refolosit la login biometric si e reperul fata de care se compara buletinul, oricand ar fi trimis). |
| [0013_admin_restabilire_biometrie.sql](supabase/migrations/0013_admin_restabilire_biometrie.sql) | Libra — restabilirea manuala a referintei biometrice Cand pozele din storage dispar (sterse manual, din greseala sau nu), userii raman fara nimic de comparat la login biometric. |
| [0014_admin_rls_verificari_identitate.sql](supabase/migrations/0014_admin_rls_verificari_identitate.sql) | Libra — RLS pentru revizuirea de admin a verificarilor de identitate Backend-ul foloseste service-role la /api/identity/admin/* (ocoleste RLS), iar bariera reala e cere_administrator() din Python. |
| [0014_payments.sql](supabase/migrations/0014_payments.sql) | Libra — plati de card confirmate din aplicatie (demo) Fluxul: magazinul (/shop) cere o plata cu datele unui card Libra, plata se naste in PENDING_APPROVAL, iar utilizatorul o confirma sau o respinge d... |
| [0015_credit_documente_ocr.sql](supabase/migrations/0015_credit_documente_ocr.sql) | Libra — adeverinta de venit: ce s-a citit din ea, cine a confirmat, cat sta 0009 a pregatit terenul (tabela credit_documente, bucket-ul credit-documente, sursa 'adeverinta' in credit_verificari_venit)... |
| [0016_credit_cereri_finalizat_la.sql](supabase/migrations/0016_credit_cereri_finalizat_la.sql) | Libra — `finalizat_la` se completeaza singur 0015 a adaugat coloana, dar cine o scrie? |
| [0017_asistent_export_tranzactii.sql](supabase/migrations/0017_asistent_export_tranzactii.sql) | Libra — export PDF de tranzactii, generat de aplicatie (nu incarcat de user) Aditiva la 0005_ai_asistent_atasamente_voce.sql. |
| [0018_asistent_actiune_rapida.sql](supabase/migrations/0018_asistent_actiune_rapida.sql) | Libra — actiune rapida atasata unui raspuns determinist al asistentului Aditiva la 0004_ai_asistent.sql. |
| [0018_rol_admin_unificat.sql](supabase/migrations/0018_rol_admin_unificat.sql) | 0018 — o singura sursa de adevar pentru "cine e administrator" Pana acum aceeasi intrebare primea trei raspunsuri diferite: frontend/src/lib/admin.ts user_roles.role = 'admin' |
| [0019_schimb_valutar_suma.sql](supabase/migrations/0019_schimb_valutar_suma.sql) | Libra — schimb valutar cu suma partiala, intr-un cont separat per valuta Aditiva la schema din 0000_instantaneu_inainte_de_credite.sql (public.schimba_valuta_cont, public.converteste, public.genereaza... |
| [0019_securitate_cont.sql](supabase/migrations/0019_securitate_cont.sql) | 0019 — sectiunea de securitate din setari Doua lucruri care nu existau deloc: un comutator prin care omul isi poate opri login-ul biometric, si evidenta dispozitivelor de pe care s-a intrat in |
| [0020_analize_si_notificari.sql](supabase/migrations/0020_analize_si_notificari.sql) | 0020 — Analiza administratorului asupra unui cont, si notificarile clientului STRICT ADITIVA. |
| [0021_credit_ai_pipeline.sql](supabase/migrations/0021_credit_ai_pipeline.sql) | Libra — pipeline AI de creditare: observatii consultative peste dosarul deja decis determinist de credit_service.py + scorecard.py. |
| [0022_credit_mesaj_analist.sql](supabase/migrations/0022_credit_mesaj_analist.sql) | Libra — canalul dintre analist si client, plus starea "asteapta documente" Pana acum analistul avea doua iesiri dintr-un dosar din zona gri: aproba sau respinge. |
| [0023_credit_mesaje.sql](supabase/migrations/0023_credit_mesaje.sql) | Libra — firul de discutie pe dosarul de credit 0019 a pus mesajul analistului intr-o coloana pe cerere. |
| [0024_credit_mesaje_citit.sql](supabase/migrations/0024_credit_mesaje_citit.sql) | Libra — marcaj de citit pe firul dosarului de credit Bulina "ai mesaje noi" are nevoie de o sursa proprie. |
| [0025_credit_mesaje_citit_analist.sql](supabase/migrations/0025_credit_mesaje_citit_analist.sql) | Simetricul lui `citit_de_client_la` din 0024, pentru cealalta parte a firului. |
| [0026_credit_mesaje_realtime.sql](supabase/migrations/0026_credit_mesaje_realtime.sql) | Mesajul analistului ajunge la client fara reincarcare de pagina. |
| [0027_card_cont.sql](supabase/migrations/0027_card_cont.sql) | 0027 — Pasul A: cardul primeste un cont Pana acum un card apartinea direct unui utilizator, iar contul din care se luau banii se alegea la FIECARE plata, printr-o euristica din `creeaza_plata`: |
| [0028_card_cont_completare.sql](supabase/migrations/0028_card_cont_completare.sql) | 0028 — Pasul B: completarea contului pentru cardurile existente Se ruleaza DUPA 0027 si SE CITESTE INAINTE DE A FI RULAT. |
| [0029_card_cont_obligatoriu.sql](supabase/migrations/0029_card_cont_obligatoriu.sql) | 0029 — Pasul C: contul devine obligatoriu, iar plata il foloseste Se ruleaza DUPA ce 0028 a raportat `carduri_fara_cont = 0`. |
| [0030_blocare_cont.sql](supabase/migrations/0030_blocare_cont.sql) | 0030 — Blocarea administrativa, la nivel de cont si etansa in baza Doua probleme se rezolva aici. |
| [0031_card_tip_limite.sql](supabase/migrations/0031_card_tip_limite.sql) | 0031 — Carduri virtuale si limita zilnica Amandoua devin posibile abia dupa 0029: un card are acum un cont propriu, deci si o valuta proprie si un sold propriu. |
| [0032_card_blocat_de_banca.sql](supabase/migrations/0032_card_blocat_de_banca.sql) | 0032 — Blocarea unui card de catre banca, pe care clientul n-o poate ridica Pana acum cardul avea un singur steag, `is_blocked`, folosit si de client (card pierdut) si — inainte de 0030 — de administr... |
| [0033_rag_categorie_si_cautare_hibrida.sql](supabase/migrations/0033_rag_categorie_si_cautare_hibrida.sql) | Optimizari RAG: filtrare pe categorie + cautare hibrida (vector + text) 1. |
| [0034_tranzactii_cont_sters.sql](supabase/migrations/0034_tranzactii_cont_sters.sql) | 0034 — stergerea unui cont nu mai pica, iar istoricul arata "Cont sters" CAUZA REALA, obtinuta abia dupa ce am ocolit GoTrue si am sters randul din profiles direct prin PostgREST (auth raspunde doar c... |
| [0035_plata_dupa_card.sql](supabase/migrations/0035_plata_dupa_card.sql) | 0035 — plata din magazin se leaga de card, nu de sesiunea celui care plateste Pana acum `creeaza_plata` primea `p_id_user` (utilizatorul logat in magazin) si cauta cardul cu `numar_card = ... |
| [0036_cereri_stergere_cont.sql](supabase/migrations/0036_cereri_stergere_cont.sql) | 0036 — Clientul isi poate cere stergerea contului, banca decide Pana acum nu exista niciun drum prin care cineva sa ceara asta din aplicatie. |
| [0037_stergere_cont_decizie.sql](supabase/migrations/0037_stergere_cont_decizie.sql) | 0037 — Banca decide cererea de inchidere, si stie sa stranga banii intai 0036 a adus doar cererea. |
| [0038_sterge_client.sql](supabase/migrations/0038_sterge_client.sql) | 0038 — Stergerea efectiva a clientului, cu poarta pe solduri Regula bancii: nu se sterge un client care mai are bani la noi. |
| [0039_cereri_suport.sql](supabase/migrations/0039_cereri_suport.sql) | 0039 — Sesizarile clientului catre banca Pana acum comunicarea mergea intr-un singur sens: `notificari` duce mesajele bancii catre client, iar `credit_mesaje` e firul de discutie de pe o cerere de |
| [0040_inchidere_cont_bancar.sql](supabase/migrations/0040_inchidere_cont_bancar.sql) | 0040 — Inchiderea unui CONT BANCAR (nu a relatiei cu banca) 0036-0038 acopera plecarea clientului de tot. |
| [0041_decizia_bancii_trece_de_trigger.sql](supabase/migrations/0041_decizia_bancii_trece_de_trigger.sql) | 0041 — Deciziile bancii treceau de politici, dar se opreau in propriul trigger CAUZA, gasita ruland fluxul cap-coada pe baza reala, nu citind codul: ERROR: DECIZIE_REZERVATA_BANCII |
| [0042_notificari_tip_valid.sql](supabase/migrations/0042_notificari_tip_valid.sql) | 0042 — Notificarile deciziilor foloseau un `tip` care nu exista CAUZA, gasita tot ruland fluxul cap-coada, nu citind codul: ERROR: 23514 new row for relation "notificari" violates check constraint |
| [0047_poprire.sql](supabase/migrations/0047_poprire.sql) | 0047 — Poprirea: se indisponibilizeaza o SUMA, nu tot contul 0030 a dat bancii un intrerupator: `blocat_administrativ`, pornit sau oprit, si din contul blocat nu mai iese niciun ban. |
| [0053_drepturi_grup.sql](supabase/migrations/0053_drepturi_grup.sql) | 0053 — drepturile membrilor intr-un grup, decise de creator: daca un membru poate scoate bani din soldul comun, plafonul lui lunar, si daca miscarile de bani se vad intre membri. |
| [0048_poprire_stornare.sql](supabase/migrations/0048_poprire_stornare.sql) | 0048 — Stornarea unei incasari din poprire: banii virati se intorc 0047 avea o gaura de operare, scrisa chiar in comentariile ei: „banii deja virati NU se intorc automat — au plecat catre creditor". |

### Teste

| Fișier | Ce face |
|---|---|
| [conftest.py](backend/tests/conftest.py) | _(fără descriere proprie în fișier)_ |
| [test_adeverinta.py](backend/tests/test_adeverinta.py) | Citirea adeverintei de venit. |
| [test_admin_identity.py](backend/tests/test_admin_identity.py) | Revizuirea manuala a verificarilor: cine intra, ce vede, ce poate schimba. |
| [test_amortizare.py](backend/tests/test_amortizare.py) | Graficul de rambursare: invariantii care trebuie sa tina la orice parametri. |
| [test_analiza_cont.py](backend/tests/test_analiza_cont.py) | Hotararea administratorului asupra unui cont: istoric, blocare, notificare. |
| [test_analiza_service.py](backend/tests/test_analiza_service.py) | _(fără descriere proprie în fișier)_ |
| [test_antrenare.py](backend/tests/test_antrenare.py) | _(fără descriere proprie în fișier)_ |
| [test_banking_tools.py](backend/tests/test_banking_tools.py) | _(fără descriere proprie în fișier)_ |
| [test_calitate_poza.py](backend/tests/test_calitate_poza.py) | Teste pentru feedback-ul de calitate a pozei. |
| [test_caracteristici.py](backend/tests/test_caracteristici.py) | Vectorul de trasaturi: ce vede modelul si ce nu are voie sa vada. |
| [test_card_tools.py](backend/tests/test_card_tools.py) | _(fără descriere proprie în fișier)_ |
| [test_categorii_tranzactii.py](backend/tests/test_categorii_tranzactii.py) | _(fără descriere proprie în fișier)_ |
| [test_chunking.py](backend/tests/test_chunking.py) | _(fără descriere proprie în fișier)_ |
| [test_citire_adeverinta.py](backend/tests/test_citire_adeverinta.py) | Citirea adeverintelor prin Azure Document Intelligence. |
| [test_coerenta_credit.py](backend/tests/test_coerenta_credit.py) | Etapa 'coerenta' a pipeline-ului AI de credite — pur, fara model, testat ca reguli.py: fiecare semnal se declanseaza sau nu, in functie de date construite. |
| [test_compression.py](backend/tests/test_compression.py) | _(fără descriere proprie în fișier)_ |
| [test_confidence.py](backend/tests/test_confidence.py) | _(fără descriere proprie în fișier)_ |
| [test_credit_tools.py](backend/tests/test_credit_tools.py) | Creditele, vazute de asistent. |
| [test_document_intelligence.py](backend/tests/test_document_intelligence.py) | _(fără descriere proprie în fișier)_ |
| [test_envelope_errors.py](backend/tests/test_envelope_errors.py) | _(fără descriere proprie în fișier)_ |
| [test_financial_advisor_context.py](backend/tests/test_financial_advisor_context.py) | _(fără descriere proprie în fișier)_ |
| [test_flux_credit.py](backend/tests/test_flux_credit.py) | Fluxul de creditare, prin HTTP, cu un depozit fals in memorie. |
| [test_flux_credit_documente.py](backend/tests/test_flux_credit_documente.py) | Adeverinta de venit: citita de masina, confirmata de om. |
| [test_gravitate_cont.py](backend/tests/test_gravitate_cont.py) | Ordonarea conturilor in lista administratorului. |
| [test_health.py](backend/tests/test_health.py) | _(fără descriere proprie în fișier)_ |
| [test_identity_service.py](backend/tests/test_identity_service.py) | _(fără descriere proprie în fișier)_ |
| [test_inchidere_cont_bancar.py](backend/tests/test_inchidere_cont_bancar.py) | Cererea de inchidere a unui CONT BANCAR, partea de backend. |
| [test_indexing.py](backend/tests/test_indexing.py) | _(fără descriere proprie în fișier)_ |
| [test_input_guardrail.py](backend/tests/test_input_guardrail.py) | _(fără descriere proprie în fișier)_ |
| [test_intent_routing.py](backend/tests/test_intent_routing.py) | _(fără descriere proprie în fișier)_ |
| [test_knowledge_repository.py](backend/tests/test_knowledge_repository.py) | _(fără descriere proprie în fișier)_ |
| [test_knowledge_tools.py](backend/tests/test_knowledge_tools.py) | _(fără descriere proprie în fișier)_ |
| [test_limite_credite.py](backend/tests/test_limite_credite.py) | Gardurile de pe rutele de creditare: limita de rata si poarta de demo. |
| [test_link_cerere_credit.py](backend/tests/test_link_cerere_credit.py) | Butonul din chat trebuie sa deschida formularul COMPLETAT. |
| [test_memory_extraction.py](backend/tests/test_memory_extraction.py) | _(fără descriere proprie în fișier)_ |
| [test_neregularitati.py](backend/tests/test_neregularitati.py) | _(fără descriere proprie în fișier)_ |
| [test_orchestrare.py](backend/tests/test_orchestrare.py) | _(fără descriere proprie în fișier)_ |
| [test_orchestrator_smoke.py](backend/tests/test_orchestrator_smoke.py) | Test de integrare pentru Orchestrator.handle_message cu dubluri async. |
| [test_output_guardrail.py](backend/tests/test_output_guardrail.py) | _(fără descriere proprie în fișier)_ |
| [test_pipeline_credit_ai.py](backend/tests/test_pipeline_credit_ai.py) | CreditAiPipeline — strict consultativ, tolerant la esec, idempotent prin hash. |
| [test_plan_reindex.py](backend/tests/test_plan_reindex.py) | _(fără descriere proprie în fișier)_ |
| [test_prompt_formular.py](backend/tests/test_prompt_formular.py) | Promptul de sistem trebuie sa lase agentul sa ceara datele care lipsesc. |
| [test_rapoarte.py](backend/tests/test_rapoarte.py) | Raportul: continut determinist, formate valide, avertismentul la locul lui. |
| [test_reguli_credit.py](backend/tests/test_reguli_credit.py) | Criteriile hard: fiecare respinge cu codul corect, si nimic nu trece pe furis. |
| [test_retrieval.py](backend/tests/test_retrieval.py) | _(fără descriere proprie în fișier)_ |
| [test_ruta_alerte.py](backend/tests/test_ruta_alerte.py) | Lantul complet al rutei /alerte: HTTP -> serviciu -> detector -> raspuns. |
| [test_rute_admin.py](backend/tests/test_rute_admin.py) | Zona administratorului: cine intra, cine nu, si ce iese. |
| [test_rute_admin_identitate.py](backend/tests/test_rute_admin_identitate.py) | Id-ul administratorului ajunge la depozit asa cum vine, nu reambalat. |
| [test_rute_admin_popriri.py](backend/tests/test_rute_admin_popriri.py) | Rutele de poprire: ce ajunge la depozit si ce se intampla la refuzul bazei. |
| [test_rute_agenti.py](backend/tests/test_rute_agenti.py) | _(fără descriere proprie în fișier)_ |
| [test_rute_si_depozit.py](backend/tests/test_rute_si_depozit.py) | Rutele si depozitul trebuie sa cada la fel. |
| [test_scorecard_credit.py](backend/tests/test_scorecard_credit.py) | Scorecard-ul: scara, praguri, si monotonia — proprietatea care conteaza. |
| [test_security_principal.py](backend/tests/test_security_principal.py) | _(fără descriere proprie în fișier)_ |
| [test_stergere_cont.py](backend/tests/test_stergere_cont.py) | Cererea de inchidere a contului: cine o poate depune si ce o blocheaza. |
| [test_tool_eligibility.py](backend/tests/test_tool_eligibility.py) | _(fără descriere proprie în fișier)_ |
| [test_transaction_export_service.py](backend/tests/test_transaction_export_service.py) | _(fără descriere proprie în fișier)_ |
| [test_venit_credit.py](backend/tests/test_venit_credit.py) | Detectia venitului: ce trebuie sa gaseasca si, mai important, ce nu. |

### Neîncadrate

| Fișier | Ce face |
|---|---|
| [backend/app/main.py](backend/app/main.py) | _(fără descriere proprie în fișier)_ |
| [frontend/src/middleware.ts](frontend/src/middleware.ts) | _(fără descriere proprie în fișier)_ |
