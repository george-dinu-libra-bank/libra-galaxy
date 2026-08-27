/**
 * Legatura dintre o notificare si lucrul despre care vorbeste.
 *
 * Notificarile care trimit undeva poarta id-ul tintei intr-un marcaj la finalul
 * mesajului. Tabela `notificari` e comuna intregii aplicatii, deci n-am largit-o
 * cu o coloana folosita de un singur flux; marcajul o lasa neatinsa si face
 * notificarea utilizabila, nu doar informativa.
 *
 * Traieste aici, nu in componenta, fiindca il citesc **doua** suprafete —
 * clopotelul din antet si cardul de mesaje de pe dashboard. Doua copii ar
 * diverge la primul retus (REGULI.md #2), iar divergenta s-ar vedea: una din
 * ele ar afisa clientului „[cerere:8bfa27ef-...]" in clar.
 *
 * Fisierul si-a pastrat numele desi acum acopera doua feluri de tinte: e
 * importat din mai multe locuri, iar o redenumire ar fi fost o schimbare mai
 * mare decat lucrul pe care il aduce.
 */

const MARCAJ_CERERE = /\n*\[cerere:([0-9a-f-]{36})\]\s*$/i;
const MARCAJ_INVESTIGATIE = /\n*\[investigatie:([0-9a-f-]{36})\]\s*$/i;

/** Id-ul cererii, daca notificarea e despre un dosar de credit. */
export function idCerereDinNotificare(mesaj: string): string | null {
  return MARCAJ_CERERE.exec(mesaj)?.[1] ?? null;
}

/** Id-ul investigatiei, daca notificarea e despre un fir deschis de banca. */
export function idInvestigatieDinNotificare(mesaj: string): string | null {
  return MARCAJ_INVESTIGATIE.exec(mesaj)?.[1] ?? null;
}

/** Mesajul asa cum trebuie citit de om, fara marcajul tehnic. */
export function textFaraMarcaj(mesaj: string): string {
  return mesaj.replace(MARCAJ_CERERE, "").replace(MARCAJ_INVESTIGATIE, "").trim();
}
