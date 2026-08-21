"use client";

import { useEffect, useRef, useState, useTransition } from "react";
import Link from "next/link";
import { Info } from "lucide-react";
import { Banda } from "@/components/ui/banda";
import { simuleazaCredit } from "@/lib/actions/credite";
import type { ProdusCredit, Simulare } from "@/lib/data/credite";
import { formateazaSuma } from "@/lib/utils";

/**
 * Calculatorul de rată. Nu creează nimic în baza de date — de aceea nu cere
 * date despre venit și nu are nevoie de consimțământ.
 *
 * Calculul se face pe server, nu în browser, deși formula ar încăpea în zece
 * linii de JavaScript. Motivul e că ar deveni a doua implementare a
 * amortizării, iar cele două ar diverge la prima rotunjire — exact ce previne
 * REGULI.md #2. Rata pe care o vede clientul aici e cea pe care o va semna.
 */

const PAS_SUMA = 1000;
const INTARZIERE_MS = 250;

export function Simulator({ produs }: { produs: ProdusCredit }) {
  const [suma, setSuma] = useState(() => rotunjit(produs.sumaMin + (produs.sumaMax - produs.sumaMin) / 6));
  const [luni, setLuni] = useState(36);
  const [simulare, setSimulare] = useState<Simulare | null>(null);
  const [eroare, setEroare] = useState<string | null>(null);
  const [seIncarca, startTransition] = useTransition();

  // Ultima cerere trimisă câștigă: fără asta, un răspuns întârziat pentru o
  // sumă veche ar putea suprascrie rezultatul celei curente.
  const cerereCurenta = useRef(0);

  useEffect(() => {
    const temporizator = setTimeout(() => {
      const aceasta = ++cerereCurenta.current;
      startTransition(async () => {
        const rezultat = await simuleazaCredit(suma, luni);
        if (aceasta !== cerereCurenta.current) return;
        if (rezultat.eroare) {
          setEroare(rezultat.eroare);
          return;
        }
        setEroare(null);
        setSimulare(rezultat.simulare ?? null);
      });
    }, INTARZIERE_MS);

    return () => clearTimeout(temporizator);
  }, [suma, luni]);

  return (
    <div className="mt-6 space-y-5">
      <section className="rounded-card bg-surface p-5 shadow-sm">
        <Cursor
          eticheta="Suma"
          valoare={suma}
          afisare={formateazaSuma(suma)}
          min={produs.sumaMin}
          max={produs.sumaMax}
          pas={PAS_SUMA}
          onChange={setSuma}
          capete={[formateazaSuma(produs.sumaMin), formateazaSuma(produs.sumaMax)]}
        />

        <div className="mt-6">
          <Cursor
            eticheta="Perioadă"
            valoare={luni}
            afisare={`${luni} luni`}
            min={produs.luniMin}
            max={produs.luniMax}
            pas={6}
            onChange={setLuni}
            capete={[`${produs.luniMin} luni`, `${produs.luniMax} luni`]}
          />
        </div>
      </section>

      {eroare ? <Banda ton="eroare">{eroare}</Banda> : null}

      <section
        className="rounded-card bg-surface p-5 shadow-sm"
        aria-busy={seIncarca || undefined}
      >
        <p className="text-[13px] text-ink-faint">Rata lunară estimată</p>
        <p className="tabular mt-1 text-[30px] font-bold leading-[36px] text-ink">
          {simulare ? formateazaSuma(simulare.rataLunara) : "—"}
        </p>

        <dl className="mt-5 space-y-2 border-t border-line pt-4">
          <Rand eticheta="Dobândă fixă" valoare={procent(produs.dobandaAnuala)} />
          <Rand eticheta="DAE" valoare={simulare ? procent(simulare.dae) : "—"} />
          <Rand
            eticheta="Total de plată"
            valoare={simulare ? formateazaSuma(simulare.totalPlatit) : "—"}
          />
          <Rand
            eticheta="Cost total al creditului"
            valoare={simulare ? formateazaSuma(simulare.costTotal) : "—"}
          />
        </dl>
      </section>

      <div className="flex items-start gap-2 px-1 text-[13px] leading-[19px] text-ink-faint">
        <Info size={16} strokeWidth={1.75} aria-hidden className="mt-0.5 shrink-0" />
        <p>
          Simularea e informativă. Rata finală se stabilește după verificarea
          veniturilor și a gradului de îndatorare — îndeplinirea criteriilor
          minime nu garantează aprobarea.
        </p>
      </div>

      {/* Suma si perioada pleaca in URL, ca omul sa nu le retasteze in wizard. */}
      <Link
        href={`/credite/cerere?suma=${suma}&luni=${luni}`}
        className="flex h-12 w-full items-center justify-center rounded-field bg-primary-600 text-[15px] font-semibold text-white shadow-btn transition-[transform,box-shadow] duration-[180ms] ease-soft hover:shadow-md active:scale-[0.99] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
      >
        Continuă cu cererea
      </Link>
    </div>
  );
}

function Cursor({
  eticheta,
  valoare,
  afisare,
  min,
  max,
  pas,
  onChange,
  capete,
}: {
  eticheta: string;
  valoare: number;
  afisare: string;
  min: number;
  max: number;
  pas: number;
  onChange: (valoare: number) => void;
  capete: [string, string];
}) {
  return (
    <div>
      <div className="flex items-baseline justify-between">
        <label className="text-[13px] text-ink-faint" htmlFor={`cursor-${eticheta}`}>
          {eticheta}
        </label>
        <span className="tabular text-[17px] font-semibold text-ink">{afisare}</span>
      </div>

      <input
        id={`cursor-${eticheta}`}
        type="range"
        min={min}
        max={max}
        step={pas}
        value={valoare}
        onChange={(eveniment) => onChange(Number(eveniment.target.value))}
        className="mt-3 h-2 w-full cursor-pointer appearance-none rounded-full bg-muted accent-primary-600 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
      />

      <div className="mt-1.5 flex justify-between text-[11px] text-ink-faint">
        <span>{capete[0]}</span>
        <span>{capete[1]}</span>
      </div>
    </div>
  );
}

function Rand({ eticheta, valoare }: { eticheta: string; valoare: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4">
      <dt className="text-[13px] text-ink-soft">{eticheta}</dt>
      <dd className="tabular text-[15px] font-medium text-ink">{valoare}</dd>
    </div>
  );
}

function procent(fractie: number) {
  return `${(fractie * 100).toFixed(2).replace(".", ",")}%`;
}

function rotunjit(valoare: number) {
  return Math.round(valoare / PAS_SUMA) * PAS_SUMA;
}
