"use client";

import CountUp from "@/components/reactbits/CountUp";
import { useMiscareRedusa } from "@/hooks/use-miscare-redusa";

/**
 * Cifrele descriu produsul asa cum e construit, nu promisiuni de marketing:
 * numarul de ecrane din aplicatie, straturile prin care trece o cerere pana la
 * baza de date (FastAPI -> serviciu -> repository, ARCHITECTURE.md 4.2) si
 * modulele functionale.
 */
const CIFRE = [
  { pana: 13, sufix: "", eticheta: "ecrane în aplicație" },
  { pana: 9, sufix: "", eticheta: "module: cont, transfer, credite, grupuri…" },
  { pana: 3, sufix: "", eticheta: "straturi între agent și baza de date" },
  { pana: 2, sufix: " min", eticheta: "de la înregistrare la IBAN activ" },
];

export function Cifre() {
  const miscareRedusa = useMiscareRedusa();

  return (
    <section className="mx-auto w-full max-w-6xl px-5 py-12 sm:px-8">
      <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {CIFRE.map((cifra) => (
          <div
            key={cifra.eticheta}
            className="rounded-card border border-line bg-surface p-5 shadow-sm"
          >
            <dt className="sr-only">{cifra.eticheta}</dt>
            <dd>
              <p className="tabular text-[32px] font-bold leading-[38px] tracking-[-0.02em] text-ink">
                {miscareRedusa ? (
                  <span>{cifra.pana}</span>
                ) : (
                  <CountUp to={cifra.pana} duration={1.2} separator="." />
                )}
                {cifra.sufix}
              </p>
              <p className="mt-1.5 text-[13px] leading-[19px] text-ink-soft">{cifra.eticheta}</p>
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
