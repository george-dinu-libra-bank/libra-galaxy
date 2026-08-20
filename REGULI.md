# Reguli — din experiența directă pe acest proiect

Nu e teorie generică — fiecare regulă de aici a apărut dintr-o problemă reală, verificată live, în timpul lucrului la `backend/` și la asistentul AI. Actualizează documentul când mai apare o lecție de genul ăsta.

---

## 1. Backend — gotcha-uri verificate live

**Microsoft Foundry (chat + embeddings)**
- Endpoint-ul din blade-ul „Models" (`https://<resursă>.openai.azure.com/models`) e compatibil OpenAI **direct** — folosește clientul `OpenAI`/`AsyncOpenAI` cu `base_url=<endpoint>`, NU `AzureOpenAI`/`AsyncAzureOpenAI` cu `azure_endpoint`+`api_version` (răspunde 404 pe acest tip de resursă).
- `gpt-5-mini` e model de reasoning: respinge orice `temperature` diferit de valoarea implicită (400 `unsupported_value`) — nu trimite acest parametru deloc.
- Tokenii de reasoning se scad din același buget ca răspunsul vizibil, invizibil — un „OK" poate consuma 64-128 tokeni de reasoning. `max_completion_tokens` trebuie generos (2000+), altfel răspunsul iese trunchiat la gol.

**Azure AI Speech (voce)**
- REST-ul de recunoaștere/sinteză merge pe domeniul **regional** (`<regiune>.stt/tts.speech.microsoft.com`), nu pe endpoint-ul resursei (`*.cognitiveservices.azure.com`, care răspunde 404 pe aceste căi).
- STT întoarce `RecognitionStatus: Success` cu `DisplayText` **gol** pentru formate audio nesuportate (ex. MP3) — nu aruncă eroare, deci un test superficial poate păcăli. Format confirmat funcțional: WAV/PCM. Format audio din browser (MediaRecorder): preferă `audio/ogg;codecs=opus` dacă e suportat, trimite mereu `content-type`-ul real raportat de recorder, nu unul presupus.

**Supabase**
- Proiectele noi Supabase semnează JWT-urile cu **ES256** (chei asimetrice), nu cu un secret HS256 partajat — verificarea se face prin JWKS (`/auth/v1/.well-known/jwks.json`), nu printr-un `SUPABASE_JWT_SECRET`. Nu presupune HS256 fără să verifici `jwks.json` întâi.
- Cheile Supabase noi: `sb_publishable_...` = anon/client-side (RLS activ). `sb_secret_...` = echivalentul service_role, ocolește RLS. Nu le încurca — un `sb_publishable_...` pus ca service-role key produce erori de RLS greu de diagnosticat (insert-urile din backend eșuează silențios cu „row-level security policy").
- `.maybe_single().execute()` din `supabase-py`/`postgrest-py` întoarce `None` **direct** (nu un răspuns cu `.data=None`) când nu există niciun rând — orice cod care face `result.data` fără să verifice `result is not None` întâi va arunca `AttributeError`.

---

## 2. O singură implementare per responsabilitate

Când doi oameni lucrează în paralel pe `backend/`, e ușor să apară două module cu același scop (config, logging, erori, auth) în locuri diferite. Regula: **quando se descoperă o coliziune, se consolidează pe UNA din ele, niciodată nu rămân două în paralel** — alegerea se face după care e mai completă/mai integrată cu restul sistemului (nu după cine a scris-o primul).

Exemplu real: `app/core/config.py`+`errors.py`+`logging.py`+`security.py` (deja folosite de tot orchestratorul) vs. `app/infrastructure/config.py`+`errors.py`+`logging.py`+auth separat dintr-un branch paralel — s-au păstrat cele din `app/core/`, iar auth-ul nou (modul cu cheie internă, pentru apeluri Next.js înainte de sesiune) a fost **adăugat ca funcție nouă** în `core/security.py`, nu ținut separat.

---

## 3. Migrații Supabase

- Numerotare secvențială, strict aditivă — niciodată nu se modifică o migrație deja aplicată.
- **Verifică numărul următor liber înainte să creezi o migrație nouă** — dacă doi oameni pornesc de la același ultim număr cunoscut în paralel, apare coliziune (`0004_ceva.sql` de două ori, cu conținut diferit). La merge: se renumerotează una dintre ele (`git mv`), nu se aleg conflict markers pe conținutul SQL.
- **Pot fi aplicate de mine (Claude), prin serverul MCP Supabase** — `apply_migration` pentru DDL, `execute_sql` pentru verificări. Regula anterioară spunea că nu se poate, ceea ce era adevărat doar despre cheia service-role: aceea e într-adevăr o cheie REST și nu poate rula DDL. Dar există alte două căi, amândouă verificate:
  - serverul MCP hostat (`claude mcp add --scope project --transport http supabase "https://mcp.supabase.com/mcp"`), după autorizare OAuth din `/mcp`;
  - local, prin `.\scripts\supabase.ps1` — CLI-ul rulează în container, iar `config.toml` are `[db.migrations] enabled = true`, deci `db reset` reaplică tot.
- **Gotcha la MCP-ul Supabase**: URL-ul din `.mcp.json` trebuie să fie exact `https://mcp.supabase.com/mcp`, fără query string. Metadatele lui (`/.well-known/oauth-protected-resource/mcp`) declară `"resource": "https://mcp.supabase.com/mcp"`, iar clientul trimite URL-ul configurat ca indicator de resursă (RFC 9728). Cu `?project_ref=...&features=...` în URL, `api.supabase.com` respinge autorizarea cu `resource: Resource must be a valid MCP endpoint`. Proiectul se dă oricum ca parametru la fiecare tool.
- **`supabase_migrations` e GOL în proiectul cloud** — schema existentă a fost construită direct în SQL Editor. Fișierele din `supabase/migrations/` descriu *intenția*, nu istoricul aplicat, și cele două chiar au divergat: `0008_rol_administrator.sql` nu e aplicat (nu există `profiles.rol`, nici `public.este_administrator()` înainte de `0009`, nici `acces_administrator`), iar rolurile trăiesc de fapt în `public.user_roles`. **Verifică schema reală cu `list_tables` înainte să te bazezi pe un fișier de migrație.**
- Înainte de o migrație pe cloud, ia un instantaneu al stării reale (vezi `0000_instantaneu_inainte_de_credite.sql`, generat din catalogul Postgres). Nu înlocuiește backupul automat Supabase, dar arată exact ce era acolo înainte.
- După orice DDL, rulează `get_advisors` cu `type: "security"` — prinde tabele cu RLS activat fără politici și funcții `SECURITY DEFINER` expuse ca RPC pentru `anon`.

---

## 4. `.env` / `.env.example`

- Trebuie să aibă **exact aceleași chei** — verifică programatic (`set(dotenv_values('.env')) == set(dotenv_values('.env.example'))`), nu vizual.
- Niciodată comentarii inline pe aceeași linie cu o variabilă (`CHEIE=  # explicație`) — `python-dotenv` nu le taie, valoarea devine literal `"# explicație"`. Explicațiile stau pe linie proprie, deasupra.
- La un merge cu variabile noi de ambele părți: unește ambele seturi în `.env.example` (valori goale/implicite) **și** în `.env`-ul local (cu valori reale sau placeholder), ca cele două fișiere să rămână sincronizate.

---

## 5. Docker — sursa unică de adevăr pentru rulare

- `docker compose up --build` din rădăcină pornește tot; nimeni nu instalează Node/Python local.
- `./start.sh` / `.\start.ps1` — verifică Docker pornit, creează `.env` din `.env.example` dacă lipsește, apoi `docker compose up --build`.
- Dependințe grele/sensibile la versiune (ex. `deepface`, `tf-keras`, `opencv-python-headless`) se pinează exact (`==`), nu cu `>=` — restul dependințelor pot rămâne flexibile (`>=`).
- Verifică imaginea chiar se construiește și containerul chiar pornește înainte să declari o schimbare „gata" — un import care lipsește sau o versiune incompatibilă nu se vede din citirea codului.

---

## 6. Conflicte de merge — nu accepta orbește „current"

**Cea mai importantă regulă din sesiunea asta.** La un conflict, „current" (HEAD) nu e automat varianta corectă doar pentru că e a ta. Citește efectiv ambele părți ale conflictului:

- Dacă partea „incoming" e doar un placeholder vechi / cod mort → păstrează „current".
- Dacă partea „incoming" e un refactor real (funcții mutate în `lib/utils.ts`), un fix de accesibilitate (`focus-visible:ring-4`, cerut explicit de `DESIGN.md`), sau orice altă îmbunătățire legitimă → **păstrează „incoming"**, chiar dacă înseamnă să renunți la codul tău local.
- Pentru fișiere unde ambele părți au construit funcționalitate reală și diferită (backend paralel, feature nouă) → nu e un conflict de linie, e o **decizie de arhitectură**: se integrează ambele funcționalități, consolidând pe infrastructura comună (vezi regula #2), nu se alege un „câștigător".

---

## 7. Verificare înainte de „gata"

Nu se declară o schimbare terminată doar din citirea codului. Ordinea de verificare, de la ieftin la scump:
1. `pytest` (logică pură, fără DB/Foundry) — rapid, rulează mereu.
2. `npm run typecheck` — prinde erori de tip fără server pornit.
3. Apel live cu credențiale reale (Foundry/Speech/Supabase) — prinde discrepanțe între documentație și comportamentul real al API-ului (ex. toate gotcha-urile din secțiunea 1 au fost găsite așa, nu din citirea docs Microsoft/Supabase).
4. Container Docker chiar construit și pornit, cu request real prin el.

---

## 8. Cum lucrăm împreună

- Eu (Claude) editez fișiere, rulez teste, fac build-uri Docker, verific live cu credențiale — toate astea sunt reversibile/locale.
- **Git rămâne treaba ta** — nu rulez `git add`/`git commit`/`git push`. Rezolv conținutul fișierelor la conflict, apoi îți dau comenzile exacte de rulat.
- Când găsesc o discrepanță reală între ce spune documentația/codul existent și ce se comportă efectiv (schema DB, format API extern, versiune de bibliotecă) — o semnalez explicit, nu aleg tacit o variantă.
