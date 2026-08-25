import Link from "next/link";
import { ChevronLeft } from "lucide-react";
import { Banda } from "@/components/ui/banda";
import { cereAdmin } from "@/lib/admin";
import { BackendError } from "@/lib/backend";
import { obtineObservabilitateAi } from "@/lib/data/admin-credite";
import type { EtapaSpec, ObservabilitateAi, RezumatZilnicEtapa } from "@/lib/tipuri-admin";
import { cn } from "@/lib/utils";

const ETICHETA_ETAPA: Record<string, string> = {
  documente: "Documente",
  coerenta: "Coerență",
  brief: "Brief",
  explicatie: "Explicație",
};

export default async function ObservabilitatePipelineAiPage() {
  const admin = await cereAdmin();

  let date: ObservabilitateAi | null = null;
  let eroare: string | null = null;
  try {
    date = await obtineObservabilitateAi(admin.token);
  } catch (exc) {
    eroare =
      exc instanceof BackendError
        ? exc.message
        : "Nu am putut încărca datele. Verifică dacă backendul răspunde.";
  }

  return (
    <div className="flex flex-col gap-6">
      <Link
        href="/admin/credite"
        className="inline-flex w-fit items-center gap-1.5 text-[13px] font-semibold text-primary-600 hover:underline"
      >
        <ChevronLeft size={16} strokeWidth={2} aria-hidden />
        Înapoi la credite
      </Link>

      <div>
        <h1 className="text-[26px] font-bold leading-8 tracking-[-0.02em] text-ink">Pipeline AI</h1>
        <p className="mt-1.5 text-[15px] leading-[22px] text-ink-soft">
          Observații consultative pentru dosarele de credit — nu ating scorul și nu decid nimic.
        </p>
      </div>

      {eroare ? <Banda ton="eroare">{eroare}</Banda> : null}

      {date ? (
        <>
          <Cifre date={date} />
          <RezumatEtape rezumat={date.rezumat_zilnic} />
          <DocumentatieEtape etape={date.etape} />
        </>
      ) : null}
    </div>
  );
}

function Cifre({ date }: { date: ObservabilitateAi }) {
  const { rata_acord, cost_estimat_usd_30_zile } = date;

  return (
    <section className="grid grid-cols-2 gap-3 sm:grid-cols-3">
      <Cifra
        eticheta="Acord AI vs. decizia omului"
        valoare={rata_acord.rata === null ? "—" : `${Math.round(rata_acord.rata * 100)}%`}
        subtitlu={
          rata_acord.total_comparabile > 0
            ? `${rata_acord.de_acord} din ${rata_acord.total_comparabile} cazuri`
            : "încă niciun caz comparabil"
        }
      />
      <Cifra
        eticheta="Cost estimat"
        valoare={`$${cost_estimat_usd_30_zile.toFixed(4)}`}
        subtitlu="ultimele 30 de zile"
      />
      <Cifra
        eticheta="Etape monitorizate"
        valoare={String(date.etape.length)}
        subtitlu="documente, coerență, brief, explicație"
      />
    </section>
  );
}

function Cifra({ eticheta, valoare, subtitlu }: { eticheta: string; valoare: string; subtitlu?: string }) {
  return (
    <div className="rounded-card border border-line bg-surface p-4">
      <p className="text-[12px] text-ink-faint">{eticheta}</p>
      <p className="mt-1 text-[18px] font-bold tabular text-ink">{valoare}</p>
      {subtitlu ? <p className="text-[11.5px] text-ink-faint">{subtitlu}</p> : null}
    </div>
  );
}

/**
 * Randuri per (zi, etapa) — 'coerenta' ar trebui sa fie mereu 100% reusita,
 * fiindca e determinista: orice esec acolo e un bug, nu un raspuns rau de la
 * Foundry.
 */
function RezumatEtape({ rezumat }: { rezumat: RezumatZilnicEtapa[] }) {
  if (rezumat.length === 0) {
    return (
      <section className="rounded-card border border-dashed border-line bg-surface p-8 text-center">
        <p className="text-[13px] leading-[19px] text-ink-faint">
          Pipeline-ul n-a rulat încă în ultimele 30 de zile.
        </p>
      </section>
    );
  }

  return (
    <section className="rounded-card border border-line bg-surface p-5">
      <h2 className="text-[15px] font-semibold text-ink">Rulări pe etapă, pe zi</h2>
      <div className="mt-3 overflow-x-auto">
        <table className="w-full min-w-[560px] border-collapse text-[12.5px]">
          <thead>
            <tr className="border-b border-line text-left text-ink-faint">
              <th className="py-2 pr-3 font-medium">Zi</th>
              <th className="py-2 pr-3 font-medium">Etapă</th>
              <th className="py-2 pr-3 text-right font-medium">Reușite</th>
              <th className="py-2 pr-3 text-right font-medium">Eșuate</th>
              <th className="py-2 pr-3 text-right font-medium">Sărite</th>
              <th className="py-2 pr-3 text-right font-medium">Latență medie</th>
              <th className="py-2 text-right font-medium">Tokeni (in/out)</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {rezumat.map((rand) => (
              <tr key={`${rand.zi}-${rand.etapa}`}>
                <td className="py-2 pr-3 tabular text-ink-soft">{rand.zi}</td>
                <td className="py-2 pr-3 font-medium text-ink">
                  {ETICHETA_ETAPA[rand.etapa] ?? rand.etapa}
                </td>
                <td className="py-2 pr-3 text-right tabular text-ink">{rand.reusite}</td>
                <td
                  className={cn(
                    "py-2 pr-3 text-right tabular",
                    rand.esuate > 0 ? "font-semibold text-danger" : "text-ink-faint",
                  )}
                >
                  {rand.esuate}
                </td>
                <td className="py-2 pr-3 text-right tabular text-ink-faint">{rand.sarite}</td>
                <td className="py-2 pr-3 text-right tabular text-ink-soft">
                  {rand.latenta_medie_ms === null ? "—" : `${rand.latenta_medie_ms} ms`}
                </td>
                <td className="py-2 text-right tabular text-ink-soft">
                  {rand.tokeni_intrare} / {rand.tokeni_iesire}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

/** Documentatie executabila — acelasi obiect din app/credit/ai/contracte.py. */
function DocumentatieEtape({ etape }: { etape: EtapaSpec[] }) {
  return (
    <section className="rounded-card border border-line bg-surface p-5">
      <h2 className="text-[15px] font-semibold text-ink">Cele patru etape</h2>
      <div className="mt-3 flex flex-col divide-y divide-line">
        {etape.map((etapa) => (
          <div key={etapa.id} className="py-3 first:pt-0 last:pb-0">
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-[13.5px] font-semibold text-ink">
                {ETICHETA_ETAPA[etapa.id] ?? etapa.id}
              </p>
              <span
                className={cn(
                  "rounded-full px-2 py-0.5 text-[11px] font-medium",
                  etapa.are_nevoie_de_model
                    ? "bg-primary-50 text-primary-700"
                    : "bg-muted text-ink-faint",
                )}
              >
                {etapa.are_nevoie_de_model ? "cu model" : "determinist"}
              </span>
              {etapa.versiune_prompt ? (
                <span className="text-[11px] text-ink-faint">{etapa.versiune_prompt}</span>
              ) : null}
            </div>
            <p className="mt-1 text-[13px] leading-[19px] text-ink-soft">{etapa.scop}</p>
            {etapa.interzis.length > 0 ? (
              <ul className="mt-1.5 flex flex-col gap-0.5">
                {etapa.interzis.map((element, indice) => (
                  <li key={indice} className="text-[12px] leading-[17px] text-ink-faint">
                    Nu are voie: {element}
                  </li>
                ))}
              </ul>
            ) : null}

            {/*
              Promptul vine din prompturi.py prin API, nu copiat aici: o copie
              ar diverge de ce se trimite efectiv modelului. Pliat, fiindca e
              lung si rar consultat — dar la un click distanta, nu doar in cod.
            */}
            {etapa.prompt_sistem ? (
              <details className="group mt-2.5">
                <summary className="w-fit cursor-pointer list-none text-[12px] font-medium text-primary-600 hover:underline">
                  <span className="group-open:hidden">Vezi promptul trimis modelului</span>
                  <span className="hidden group-open:inline">Ascunde promptul</span>
                </summary>
                <pre className="mt-2 max-h-80 overflow-auto whitespace-pre-wrap rounded-field bg-muted p-3 text-[12px] leading-[17px] text-ink-soft">
                  {etapa.prompt_sistem}
                </pre>
              </details>
            ) : (
              <p className="mt-2.5 text-[12px] text-ink-faint">
                Fără prompt — etapa e deterministă, nu trimite nimic unui model.
              </p>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}

export const dynamic = "force-dynamic";
