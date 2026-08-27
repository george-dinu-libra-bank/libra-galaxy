/**
 * Ruleaza cu runnerul din Node, fara nicio dependenta noua:
 *
 *   docker compose exec frontend node --test --experimental-strip-types \
 *     src/lib/qr-plata.test.ts
 *
 * Ce se testeaza e dus-intorsul: ce pune in link ecranul care CERE banii trebuie
 * sa citeasca la fel ecranul care ii TRIMITE. Cele doua capete sunt scrise in
 * fisiere diferite si rulate in locuri diferite (browser si server), deci nimic
 * nu le tine sincronizate in afara de testul asta.
 */

import assert from "node:assert/strict";
import { test } from "node:test";

import { citesteCerereDePlata, construiesteLinkPlata } from "./qr-plata.ts";

const IBAN = "RO49LIBR1B31007593840000";
const ORIGINE = "https://galaxy.bank";

/** Parametrii unui link, asa cum ii vede pagina de transfer. */
function paramsDin(link: string) {
  return Object.fromEntries(new URL(link).searchParams);
}

test("linkul duce catre ecranul de transfer, cu cele trei date", () => {
  const link = construiesteLinkPlata(ORIGINE, {
    iban: IBAN,
    suma: 123.4,
    detalii: "Chirie august",
  });

  assert.equal(new URL(link).pathname, "/transfer");
  assert.deepEqual(paramsDin(link), {
    iban: IBAN,
    suma: "123.40",
    detalii: "Chirie august",
  });
});

test("ce se scrie in link se citeste inapoi identic", () => {
  const cerere = { iban: IBAN, suma: 99.99, detalii: "Cadou pentru Ana" };
  const link = construiesteLinkPlata(ORIGINE, cerere);

  assert.deepEqual(citesteCerereDePlata(paramsDin(link)), cerere);
});

test("suma si motivul sunt optionale", () => {
  const link = construiesteLinkPlata(ORIGINE, { iban: IBAN, suma: null, detalii: null });

  assert.deepEqual(paramsDin(link), { iban: IBAN });
  assert.deepEqual(citesteCerereDePlata(paramsDin(link)), {
    iban: IBAN,
    suma: null,
    detalii: null,
  });
});

test("IBAN-ul se normalizeaza la scriere si la citire", () => {
  const link = construiesteLinkPlata(ORIGINE, {
    iban: "ro49 libr 1b31 0075 9384 0000",
    suma: null,
    detalii: null,
  });

  assert.equal(paramsDin(link).iban, IBAN);
  assert.equal(citesteCerereDePlata({ iban: "ro49 libr 1b31 0075 9384 0000" })?.iban, IBAN);
});

test("un link fara IBAN bun nu produce nicio cerere", () => {
  assert.equal(citesteCerereDePlata({}), null);
  assert.equal(citesteCerereDePlata({ iban: "RO49" }), null);
  assert.equal(citesteCerereDePlata({ iban: "DE89370400440532013000" }), null);
});

test("o suma aiurea din URL se ignora, nu strica ecranul", () => {
  for (const suma of ["abc", "-5", "0"]) {
    assert.equal(citesteCerereDePlata({ iban: IBAN, suma })?.suma, null, `suma=${suma}`);
  }

  // Scrisa cu virgula, cum ar putea-o edita cineva de mana in bara de adrese.
  assert.equal(citesteCerereDePlata({ iban: IBAN, suma: "12,50" })?.suma, 12.5);
});

test("origine cu slash la final nu produce doua slash-uri", () => {
  const link = construiesteLinkPlata("https://galaxy.bank/", { iban: IBAN, suma: null, detalii: null });
  assert.ok(link.startsWith("https://galaxy.bank/transfer?"), link);
});
