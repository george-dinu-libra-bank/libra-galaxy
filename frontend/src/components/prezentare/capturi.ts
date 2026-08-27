import type { DateCaptura } from "./captura";

/**
 * Toate capturile de care are nevoie landing-ul, intr-un singur loc.
 *
 * Cand faci o captura: pui fisierul in `frontend/public/capturi/` si adaugi
 * `src` la intrarea corespunzatoare de mai jos. Nu trebuie umblat prin sectiuni.
 *
 * Aceeasi lista, in proza, e in `frontend/public/capturi/README.md`.
 */

const PORNIRE = "rulează `.\\scripts\\dev-up.ps1` și autentifică-te cu un cont de test";

export const CAPTURI = {
  dashboard: {
    src: "/capturi/dashboard.png",
    raport: "598 / 1010",
    alt: "Ecranul principal cu cardul de cont, soldul și acțiunile rapide",
    ruta: "/dashboard",
    fisier: "capturi/dashboard.png",
    dimensiune: "390×844",
    detaliu: "cardul de cont cu IBAN și sold, grila de acțiuni rapide și ultimele tranzacții",
    tema: "deschisă",
    pregatire: PORNIRE,
  },

  transfer: {
    src: "/capturi/transfer.png",
    raport: "607 / 1014",
    alt: "Formularul de transfer, cu suma și beneficiarul completate",
    ruta: "/transfer",
    fisier: "capturi/transfer.png",
    dimensiune: "390×844",
    detaliu: "formularul completat, cu beneficiarul ales și drawerul de confirmare deschis",
    tema: "deschisă",
    pregatire: `${PORNIRE}; adaugă întâi un beneficiar din /beneficiari`,
  },

  qr: {
    src: "/capturi/qr.png",
    raport: "610 / 1017",
    alt: "Drawerul cu codul QR pentru încasare",
    ruta: "/dashboard",
    fisier: "capturi/qr.png",
    dimensiune: "390×844",
    detaliu: "drawerul „Primește bani” deschis, cu codul QR generat și IBAN-ul dedesubt",
    tema: "deschisă",
    pregatire: `${PORNIRE}; apasă acțiunea rapidă „Primește”`,
  },

  istoric: {
    src: "/capturi/istoric.png",
    raport: "592 / 1006",
    alt: "Istoricul tranzacțiilor cu filtre",
    ruta: "/istoric",
    fisier: "capturi/istoric.png",
    dimensiune: "390×844",
    detaliu: "lista pe zile, cu sume colorate pe încasări și plăți, și bara de filtre sus",
    tema: "întunecată",
    pregatire: `${PORNIRE}; pornește tema întunecată din /setari și fă câteva transferuri`,
  },

  carduri: {
    src: "/capturi/carduri.png",
    raport: "609 / 1015",
    alt: "Lista de carduri cu tematici diferite",
    ruta: "/carduri",
    fisier: "capturi/carduri.png",
    dimensiune: "390×844",
    detaliu: "cel puțin două carduri cu tematici vizuale diferite, unul dintre ele blocat",
    tema: "întunecată",
    pregatire: `${PORNIRE}; emite două carduri din /carduri`,
  },

  credite: {
    src: "/capturi/simulare.png",
    raport: "654 / 1005",
    alt: "Simulatorul de credit",
    ruta: "/credite/simulare",
    fisier: "capturi/simulare.png",
    dimensiune: "390×844",
    detaliu: "suma și perioada alese, rata lunară calculată și butonul de cerere",
    tema: "deschisă",
    pregatire: PORNIRE,
  },

  grupuri: {
    src: "/capturi/grupuri.png",
    raport: "677 / 1004",
    alt: "Un grup cu sold comun și conversație",
    ruta: "/grupuri",
    fisier: "capturi/grupuri.png",
    dimensiune: "390×844",
    detaliu: "un grup deschis, cu soldul comun, membrii și ultimele mișcări",
    tema: "deschisă",
    pregatire: `${PORNIRE}; creează un grup și invită un al doilea cont`,
  },

  asistent: {
    src: "/capturi/asistent.png",
    raport: "680 / 1011",
    alt: "Conversație cu asistentul despre cheltuieli",
    ruta: "/asistent",
    fisier: "capturi/asistent.png",
    dimensiune: "390×844",
    detaliu: "o întrebare despre cheltuieli și răspunsul asistentului sub ea",
    tema: "deschisă",
    pregatire: `${PORNIRE}; backendul trebuie să răspundă (http://localhost:8000/docs)`,
  },

  inregistrare: {
    alt: "Pasul de verificare a identității din înregistrare",
    ruta: "/register",
    fisier: "capturi/inregistrare.png",
    dimensiune: "390×844",
    detaliu: "pasul cu fotografierea buletinului, cu indiciul de lumină afișat",
    tema: "deschisă",
    pregatire: "deschide /register într-o fereastră privată și mergi până la pasul de identitate",
  },

  suspecte: {
    alt: "Panoul de administrare cu tranzacții semnalate",
    ruta: "/admin/tranzactii-suspecte",
    fisier: "capturi/admin-suspecte.png",
    dimensiune: "1440×900",
    detaliu: "tabelul de tranzacții semnalate, cu motivul semnalării pe fiecare rând",
    tema: "deschisă",
    pregatire: "autentifică-te cu un cont de administrator",
    raport: "16 / 10",
  },

  securitate: {
    alt: "Editorul de cuvinte sensibile din administrare",
    ruta: "/admin/securitate",
    fisier: "capturi/admin-securitate.png",
    dimensiune: "1440×900",
    detaliu: "lista de cuvinte sensibile și formularul de adăugare",
    tema: "deschisă",
    pregatire: "autentifică-te cu un cont de administrator",
    raport: "16 / 10",
  },
} satisfies Record<string, DateCaptura>;
