/**
 * Ruleaza cu runnerul din Node, fara nicio dependenta noua:
 *
 *   docker compose exec frontend node --test --experimental-strip-types \
 *     src/lib/scanare-cuvinte.test.ts
 *
 * Ce se testeaza sunt cele doua feluri in care scanerul poate gresi si le-ar
 * simti oamenii: sa scape un transfer scris cu diacritice, cifre in loc de
 * litere sau o litera gresita — si, la fel de rau, sa opreasca un transfer
 * curat fiindca un cuvant scurt seamana vag cu altul.
 */

import assert from "node:assert/strict";
import { test } from "node:test";

import { gasesteCuvinteSensibile, normalizeazaText } from "./scanare-cuvinte.ts";

const LISTA = ["spalare de bani", "droguri", "mita", "arme", "cocaina"];

test("normalizarea taie diacriticele si punctuatia, dar lasa cifrele in pace", () => {
  assert.equal(normalizeazaText("MITĂ, urgent!"), "mita urgent");
  assert.equal(normalizeazaText("Am trimis 500 pentru chirie"), "am trimis 500 pentru chirie");
});

test("prinde cuvantul scris normal, oricum ar fi scris", () => {
  assert.deepEqual(gasesteCuvinteSensibile("Pentru MITĂ.", LISTA), ["mita"]);
  assert.deepEqual(gasesteCuvinteSensibile("bani de droguri", LISTA), ["droguri"]);
});

test("prinde cifrele puse in locul literelor", () => {
  assert.deepEqual(gasesteCuvinteSensibile("plata pentru c0c4ina", LISTA), ["cocaina"]);
});

test("prinde radacina si greselile mici de scriere", () => {
  assert.deepEqual(gasesteCuvinteSensibile("pentru drogurile lui", LISTA), ["droguri"]);
  assert.deepEqual(gasesteCuvinteSensibile("plata drogurii", LISTA), ["droguri"]);
  assert.deepEqual(gasesteCuvinteSensibile("cumparare armele vechi", LISTA), ["arme"]);
});

test("expresia se cauta intreaga, la granita de cuvant", () => {
  assert.deepEqual(gasesteCuvinteSensibile("ajutor la spălare de bani", LISTA), [
    "spalare de bani",
  ]);
  // „de bani" exista, „spalare" nu — expresia nu se potriveste pe bucati.
  assert.deepEqual(gasesteCuvinteSensibile("transfer de bani catre Ana", LISTA), []);
});

test("nu opreste transferuri curate", () => {
  assert.deepEqual(gasesteCuvinteSensibile("Chirie august", LISTA), []);
  // Cuvintele scurte nu tolereaza nicio litera schimbata: „mita" / „mira".
  assert.deepEqual(gasesteCuvinteSensibile("mira de la fereastra", LISTA), []);
  // Radacina, nu orice subsir: „arme" nu are ce cauta in „farmec".
  assert.deepEqual(gasesteCuvinteSensibile("plata la farmecul serii", LISTA), []);
});

test("intoarce toate cuvintele gasite, in forma din lista", () => {
  assert.deepEqual(gasesteCuvinteSensibile("droguri si arme", LISTA), ["droguri", "arme"]);
});
