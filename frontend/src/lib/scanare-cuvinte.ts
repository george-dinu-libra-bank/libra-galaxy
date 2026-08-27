/**
 * Potrivirea unui text cu lista de cuvinte sensibile.
 *
 * Fisierul nu stie nimic despre Supabase, Next sau cache: numai text si
 * comparatii. De aceea poate fi rulat direct de runnerul din Node
 * (scanare-cuvinte.test.ts), fara nicio dependenta.
 *
 * Potrivirea nu e „egal". Cine trimite bani pentru ceva ce nu se cade nu scrie
 * cuvantul curat: scrie „sp4lare", „drogurii", „MITĂ.". Asa ca se compara forme
 * normalizate si se accepta o mica distanta de editare.
 */

/** Cifrele si semnele puse in locul literelor, aduse inapoi la litere. */
const SUBSTITUIRI: Record<string, string> = {
  "0": "o",
  "1": "i",
  "3": "e",
  "4": "a",
  "5": "s",
  "7": "t",
  "8": "b",
  "@": "a",
  $: "s",
};

/**
 * Aduce un text la forma dupa care se compara: fara diacritice, fara majuscule,
 * fara semne de punctuatie, cu cifrele-litera intoarse la litere.
 *
 * „Pentru SPĂ_LARE de b4ni!!" -> „pentru spa lare de bani"
 *
 * Substituirile se fac doar in bucatile care au si litere: „500" trebuie sa
 * ramana „500", nu sa devina „soo" si sa inceapa sa semene cu vreun cuvant.
 */
export function normalizeazaText(text: string): string {
  const curatat = text
    .normalize("NFD")
    // Semnele diacritice raman caractere separate dupa NFD; se sterg.
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9@$]+/g, " ")
    .trim();

  return curatat
    .split(" ")
    .filter(Boolean)
    .map((bucata) =>
      /[a-z]/.test(bucata)
        ? bucata.replace(/[0134578@$]/g, (caracter) => SUBSTITUIRI[caracter] ?? caracter)
        : bucata,
    )
    .join(" ");
}

/**
 * Distanta de editare, oprita cat mai devreme.
 *
 * `maxim` taie calculul: nu ne intereseaza cat de departe sunt doua cuvinte
 * complet diferite, doar daca sunt suficient de aproape.
 */
function distantaEditare(a: string, b: string, maxim: number): number {
  if (Math.abs(a.length - b.length) > maxim) return maxim + 1;

  let anterior = Array.from({ length: b.length + 1 }, (_, i) => i);

  for (let i = 1; i <= a.length; i++) {
    const curent = [i];
    let minimPeRand = i;

    for (let j = 1; j <= b.length; j++) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      const valoare = Math.min(
        anterior[j] + 1, // stergere
        curent[j - 1] + 1, // inserare
        anterior[j - 1] + cost, // inlocuire
      );
      curent.push(valoare);
      if (valoare < minimPeRand) minimPeRand = valoare;
    }

    // Tot randul e deja peste prag; de aici incolo nu mai are cum sa scada.
    if (minimPeRand > maxim) return maxim + 1;
    anterior = curent;
  }

  return anterior[b.length];
}

/** Cate greseli de scriere se iarta, dupa cat de lung e cuvantul cautat. */
function pragToleranta(lungime: number): number {
  if (lungime >= 8) return 2;
  if (lungime >= 5) return 1;
  // Sub 5 litere, o litera schimbata face deja alt cuvant: „arme" / „arme"
  // versus „arte". Toleranta ar produce mai multe alarme false decat prinderi.
  return 0;
}

/**
 * Cuvintele din lista care se regasesc in text, in forma lor originala.
 *
 * Trei feluri de potrivire, in ordinea increderii:
 *   - expresie („spalare de bani"): se cauta ca atare, la granita de cuvant;
 *   - cuvant care apare intreg sau ca radacina intr-un cuvant din text
 *     („drog" in „drogurile");
 *   - cuvant scris gresit, la cel mult una-doua litere distanta.
 */
export function gasesteCuvinteSensibile(text: string, cuvinte: string[]): string[] {
  const normalizat = normalizeazaText(text ?? "");
  if (!normalizat) return [];

  const bucati = normalizat.split(" ").filter(Boolean);
  const gasite: string[] = [];

  for (const original of cuvinte) {
    const cautat = normalizeazaText(original);
    if (!cautat) continue;

    // Expresiile se cauta ca subsir; spatiile din jur tin potrivirea la granita
    // de cuvant, ca „de bani" sa nu prinda „bordani".
    if (cautat.includes(" ")) {
      if (` ${normalizat} `.includes(` ${cautat} `)) gasite.push(original);
      continue;
    }

    const prag = pragToleranta(cautat.length);

    const potriveste = bucati.some(
      (bucata) =>
        bucata === cautat ||
        // Radacina, nu orice subsir: „arme" nu trebuie sa prinda „farmec".
        (cautat.length >= 4 && bucata.startsWith(cautat)) ||
        (prag > 0 && distantaEditare(bucata, cautat, prag) <= prag),
    );

    if (potriveste) gasite.push(original);
  }

  return gasite;
}
