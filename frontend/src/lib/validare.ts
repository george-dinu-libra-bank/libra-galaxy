/**
 * Validari pentru formularele de autentificare.
 * Aceleasi reguli sunt aplicate si in baza de date (constraint-urile din
 * supabase/migrations/0001_profiles.sql), ca sa nu existe date invalide nici
 * daca cineva ocoleste interfata.
 */

export type Eroare = string | null;

/* -------------------------------------------------------------------------- */
/* Nume                                                                        */
/* -------------------------------------------------------------------------- */

export function validNume(valoare: string): Eroare {
  const nume = valoare.trim();

  if (!nume) return "Introdu numele complet.";
  if (nume.length < 3) return "Numele pare prea scurt.";
  if (nume.length > 120) return "Numele este prea lung.";
  if (!nume.includes(" ")) return "Scrie numele si prenumele.";
  if (!/^[A-Za-zĂÂÎȘȚăâîșț\s'-]+$/.test(nume))
    return "Numele poate contine doar litere, spatii, apostrof si cratima.";

  return null;
}

/* -------------------------------------------------------------------------- */
/* CNP                                                                         */
/* -------------------------------------------------------------------------- */

const PONDERI_CNP = [2, 7, 9, 1, 4, 6, 3, 5, 8, 2, 7, 9];

/** Verifica lungimea, data nasterii si cifra de control. */
export function validCnp(valoare: string): Eroare {
  const cnp = valoare.replace(/\s+/g, "");

  if (!cnp) return "Introdu CNP-ul.";
  if (!/^[0-9]{13}$/.test(cnp)) return "CNP-ul trebuie sa aiba exact 13 cifre.";
  if (!/^[1-8]/.test(cnp)) return "Prima cifra a CNP-ului nu este valida.";

  const luna = Number(cnp.slice(3, 5));
  const zi = Number(cnp.slice(5, 7));
  if (luna < 1 || luna > 12) return "Luna din CNP nu este valida.";
  if (zi < 1 || zi > 31) return "Ziua din CNP nu este valida.";

  const judet = Number(cnp.slice(7, 9));
  if (judet < 1 || judet > 52) return "Codul de judet din CNP nu este valid.";

  const suma = PONDERI_CNP.reduce(
    (acc, pondere, i) => acc + pondere * Number(cnp[i]),
    0,
  );
  const rest = suma % 11;
  const control = rest === 10 ? 1 : rest;

  if (control !== Number(cnp[12])) return "CNP-ul nu este valid.";

  return null;
}

/* -------------------------------------------------------------------------- */
/* Telefon                                                                     */
/* -------------------------------------------------------------------------- */

/** Accepta 07xxxxxxxx, 00407..., +407... si normalizeaza la +407xxxxxxxx. */
export function normalizeazaTelefon(valoare: string): string {
  let tel = valoare.replace(/[^\d+]/g, "");

  if (tel.startsWith("00")) tel = `+${tel.slice(2)}`;
  if (/^0[0-9]{9}$/.test(tel)) tel = `+4${tel}`;
  if (/^40[0-9]{9}$/.test(tel)) tel = `+${tel}`;

  return tel;
}

export function validTelefon(valoare: string): Eroare {
  if (!valoare.trim()) return "Introdu numarul de telefon.";

  const tel = normalizeazaTelefon(valoare);

  if (!/^\+40[0-9]{9}$/.test(tel))
    return "Numarul trebuie sa fie romanesc, de forma 07xx xxx xxx.";
  if (!/^\+407/.test(tel)) return "Introdu un numar de telefon mobil.";

  return null;
}

/* -------------------------------------------------------------------------- */
/* Email                                                                       */
/* -------------------------------------------------------------------------- */

export function validEmail(valoare: string): Eroare {
  const email = valoare.trim();

  if (!email) return "Introdu adresa de email.";
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/.test(email))
    return "Adresa de email nu pare corecta.";

  return null;
}

/* -------------------------------------------------------------------------- */
/* Parola                                                                      */
/* -------------------------------------------------------------------------- */

export function validParola(valoare: string): Eroare {
  if (!valoare) return "Alege o parola.";
  if (valoare.length < 8) return "Parola trebuie sa aiba cel putin 8 caractere.";
  if (!/[a-z]/.test(valoare)) return "Adauga cel putin o litera mica.";
  if (!/[A-Z]/.test(valoare)) return "Adauga cel putin o litera mare.";
  if (!/[0-9]/.test(valoare)) return "Adauga cel putin o cifra.";

  return null;
}

/** 0-4, pentru indicatorul vizual de sub campul de parola. */
export function putereParola(valoare: string): number {
  let scor = 0;

  if (valoare.length >= 8) scor++;
  if (valoare.length >= 12) scor++;
  if (/[A-Z]/.test(valoare) && /[a-z]/.test(valoare)) scor++;
  if (/[0-9]/.test(valoare) && /[^A-Za-z0-9]/.test(valoare)) scor++;

  return Math.min(scor, 4);
}
