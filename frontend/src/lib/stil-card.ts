import type { StilCard } from "@/lib/data/carduri";

/** Gradientul vizual pentru fiecare tematica de card. Doar tokeni din DESIGN.md. */
export const GRADIENTE_STIL_CARD: Record<StilCard, string> = {
  standard:
    "linear-gradient(160deg, var(--color-primary-500) 0%, var(--color-primary-600) 55%, var(--color-primary-700) 100%)",
  silver: "linear-gradient(160deg, var(--color-ink-soft) 0%, var(--color-ink) 100%)",
  gold: "linear-gradient(160deg, color-mix(in srgb, var(--color-warning) 55%, white) 0%, var(--color-warning) 55%, color-mix(in srgb, var(--color-warning) 65%, black) 100%)",
};

export const ETICHETE_STIL_CARD: Record<StilCard, string> = {
  standard: "Standard",
  silver: "Silver",
  gold: "Gold",
};

/**
 * Pe ce culoare de text se scrie fiecare tematica.
 *
 * NU e o preferinta estetica, e o problema de contrast masurabila. Cardul `gold`
 * porneste din `color-mix(warning 55%, white)` — un fundal DESCHIS. Textul alb
 * folosit pana acum pe el statea sub pragul de 4.5:1 cerut de DESIGN.md #2.5,
 * adica exact regula pe care restul aplicatiei o respecta peste tot.
 *
 * `standard` (albastru 500-700) si `silver` (ink-soft -> ink) sunt fundaluri
 * inchise, deci raman pe alb.
 */
export const TON_STIL_CARD: Record<StilCard, "deschis" | "inchis"> = {
  standard: "deschis",
  silver: "deschis",
  gold: "inchis",
};

/**
 * Cum se coloreaza sigla ca sa se vada pe card.
 *
 * `logo.png` e semnul albastru al bancii, pe fundal transparent. Pus asa cum e,
 * pe cardul standard (gradient albastru) ar fi aproape invizibil — albastru pe
 * albastru. Semnul e plat, dintr-o singura culoare, deci aplatizarea la o
 * singura nuanta nu pierde nimic din el:
 *
 *   `brightness(0)` duce orice pixel la negru; `invert(1)` de dupa il face alb.
 *   Pe fundal deschis (gold) ne oprim la negru.
 *
 * Asa nu e nevoie de un al doilea fisier de sigla, care oricum ar fi trebuit
 * tinut in sincron cu primul.
 */
export const FILTRU_SIGLA_CARD: Record<StilCard, string> = {
  standard: "brightness(0) invert(1)",
  silver: "brightness(0) invert(1)",
  gold: "brightness(0)",
};

/**
 * Cipul auriu, desenat din tokeni.
 *
 * Pe cardurile inchise e auriu clasic; pe cel gold ar disparea in fundal, deci
 * se inchide la culoare.
 */
export const GRADIENT_CIP_CARD: Record<StilCard, string> = {
  standard:
    "linear-gradient(135deg, color-mix(in srgb, var(--color-warning) 70%, white) 0%, var(--color-warning) 50%, color-mix(in srgb, var(--color-warning) 70%, black) 100%)",
  silver:
    "linear-gradient(135deg, color-mix(in srgb, var(--color-warning) 70%, white) 0%, var(--color-warning) 50%, color-mix(in srgb, var(--color-warning) 70%, black) 100%)",
  gold: "linear-gradient(135deg, color-mix(in srgb, var(--color-ink) 55%, white) 0%, var(--color-ink) 60%, black 100%)",
};

/**
 * Culoarea inelului de focus, desenata INAUNTRUL cardului.
 *
 * Inelul albastru translucid de dinainte (`ring-primary-500/25`) statea in
 * afara conturului, peste fundalul paginii. Pe un card inclinat sau rotit in
 * carusel asta arata ca o pata: inelul e desenat plat, in planul ecranului, si
 * nu urmareste muchia cardului, deci se vede ca o umbra albastra scapata pe
 * langa el.
 *
 * Desenat pe dinauntru (`ring-inset`), inelul sta pe suprafata cardului si se
 * roteste odata cu ea. Culoarea urmeaza tonul, ca sa treaca pragul de 3:1 cerut
 * pentru elemente negrafice: alb pe fundal inchis, `ink` pe cardul gold.
 */
export const INEL_FOCUS_CARD: Record<StilCard, string> = {
  standard: "focus-visible:ring-white/90",
  silver: "focus-visible:ring-white/90",
  gold: "focus-visible:ring-ink/80",
};

/**
 * Holograma de pe spatele cardului.
 *
 * Un petic care isi schimba culoarea cu unghiul — pe un card adevarat e
 * elementul care se vede cel mai clar ca e 3D. Construita din tokenii marcii
 * (primary / warning / success), amestecati cu alb, ca sa nu intre hex-uri in
 * componenta (DESIGN.md #12).
 */
export const GRADIENT_HOLOGRAMA =
  "conic-gradient(from 210deg, " +
  "color-mix(in srgb, var(--color-primary-500) 65%, white), " +
  "color-mix(in srgb, var(--color-success) 55%, white), " +
  "color-mix(in srgb, var(--color-warning) 70%, white), " +
  "color-mix(in srgb, var(--color-danger) 55%, white), " +
  "color-mix(in srgb, var(--color-primary-500) 65%, white))";
