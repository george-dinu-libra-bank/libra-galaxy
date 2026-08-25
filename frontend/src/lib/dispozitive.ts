/**
 * Traduce un User-Agent in ceva ce poate citi un om: "Chrome pe Windows".
 *
 * Functie pura, fara dependente si fara nimic din `next/*` — se importa si din
 * server actions, si din componente, si se testeaza fara DOM (vezi
 * dispozitive.test.ts). Nu am adus un parser de UA din npm: avem nevoie de
 * browser + sistem + mobil/desktop, adica trei regexuri, nu de o baza de date
 * de dispozitive actualizata saptamanal.
 *
 * Cand browserul trimite client hints (Chromium le trimite implicit pe
 * contexte sigure, iar localhost se considera sigur), le credem pe ele:
 * `sec-ch-ua-platform` e browserul care declara sistemul, nu noi care il
 * ghicim dintr-un sir facut intentionat sa semene cu al altora.
 */

export type DescriereDispozitiv = {
  browser: string;
  sistem: string;
  mobil: boolean;
  /** Ce vede utilizatorul: "Chrome pe Windows". */
  eticheta: string;
  /** Cheia stabila din baza de date: "chrome|windows|desktop". */
  amprenta: string;
};

export type AnteteDispozitiv = {
  agentUtilizator: string | null | undefined;
  /** sec-ch-ua-platform, ex. `"Windows"` (cu ghilimele in antet). */
  platformaHint?: string | null;
  /** sec-ch-ua-mobile, `?1` pe mobil, `?0` altfel. */
  mobilHint?: string | null;
};

const NECUNOSCUT = "Necunoscut";

/**
 * Ordinea e singurul lucru care se poate strica aici, deci e explicita.
 *
 * Edge, Opera si Samsung Internet trebuie sa vina INAINTEA lui Chrome, iar
 * Chrome inaintea lui Safari: fiecare UA de Chromium contine si "Chrome", si
 * "Safari", tocmai ca sa nu fie respins de siteuri vechi. Prima potrivire
 * castiga, deci cel mai specific se pune primul.
 */
const BROWSERE: ReadonlyArray<readonly [RegExp, string]> = [
  [/\bEdgA?\//, "Edge"],
  [/\bOPR\/|\bOpera\b/, "Opera"],
  [/\bSamsungBrowser\//, "Samsung Internet"],
  [/\bFirefox\/|\bFxiOS\//, "Firefox"],
  [/\bChrome\/|\bCriOS\//, "Chrome"],
  [/\bSafari\//, "Safari"],
];

/**
 * iPad inaintea lui Macintosh: Safari pe iPad, in modul "site pentru desktop"
 * (implicit pe iPad de la iPadOS 13), trimite un UA de Macintosh. Fara ordinea
 * asta, fiecare iPad ar aparea in lista ca "macOS".
 */
const SISTEME: ReadonlyArray<readonly [RegExp, string]> = [
  [/\biPhone\b/, "iPhone"],
  [/\biPad\b/, "iPad"],
  [/\bAndroid\b/, "Android"],
  [/\bWindows\b/, "Windows"],
  [/\bMacintosh\b|\bMac OS X\b/, "macOS"],
  [/\bLinux\b|\bX11\b/, "Linux"],
];

/** sec-ch-ua-platform vine cu ghilimele: `"Windows"`. */
const PLATFORME_HINT: Readonly<Record<string, string>> = {
  windows: "Windows",
  macos: "macOS",
  android: "Android",
  linux: "Linux",
  ios: "iPhone",
  "chrome os": "Linux",
};

function potriveste(
  valoare: string,
  reguli: ReadonlyArray<readonly [RegExp, string]>,
): string {
  for (const [tipar, nume] of reguli) {
    if (tipar.test(valoare)) return nume;
  }
  return NECUNOSCUT;
}

function sistemDinHint(platformaHint: string | null | undefined): string | null {
  if (!platformaHint) return null;
  const curatat = platformaHint.replace(/"/g, "").trim().toLowerCase();
  return PLATFORME_HINT[curatat] ?? null;
}

export function descrieDispozitiv(antete: AnteteDispozitiv): DescriereDispozitiv {
  const agent = antete.agentUtilizator ?? "";

  const browser = potriveste(agent, BROWSERE);
  // Hintul bate regexul: e browserul care isi declara sistemul.
  const sistem = sistemDinHint(antete.platformaHint) ?? potriveste(agent, SISTEME);

  const mobil =
    antete.mobilHint === "?1" ||
    (antete.mobilHint !== "?0" && /\bMobile\b|\bAndroid\b|\biPhone\b/.test(agent));

  return {
    browser,
    sistem,
    mobil,
    eticheta: etichetaDin(browser, sistem),
    // Fara numere de versiune: altfel fiecare update minor de Chrome ar parea
    // un dispozitiv nou, la fiecare cateva saptamani.
    amprenta: `${browser}|${sistem}|${mobil ? "mobil" : "desktop"}`.toLowerCase(),
  };
}

/** "Necunoscut pe Necunoscut" nu se afiseaza niciodata — degradam pe rand. */
function etichetaDin(browser: string, sistem: string): string {
  if (browser !== NECUNOSCUT && sistem !== NECUNOSCUT) return `${browser} pe ${sistem}`;
  if (browser !== NECUNOSCUT) return browser;
  if (sistem !== NECUNOSCUT) return sistem;
  return "Dispozitiv necunoscut";
}
