# Libra — Sistem de design

Aplicație de mobile banking pe web. Ghidul de față este sursa unică de adevăr pentru
culori, spațieri, componente și mișcare. Orice ecran nou se construiește din piesele
descrise aici, nu din valori inventate ad-hoc.

**Stack vizual:** Next.js 16 (App Router) · Tailwind CSS 4 (tokens în `@theme`) ·
[lucide-react](https://lucide.dev) pentru iconițe · [vaul](https://vaul.emilkowal.ski)
pentru drawere.

---

## 1. Principii

1. **Light theme, mereu.** Fundal deschis, un singur albastru dominant, accente rare.
   Nu implementăm dark mode în această fază — nu adăugăm variante `dark:`.
2. **Ecranul e o „foaie".** Fiecare pagină de autentificare are un *hero* albastru sus
   și un card alb rotunjit care urcă peste el. Cardul e locul unde se lucrează.
3. **Un singur buton primar per ecran.** Restul acțiunilor sunt link-uri sau butoane
   ghost. Ambiguitatea costă bani într-o aplicație bancară.
4. **Mișcare discretă.** Animațiile confirmă o acțiune sau orientează utilizatorul.
   Nimic decorativ care depășește 300 ms.
5. **Mobile-first.** Design pentru 390 px lățime, apoi extins la desktop prin centrare
   și un panou lateral, nu prin întinderea conținutului.
6. **Ce nu merită o pagină, merită un drawer.** Detalii, confirmări, explicații, filtre,
   selectoare → `vaul`, nu rută nouă.

---

## 2. Culori

Albastrul este mai deschis și mai „azuriu" decât indigo-ul din referință — mai apropiat
de un albastru de produs financiar modern, cu mai puțin violet.

### 2.1 Primar

| Token         | HEX       | Utilizare                                       |
| ------------- | --------- | ----------------------------------------------- |
| `primary-50`  | `#EEF4FF` | fundal tint, stări hover pe rânduri             |
| `primary-100` | `#DBE7FE` | chips, badge-uri, buton dezactivat              |
| `primary-200` | `#BFD3FD` | borduri subtile pe suprafețe colorate           |
| `primary-300` | `#93B4FB` | iconițe decorative pe hero                      |
| `primary-400` | `#6693F8` | gradient hero (capătul deschis)                 |
| `primary-500` | `#4C86F5` | **accent principal**, focus ring                |
| `primary-600` | `#2F6FED` | **buton primar**, link-uri, iconițe active      |
| `primary-700` | `#2358C9` | hover pe buton primar                           |
| `primary-800` | `#1C46A0` | pressed / active                                |
| `primary-900` | `#153478` | text pe fundaluri foarte deschise, gradient hero|

### 2.2 Neutre

| Token         | HEX       | Utilizare                                 |
| ------------- | --------- | ----------------------------------------- |
| `bg`          | `#F4F7FC` | fundalul aplicației (nu alb pur)          |
| `surface`     | `#FFFFFF` | carduri, foi, drawere                     |
| `line`        | `#E3E9F2` | borduri de card și input                  |
| `muted`       | `#F7F9FD` | input dezactivat, rânduri alternante      |
| `ink`         | `#0F1B33` | titluri, valori                           |
| `ink-soft`    | `#4A5773` | text de corp                              |
| `ink-faint`   | `#8A96AE` | label-uri, placeholder, ajutor            |

### 2.3 Accente (folosite parcimonios — punctele colorate din badge, statusuri)

| Token     | HEX       | Utilizare                                  |
| --------- | --------- | ------------------------------------------ |
| `success` | `#12B981` | încasări, confirmări, validare OK          |
| `danger`  | `#F0435F` | erori, plăți respinse, acțiuni distructive |
| `warning` | `#F5A524` | atenționări, verificare în așteptare       |
| `info`    | `#4C86F5` | informativ (alias `primary-500`)           |

### 2.4 Gradientul hero

```css
background: linear-gradient(160deg, #4C86F5 0%, #2F6FED 55%, #2358C9 100%);
```

Peste el se pot pune două cercuri `bg-white/8` foarte mari, blurate, pentru adâncime.
Nimic altceva. Textul pe hero: alb (`#FFFFFF`) pentru titlu, `primary-100` pentru subtitlu.

### 2.5 Reguli de contrast

- Text pe `primary-600` → alb. Text pe `primary-100` → `primary-900`.
- Nu se folosește `primary-400` sau mai deschis pentru text pe alb.
- Toate perechile text/fundal respectă minim **4.5:1** (WCAG AA); iconițele funcționale minim **3:1**.

---

## 3. Tipografie

Font: **Geist Sans** (deja configurat în `layout.tsx`), fallback `system-ui`.
Cifrele de sold și IBAN folosesc `font-variant-numeric: tabular-nums`.

| Rol            | Mărime / linie | Greutate | Culoare      |
| -------------- | -------------- | -------- | ------------ |
| Display (sold) | 32 / 38        | 700      | `ink`       |
| H1 ecran       | 26 / 32        | 700      | `ink` sau alb pe hero |
| H2 secțiune    | 18 / 24        | 600      | `ink`       |
| Corp           | 15 / 22        | 400      | `ink-soft`  |
| Label input    | 13 / 18        | 500      | `ink-soft`  |
| Ajutor / eroare| 12.5 / 18      | 400      | `ink-faint` / `danger` |
| Buton          | 15 / 20        | 600      | contextual   |

Tracking: `-0.02em` pentru titluri ≥ 24 px, `0` în rest.

---

## 4. Spațiere, rază, umbre

**Grilă de 4 px.** Valori permise: 4, 8, 12, 16, 20, 24, 32, 40, 48, 64.

| Element                  | Rază      |
| ------------------------ | --------- |
| Foaia albă peste hero    | `32px` sus|
| Card / drawer            | `24px`    |
| Input, buton             | `14px`    |
| Chip, badge              | `999px`   |
| Badge circular cu iconiță| `999px`   |

Umbre (moi, albastre — niciodată negru pur):

```css
--shadow-sm:  0 1px 2px rgba(15, 27, 51, 0.05);
--shadow-md:  0 8px 24px -8px rgba(35, 88, 201, 0.18);
--shadow-lg:  0 24px 48px -16px rgba(35, 88, 201, 0.24);
--shadow-btn: 0 8px 20px -8px rgba(47, 111, 237, 0.55);
```

Padding standard pe orizontală în interiorul foii: **24 px** (mobil), 32 px (≥ 640 px).

---

## 5. Layout de ecran (autentificare)

```
┌──────────────────────────────┐
│  hero albastru (gradient)    │   ~34% din înălțime, min 220px
│  ‹ înapoi     Autentificare  │   buton back = ChevronLeft în cerc white/15
│  Bine ai revenit             │
├──────────────────────────────┤ ← rounded-t-[32px], -mt-6, shadow-lg
│         ( 🔒 )               │   badge 72px, alb, umbră, iconiță primary-600
│                              │   3 puncte accent la 45°/135°/315° (success/danger/warning)
│  [ Email                   ] │
│  [ Parolă               👁 ] │
│              Ai uitat parola?│
│                              │
│  [   Autentificare        ]  │   buton primar full-width, 52px
│                              │
│  ─────────  sau  ─────────   │
│  [ 🔒 Continuă cu biometrie ]│   buton secundar (opțional)
│                              │
│  Nu ai cont?  Înregistrează-te│
└──────────────────────────────┘
```

**Desktop (≥ 1024 px):** același conținut într-un card de max `440px`, centrat vertical,
pe fundal `bg`; hero-ul devine banda superioară a cardului. În stânga, opțional, un panou
albastru cu logo și un slogan — nu se întinde formularul pe toată lățimea.

---

## 6. Componente

### 6.1 Buton

| Variantă    | Fundal              | Text        | Notă                                   |
| ----------- | ------------------- | ----------- | -------------------------------------- |
| `primary`   | `primary-600`       | alb         | `shadow-btn`; hover `primary-700`      |
| `secondary` | `primary-50`        | `primary-700` | bordură `primary-100`                |
| `ghost`     | transparent         | `ink-soft` | hover `primary-50`                     |
| `danger`    | `danger`            | alb         | doar pentru acțiuni ireversibile       |

- Înălțime: **52 px** (primar, full-width în formulare), 44 px în drawere/inline.
- Dezactivat: `primary-100` + text `primary-300`, fără umbră, `cursor-not-allowed`.
- Loading: iconița `Loader2` cu `animate-spin` la stânga, textul rămâne, butonul e blocat.
- Apăsare: `active:scale-[0.98]` pe 120 ms. Atât.

### 6.2 Input

- Container: `surface`, bordură `line` 1px, rază 14 px, înălțime 52 px, padding 16 px.
- Label deasupra, 13 px, `ink-soft`, spațiu 6 px până la câmp.
- Iconiță lucide la stânga (18 px, `ink-faint`; devine `primary-600` la focus).
- Focus: bordură `primary-500` + `ring-4 ring-primary-500/12`, tranziție 150 ms.
- Eroare: bordură `danger`, mesaj sub câmp cu `AlertCircle` 14 px, apariție prin
  `fade-in` + translate 4 px.
- Succes de validare (CNP/IBAN corect): `Check` 16 px `success` în dreapta.
- Parolă: buton `Eye`/`EyeOff` în dreapta, țintă de atingere 44 px.
- Câmpuri formatate (telefon, IBAN, CNP): `inputMode` potrivit și grupare vizuală
  la 4 caractere pentru IBAN.

### 6.3 Checkbox (ex. termeni și condiții)

Pătrat 20 px, rază 6 px, bordură `line`; bifat → `primary-600` cu `Check` alb care
apare prin `scale(0.6) → 1` pe 150 ms. Textul link-uit e `primary-600`, `font-medium`.

### 6.4 Badge circular cu iconiță

Cerc alb 72 px, `shadow-md`, iconiță lucide 30 px `primary-600`, poziționat cu
`-mt-9` peste marginea foii. Trei puncte de 8 px (`success`, `danger`, `warning`) la
distanță de 4 px de cerc — semnătura vizuală a aplicației, se păstrează identică pe
toate ecranele de auth.

### 6.5 Card de cont / tranzacție (pentru ecranele post-login)

Card cu gradient hero, rază 24 px, IBAN cu `tabular-nums` și spațiere la 4 caractere,
sold în display 32 px. Sub el, grilă 3×N de acțiuni rapide: pătrat alb 72 px, rază 18 px,
iconiță lucide 22 px `primary-600`, etichetă 12 px pe două rânduri.

### 6.6 Iconografie — `lucide-react`

Pachet: **`lucide-react`** (declarat în `frontend/package.json`). Nu se amestecă alte
seturi de iconițe și nu se folosesc emoji în UI.

```tsx
import { Mail, Loader2 } from "lucide-react";

<Mail size={18} strokeWidth={1.75} className="text-ink-faint" aria-hidden />;
<Loader2 size={18} className="animate-spin" aria-hidden />;
```

**Reguli de folosire**

- Import **nominal** (`import { Mail } from "lucide-react"`), niciodată `import * as`.
- `strokeWidth={1.75}` peste tot; dimensiuni doar 16 / 18 / 20 / 24 (30 pentru badge-ul
  circular de pe ecranele de auth).
- Culoarea vine din `className` (`text-ink-faint`, `text-primary-600`, `text-danger`),
  nu din prop-ul `color`.
- Iconiță **decorativă** (lângă un text care spune deja totul) → `aria-hidden`.
  Iconiță **singură** într-un buton → `aria-label` pe buton.
- Nu se scalează iconițele cu `w-*`/`h-*` peste `size` — o singură sursă de adevăr.
- Set canonic pe care îl refolosim: `Mail`, `Lock`, `Eye`, `EyeOff`, `User`, `Phone`,
  `IdCard`, `Landmark`, `CreditCard`, `ArrowLeftRight`, `ChevronLeft`, `ChevronRight`,
  `Check`, `AlertCircle`, `Loader2`, `ShieldCheck`, `Info`, `X`.

---

## 7. Mișcare

Durate: **120 ms** (feedback tactil), **180 ms** (hover/focus), **240 ms** (intrare
element), **320 ms** (drawer). Easing implicit: `cubic-bezier(0.22, 1, 0.36, 1)`.

| Situație                  | Animație                                                  |
| ------------------------- | --------------------------------------------------------- |
| Intrare foaie albă        | `translateY(16px) → 0` + fade, 320 ms                     |
| Câmpuri de formular       | fade + `translateY(8px)`, decalaj (stagger) 40 ms          |
| Apăsare buton             | `scale(0.98)`, 120 ms                                     |
| Trimitere formular        | `Loader2` rotativ; la succes `Check` care intră prin scale |
| Eroare de câmp            | mesaj fade-in; **fără** shake                             |
| Eroare globală de formular| bandă `danger/8` care se desfășoară pe înălțime, 200 ms   |
| Tranziție între ecrane    | doar fade 180 ms — fără slide de pagină                    |

**Obligatoriu:** tot ce mișcă respectă `@media (prefers-reduced-motion: reduce)` →
durate reduse la 0.01 ms, fără transformări.

---

## 8. Drawere — `vaul`

Pachet: **`vaul`** (declarat în `frontend/package.json`). Wrapper-ul propriu, deja stilizat
conform tokenilor, este [`components/ui/drawer.tsx`](frontend/src/components/ui/drawer.tsx).
**În ecrane se importă wrapper-ul, nu `vaul` direct** — așa toate drawerele arată identic.

Vaul este singura soluție de suprapunere din aplicație: nu folosim modale centrate, nu
folosim `alert()` / `confirm()`, nu instalăm alt pachet de dialog.

### 8.1 Când drawer și când pagină

| Situație                                            | Alegere  |
| --------------------------------------------------- | -------- |
| Detaliul unei tranzacții din listă                   | drawer   |
| Confirmarea unui transfer (recapitulare + „Trimite") | drawer   |
| Alegerea contului sursă / a beneficiarului           | drawer   |
| Explicații și texte legale („De ce cerem CNP?", T&C) | drawer   |
| Editarea unui singur câmp de profil (telefon)        | drawer   |
| Filtre pe istoric, selector de perioadă / sumă       | drawer   |
| Meniu de acțiuni pe un card                          | drawer   |
| Login, register, resetare parolă                     | pagină   |
| Dashboard, istoric complet, setări                   | pagină   |
| Orice flux care trebuie să supraviețuiască unui refresh sau să fie partajabil prin URL | pagină |

Regula scurtă: **dacă are nevoie de URL propriu, e pagină; altfel e drawer.**

### 8.2 Anatomie

```
Drawer.Root  → Drawer.Trigger
             → Drawer.Portal
                 → Drawer.Overlay   bg-ink/40, fade 240 ms
                 → Drawer.Content   surface, rounded-t-[24px], max-h 92vh
                     ├ mâner: 40×4 px, bg-line, rază completă, centrat, mt 12 px
                     ├ Drawer.Title (H2 18 px) + buton X (ghost, 40 px) dacă e nevoie
                     ├ Drawer.Description (12.5 px, ink-faint) — obligatoriu pt. a11y
                     ├ conținut, padding 24 px, scroll intern dacă depășește
                     └ footer lipit jos: buton primar full-width + safe-area inferioară
```

### 8.3 Cum se folosește

**Necontrolat** (drawer informativ, deschis dintr-un buton):

```tsx
import { Info } from "lucide-react";
import { Drawer, DrawerTrigger, DrawerContent } from "@/components/ui/drawer";

<Drawer>
  <DrawerTrigger className="inline-flex items-center gap-1 text-primary-600">
    <Info size={16} strokeWidth={1.75} aria-hidden />
    De ce cerem CNP-ul?
  </DrawerTrigger>

  <DrawerContent
    title="De ce cerem CNP-ul?"
    description="Verificarea identității este obligatorie la deschiderea unui cont."
  >
    <p className="text-[15px] leading-[22px] text-ink-soft">…</p>
  </DrawerContent>
</Drawer>;
```

**Controlat** (confirmare cu acțiune, se închide din cod după succes):

```tsx
const [deschis, setDeschis] = useState(false);

<Drawer open={deschis} onOpenChange={setDeschis}>
  <DrawerContent
    title="Confirmă transferul"
    description="Verifică datele înainte de a trimite banii."
    footer={
      <Button onClick={trimite} loading={seTrimite} className="w-full">
        Trimite 250,00 RON
      </Button>
    }
  >
    …
  </DrawerContent>
</Drawer>;
```

**Drawer înalt, cu snap points** (listă lungă — se deschide pe jumătate, urcă la scroll):

```tsx
<Drawer snapPoints={[0.55, 1]}>…</Drawer>
```

### 8.4 Reguli

- **Un singur drawer deschis** simultan. Fără drawere imbricate; dacă un pas duce la
  altul, se schimbă conținutul aceluiași drawer, nu se deschide al doilea.
- `title` și `description` sunt **obligatorii** — vaul le mapează pe `Drawer.Title` /
  `Drawer.Description` pentru cititoarele de ecran. Dacă titlul nu trebuie văzut,
  se ascunde vizual, nu se omite.
- Închidere prin: swipe în jos, tap pe overlay, `Esc`, butonul din footer. Se blochează
  swipe-ul (`dismissible={false}`) **doar** cât timp o operațiune cu bani e în curs.
- Direcția implicită este `bottom`. `direction="right"` doar pe desktop, pentru panouri
  de detaliu; pe mobil rămâne mereu de jos.
- Butonul primar din footer poartă eticheta acțiunii concrete — „Trimite 250,00 RON",
  „Șterge beneficiarul" — niciodată „OK" sau „Confirmă".
- Maxim **un** buton primar în footer; acțiunea secundară e ghost, în stânga lui.
- Padding de siguranță jos: `pb-[max(24px,env(safe-area-inset-bottom))]`.
- Conținutul se montează la deschidere (nu se ține în DOM), ca animația să pornească curat.
- Drawer-ul nu ține stare critică: dacă utilizatorul îl închide accidental, nu pierde
  nimic din ce a completat într-un formular de pe pagină.
- Animația e cea implicită din vaul (~320 ms, cu urmărirea degetului la swipe) — nu se
  suprascriu duratele; `prefers-reduced-motion` e respectat global din `globals.css`.

---

## 9. Formulare și validare

- Validare **la blur**, nu la fiecare tastă; după prima eroare, câmpul se revalidează live.
- Mesajele sunt în română, concrete: „CNP-ul trebuie să aibă 13 cifre", nu „Valoare invalidă".
- Erorile de la server (email deja folosit, parolă greșită) apar în banda globală de sus
  a formularului, cu iconiță `AlertCircle`.
- Butonul primar nu se dezactivează cât timp formularul e incomplet — se dezactivează
  doar în timpul trimiterii. Utilizatorul trebuie să poată apăsa și să vadă ce lipsește.
- Câmpuri sensibile (CNP, parolă) nu se pre-completează și au `autoComplete` corect.

---

## 10. Accesibilitate

- Țintă de atingere minim **44×44 px**.
- Focus vizibil peste tot: `ring-4 ring-primary-500/25` — nu se elimină outline-ul.
- Fiecare input are `<label>` real, legat prin `htmlFor`.
- Erorile: `aria-invalid` pe câmp + `aria-describedby` către mesaj + `role="alert"`.
- Stările de încărcare anunță prin `aria-busy` / text vizual, nu doar prin spinner.
- Limba documentului: `lang="ro"`; textele cu diacritice complete.

---

## 11. Conținut și ton

Româna, persoana a doua, fără jargon bancar inutil.
„Bine ai revenit", „Deschide-ți contul în 2 minute", „Trimitem un cod pe telefon".
Sumele: `1.250,00 RON` (separator de mii `.`, zecimale `,`).
IBAN afișat grupat: `RO49 AAAA 1B31 0075 9384 0000`.
CNP-ul nu se afișează niciodată integral după înregistrare — doar `1•••••••••234`.

---

## 12. Tokens în cod

Se declară o singură dată în `src/app/globals.css`, în blocul `@theme`, și se folosesc
prin clase Tailwind (`bg-primary-600`, `text-text-soft`, `rounded-card`, `shadow-btn`).
**Nu se scriu hex-uri direct în componente.**
