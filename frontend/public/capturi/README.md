# Capturi de ecran pentru `/prezentare`

Landing-ul are unsprezece sloturi de captură. Cât timp fișierul lipsește, slotul
afișează chiar instrucțiunea de mai jos, direct în pagină — nu e o eroare, e
starea normală până pui imaginea.

## Cum se face o captură

1. Pornește tot stack-ul:

   ```powershell
   .\scripts\dev-up.ps1
   ```

2. Autentifică-te cu un cont de test și populează datele de care are nevoie
   ecranul (un beneficiar, două carduri, câteva transferuri).
3. În DevTools, pornește emularea de dispozitiv și alege **iPhone 14 Pro**
   (390×844) pentru ecranele de aplicație. Pentru cele de administrare,
   fereastră normală la 1440×900.
4. Comută tema din `/setari` dacă în tabel scrie „întunecată".
5. Fă captura fără bara de adresă și fără barele DevTools — doar viewportul.
6. Salvează PNG-ul aici, cu numele exact din tabel.

## Cum se leagă în pagină

Toate capturile sunt descrise într-un singur fișier:
`frontend/src/components/prezentare/capturi.ts`. Adaugă `src` la intrarea
corespunzătoare și slotul devine imagine:

```ts
dashboard: {
  src: "/capturi/dashboard.png",   // <- calea publică
  raport: "598 / 1010",            // <- lățimea/înălțimea reală a fișierului
  alt: "Ecranul principal cu cardul de cont, soldul și acțiunile rapide",
  ...
}
```

`raport` contează: imaginea se așază cu `object-cover`, deci dacă proporția
declarată nu e cea a fișierului, captura se taie pe margini. Ia numerele direct
din proprietățile fișierului.

Nu trebuie umblat prin componentele de secțiune.

## Lista

| Fișier | Rută | Ce trebuie să se vadă | Dimensiune | Temă |
| --- | --- | --- | --- | --- |
| `dashboard.png` | `/dashboard` | cardul de cont cu IBAN și sold, grila de acțiuni rapide, ultimele tranzacții | 390×844 | deschisă |
| `transfer.png` | `/transfer` | formularul completat, cu beneficiarul ales și drawerul de confirmare deschis | 390×844 | deschisă |
| `qr.png` | `/dashboard` | drawerul „Primește bani", cu codul QR generat și IBAN-ul dedesubt | 390×844 | deschisă |
| `istoric.png` | `/istoric` | lista pe zile, sume colorate pe încasări și plăți, bara de filtre sus | 390×844 | întunecată |
| `carduri.png` | `/carduri` | două carduri cu tematici diferite, unul blocat | 390×844 | întunecată |
| `simulare.png` | `/credite/simulare` | suma și perioada alese, rata lunară calculată, butonul de cerere | 390×844 | deschisă |
| `grupuri.png` | `/grupuri` | un grup deschis, cu soldul comun, membrii și ultimele mișcări | 390×844 | deschisă |
| `asistent.png` | `/asistent` | o întrebare despre cheltuieli și răspunsul de sub ea | 390×844 | deschisă |
| `inregistrare.png` | `/register` | pasul cu fotografierea buletinului, cu indiciul de lumină afișat | 390×844 | deschisă |
| `admin-suspecte.png` | `/admin/tranzactii-suspecte` | tabelul de tranzacții semnalate, cu motivul pe fiecare rând | 1440×900 | deschisă |
| `admin-securitate.png` | `/admin/securitate` | lista de cuvinte sensibile și formularul de adăugare | 1440×900 | deschisă |

Câteva cer pregătire în plus, scrisă și în slot: pentru `transfer.png` adaugă
întâi un beneficiar din `/beneficiari`; pentru `asistent.png` backendul trebuie
să răspundă (verifică `http://localhost:8000/docs`); pentru cele de
administrare, autentifică-te cu un cont de administrator.
