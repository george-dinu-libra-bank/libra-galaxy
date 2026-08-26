# Galaxy Bank — Knowledge Base

> Bază de cunoștințe fictivă, creată pentru testarea unui sistem RAG și a unor agenți AI. Galaxy Bank nu reprezintă o instituție bancară reală.

## Scop

Structura separă informația despre bancă, produse, operațiuni, securitate, conformitate, comisioane, suport și întrebări frecvente. Documentele sunt intenționat modulare pentru chunking și recuperare semantică.

## Principiul sursei de adevăr

`_source-of-truth.md` este documentul intern care definește valorile canonice: produse, limite, comisioane, dobânzi, contacte, program și reguli de securitate. Documentele operaționale trebuie interpretate împreună cu acesta.

## Structură

- `banca/` — prezentare, valori, contact și program.
- `conturi/` — conturi curente, de economii, valută și deschidere.
- `carduri/` — carduri, limite, blocare, înlocuire și securitate.
- `plati/` — transferuri, SEPA, RoPay, plăți recurente și plăți cu cardul.
- `valuta/` — schimb valutar, cursuri și multivalută.
- `economii/` — economisire, depozite și obiective.
- `credite/` — credite personale, ipotecare, card de credit, eligibilitate și rambursare anticipată.
- `grupuri/` — creare și administrare de grupuri, permisiuni și roluri, cheltuieli partajate și decontări, grupuri de familie și utilizatori minori, securitate/fraudă/dispute în grupuri, seifuri și obiective de grup.
- `mobile-banking/` — aplicația mobilă și accesul digital.
- `securitate/` — fraudă, tranzacții suspecte, contestații și phishing.
- `conformitate/` — KYC, AML, GDPR și identificarea clientului.
- `taxe-si-comisioane/` — tarifele aplicabile.
- `suport/` — contact, reclamații, soluționare și escaladare.
- `faq/` — întrebări frecvente tematice.

## Convenții pentru agenți AI

1. Nu inventa limite sau comisioane care nu sunt documentate.
2. Pentru valori numerice, preferă documentul specific produsului și verifică `_source-of-truth.md`.
3. Când o procedură implică fraudă sau securitate, indică și documentul relevant din `securitate/`.
4. Dacă informația nu este documentată, agentul trebuie să spună că nu există o regulă explicită în baza disponibilă.
