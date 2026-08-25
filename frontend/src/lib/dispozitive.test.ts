/**
 * Ruleaza cu runnerul din Node, fara nicio dependenta noua:
 *
 *   docker compose exec frontend node --test --experimental-strip-types \
 *     src/lib/dispozitive.test.ts
 *
 * Ce se testeaza e ORDINEA regulilor din dispozitive.ts, singurul lucru care
 * se poate strica: fiecare UA de browser e facut intentionat sa semene cu al
 * altora, deci "contine Chrome" nu inseamna Chrome.
 */

import assert from "node:assert/strict";
import { test } from "node:test";

import { descrieDispozitiv } from "./dispozitive.ts";

const UA = {
  chromeWindows:
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
  edgeWindows:
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0",
  safariIphone:
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
  // iPadOS in mod "site pentru desktop" — se da drept Macintosh.
  safariIpadDesktop:
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
  safariIpad:
    "Mozilla/5.0 (iPad; CPU OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
  firefoxLinux: "Mozilla/5.0 (X11; Linux x86_64; rv:129.0) Gecko/20100101 Firefox/129.0",
  chromeAndroid:
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Mobile Safari/537.36",
} as const;

test("Chrome pe Windows", () => {
  const d = descrieDispozitiv({ agentUtilizator: UA.chromeWindows });

  assert.equal(d.eticheta, "Chrome pe Windows");
  assert.equal(d.mobil, false);
  assert.equal(d.amprenta, "chrome|windows|desktop");
});

test("Edge nu se raporteaza ca Chrome", () => {
  // UA-ul lui Edge contine si "Chrome/", si "Safari/".
  const d = descrieDispozitiv({ agentUtilizator: UA.edgeWindows });

  assert.equal(d.browser, "Edge");
  assert.equal(d.eticheta, "Edge pe Windows");
});

test("Chrome nu se raporteaza ca Safari", () => {
  assert.equal(descrieDispozitiv({ agentUtilizator: UA.chromeWindows }).browser, "Chrome");
});

test("Safari pe iPhone e mobil", () => {
  const d = descrieDispozitiv({ agentUtilizator: UA.safariIphone });

  assert.equal(d.eticheta, "Safari pe iPhone");
  assert.equal(d.mobil, true);
  assert.equal(d.amprenta, "safari|iphone|mobil");
});

test("iPad-ul se recunoaste inaintea lui Macintosh", () => {
  assert.equal(descrieDispozitiv({ agentUtilizator: UA.safariIpad }).sistem, "iPad");
});

test("iPad in mod desktop arata ca macOS — limitare cunoscuta a UA-ului", () => {
  // Nu e o scapare, e tot ce trimite iPadOS. Testul fixeaza comportamentul, ca
  // sa nu para o regresie cand il observa cineva.
  assert.equal(descrieDispozitiv({ agentUtilizator: UA.safariIpadDesktop }).sistem, "macOS");
});

test("Firefox pe Linux", () => {
  const d = descrieDispozitiv({ agentUtilizator: UA.firefoxLinux });

  assert.equal(d.eticheta, "Firefox pe Linux");
  assert.equal(d.mobil, false);
});

test("Chrome pe Android e mobil", () => {
  const d = descrieDispozitiv({ agentUtilizator: UA.chromeAndroid });

  assert.equal(d.eticheta, "Chrome pe Android");
  assert.equal(d.mobil, true);
});

test("client hints bat regexul", () => {
  const d = descrieDispozitiv({
    agentUtilizator: UA.chromeWindows,
    platformaHint: '"macOS"',
  });

  assert.equal(d.sistem, "macOS");
});

test("sec-ch-ua-mobile ?0 bate 'Mobile' din UA", () => {
  const d = descrieDispozitiv({ agentUtilizator: UA.chromeAndroid, mobilHint: "?0" });

  assert.equal(d.mobil, false);
});

test("amprenta nu contine versiuni, deci nu se schimba la update de browser", () => {
  const vechi = descrieDispozitiv({ agentUtilizator: UA.chromeWindows });
  const nou = descrieDispozitiv({
    agentUtilizator: UA.chromeWindows.replace("140.0.0.0", "141.0.0.0"),
  });

  assert.equal(vechi.amprenta, nou.amprenta);
});

test("UA lipsa sau gunoi nu produce 'Necunoscut pe Necunoscut'", () => {
  for (const agentUtilizator of [null, undefined, "", "aiurea"]) {
    assert.equal(descrieDispozitiv({ agentUtilizator }).eticheta, "Dispozitiv necunoscut");
  }
});
