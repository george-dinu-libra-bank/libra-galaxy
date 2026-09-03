import {
  Briefcase,
  GraduationCap,
  Heart,
  Home,
  PartyPopper,
  Plane,
  ShoppingBasket,
  Users,
  type LucideIcon,
} from "lucide-react";

/**
 * Aspectul unui grup: culoarea de accent si emblema (0054_tema_grup.sql).
 *
 * Fisierul tine doar mapari, ca lib/stil-card.ts — niciun hex. Rampele de
 * culoare (50→900) traiesc in globals.css, in clasele `.tema-grup-*`, fiindca
 * DESIGN.md #12 cere ca tokenii sa fie declarati o singura data acolo. Aici
 * ramane doar numele clasei.
 *
 * Mecanismul: clasa pusa pe un container rescrie `--color-primary-*` doar
 * inauntrul lui, iar clasele Tailwind obisnuite (bg-primary-600, text-primary-700,
 * hero-gradient) se recoloreaza singure. Nicio componenta nu afla ce culoare are
 * grupul — la fel cum nicio componenta nu afla daca tema aplicatiei e intunecata.
 *
 * Cand se adauga o presetare noua, se schimba in patru locuri: constraint-ul si
 * lista din functia `seteaza_tema_grup` (0054), clasa din globals.css si
 * maparile de aici.
 */

export type TemaGrup =
  | "implicit"
  | "smarald"
  | "turcoaz"
  | "ametist"
  | "zmeura"
  | "chihlimbar"
  | "scortisoara"
  | "grafit";

export type EmblemaGrup =
  | "users"
  | "home"
  | "plane"
  | "party"
  | "briefcase"
  | "heart"
  | "graduation"
  | "basket";

/**
 * Modelul de fundal al paginii grupului. Axa a doua, independenta de culoare:
 * modelele se deseneaza din rampa de accent, deci oricare merge cu oricare.
 *
 * `implicit` inseamna „lasa cerul instelat al aplicatiei" — atunci nu se
 * randeaza niciun strat. `simplu` inseamna fundal plat, fara stele si fara
 * model: si asta e o alegere, pentru cine vrea liniste.
 */
export type FundalGrup =
  | "implicit"
  | "simplu"
  | "buline"
  | "grila"
  | "romburi"
  | "diagonale"
  | "valuri"
  | "stropi"
  | "zigzag"
  | "confetti"
  | "cercuri"
  | "inimioare"
  | "nori"
  | "stele"
  | "frunze"
  | "triunghiuri";

/** Ordinea din selector. Prima e cea implicita. */
export const TEME_GRUP: TemaGrup[] = [
  "implicit",
  "smarald",
  "turcoaz",
  "ametist",
  "zmeura",
  "chihlimbar",
  "scortisoara",
  "grafit",
];

export const EMBLEME_LISTA: EmblemaGrup[] = [
  "users",
  "home",
  "plane",
  "party",
  "briefcase",
  "heart",
  "graduation",
  "basket",
];

/** Ordinea din selector: intai cele doua „fara model", apoi geometrice, apoi figurative. */
export const FUNDALURI_GRUP: FundalGrup[] = [
  "implicit",
  "simplu",
  "stropi",
  "buline",
  "confetti",
  "grila",
  "romburi",
  "diagonale",
  "zigzag",
  "valuri",
  "cercuri",
  "triunghiuri",
  "inimioare",
  "stele",
  "nori",
  "frunze",
];

/**
 * Fundalurile a caror forma vine dintr-un SVG folosit ca masca, desenata pe un
 * `::before` absolut. Elementul care poarta clasa trebuie deci sa fie pozitionat
 * — vezi comentariul din globals.css.
 */
export const FUNDALURI_CU_MASCA: FundalGrup[] = [
  "inimioare",
  "nori",
  "stele",
  "frunze",
  "triunghiuri",
];

/**
 * Clasele puse pe containerul unui grup. Doua roluri, de aceea sunt doua clase:
 *
 *   `tema-grup`        — nuanteaza suprafetele (surface / muted / line) spre
 *                        accent, ca sa se coloreze si CARDURILE din grup, nu
 *                        doar accentele de pe ele. E aceeasi pentru toti, deci
 *                        o are si `implicit`, unde e singura.
 *   `tema-grup-<nume>` — rescrie rampa `--color-primary-*`. `implicit` n-are
 *                        asa ceva: aceea e chiar rampa din `@theme`.
 */
export const CLASA_TEMA_GRUP: Record<TemaGrup, string> = {
  implicit: "tema-grup",
  smarald: "tema-grup tema-grup-smarald",
  turcoaz: "tema-grup tema-grup-turcoaz",
  ametist: "tema-grup tema-grup-ametist",
  zmeura: "tema-grup tema-grup-zmeura",
  chihlimbar: "tema-grup tema-grup-chihlimbar",
  scortisoara: "tema-grup tema-grup-scortisoara",
  grafit: "tema-grup tema-grup-grafit",
};

export const ETICHETE_TEMA_GRUP: Record<TemaGrup, string> = {
  implicit: "Albastru",
  smarald: "Smarald",
  turcoaz: "Turcoaz",
  ametist: "Ametist",
  zmeura: "Zmeură",
  chihlimbar: "Chihlimbar",
  scortisoara: "Scorțișoară",
  grafit: "Grafit",
};

/**
 * Clasa modelului de fundal. Sir gol pentru `implicit`: acolo nu se deseneaza
 * niciun strat, ca sa ramana vizibil cerul aplicatiei.
 *
 * Clasa NU contine pozitionarea — aceeasi valoare se pune si pe stratul fix de
 * pe pagina (impreuna cu `fundal-grup-strat`), si pe miniaturile din selector,
 * unde `position: fixed` ar fi gresit.
 */
export const CLASA_FUNDAL_GRUP: Record<FundalGrup, string> = {
  implicit: "",
  simplu: "fundal-grup-simplu",
  buline: "fundal-grup-buline",
  grila: "fundal-grup-grila",
  romburi: "fundal-grup-romburi",
  diagonale: "fundal-grup-diagonale",
  valuri: "fundal-grup-valuri",
  stropi: "fundal-grup-stropi",
  zigzag: "fundal-grup-zigzag",
  confetti: "fundal-grup-confetti",
  cercuri: "fundal-grup-cercuri",
  inimioare: "fundal-grup-inimioare",
  nori: "fundal-grup-nori",
  stele: "fundal-grup-stele",
  frunze: "fundal-grup-frunze",
  triunghiuri: "fundal-grup-triunghiuri",
};

export const ETICHETE_FUNDAL_GRUP: Record<FundalGrup, string> = {
  implicit: "Cerul Galaxy",
  simplu: "Simplu",
  buline: "Buline",
  grila: "Grilă",
  romburi: "Romburi",
  diagonale: "Diagonale",
  valuri: "Valuri",
  stropi: "Stropi",
  zigzag: "Zigzag",
  confetti: "Confetti",
  cercuri: "Cercuri",
  inimioare: "Inimioare",
  nori: "Nori",
  stele: "Stele",
  frunze: "Frunze",
  triunghiuri: "Triunghiuri",
};

export const EMBLEME_GRUP: Record<EmblemaGrup, LucideIcon> = {
  users: Users,
  home: Home,
  plane: Plane,
  party: PartyPopper,
  briefcase: Briefcase,
  heart: Heart,
  graduation: GraduationCap,
  basket: ShoppingBasket,
};

/** Etichetele sunt si `aria-label`-ul butoanelor din selector, nu doar decor. */
export const ETICHETE_EMBLEMA_GRUP: Record<EmblemaGrup, string> = {
  users: "Oameni",
  home: "Casă",
  plane: "Vacanță",
  party: "Petrecere",
  briefcase: "Muncă",
  heart: "Familie",
  graduation: "Școală",
  basket: "Cumpărături",
};

/**
 * Normalizeaza o valoare bruta din baza, ca `temaDinCookie` din lib/tema.ts.
 *
 * Nu e paranoia: constraint-ul din 0054 apara scrierea, dar o presetare scoasa
 * intr-o versiune viitoare ar ramane pe randurile vechi. Fara normalizare am
 * pune pe container `class="undefined"` si am cauta bug-ul in CSS.
 */
export function temaGrupValida(valoare: string | null | undefined): TemaGrup {
  return TEME_GRUP.includes(valoare as TemaGrup) ? (valoare as TemaGrup) : "implicit";
}

export function emblemaGrupValida(valoare: string | null | undefined): EmblemaGrup {
  return EMBLEME_LISTA.includes(valoare as EmblemaGrup)
    ? (valoare as EmblemaGrup)
    : "users";
}

export function fundalGrupValid(valoare: string | null | undefined): FundalGrup {
  return FUNDALURI_GRUP.includes(valoare as FundalGrup)
    ? (valoare as FundalGrup)
    : "implicit";
}
