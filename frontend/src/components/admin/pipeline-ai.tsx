"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { RefreshCw, Sparkles } from "lucide-react";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { ruleazaPipelineAi } from "@/lib/actions/admin-credite";
import {
  etichetaSemnal,
  lei,
  type DosarAi,
  type EtapaAi,
  type Recomandare,
  type SemnalAi,
} from "@/lib/tipuri-admin";
import { cn } from "@/lib/utils";

const STIL_SEVERITATE = {
  grav: "bg-danger/8 text-danger",
  atentie: "bg-warning/10 text-warning",
  informativ: "bg-muted text-ink-faint",
} as const;

const ETICHETA_SEVERITATE = {
  grav: "Grav",
  atentie: "Atenție",
  informativ: "Info",
} as const;

const ORDINE_SEVERITATE = { grav: 0, atentie: 1, informativ: 2 } as const;

const ETICHETA_RECOMANDARE: Record<Recomandare, string> = {
  aproba: "Recomandă aprobarea",
  respinge: "Recomandă respingerea",
  cere_document: "Recomandă cerere de document",
  fara_recomandare: "Fără recomandare clară",
};

type ExtractieDocument = {
  venit_net?: string | null;
  angajator?: string | null;
  incredere?: number;
  citate?: Record<string, string | null>;
};

type BriefRezultat = {
  rezumat?: string;
  riscuri?: string[];
  atenuari?: string[];
  intrebari_de_pus?: string[];
  recomandare?: Recomandare;
  incredere?: number;
};

/**
 * Panoul consultativ din dosarul cererii — semnalele de coerenta, ce a citit
 * modelul din document, si un brief pentru zona gri. Nimic de aici nu a
 * schimbat scorul: banda de mai jos o spune explicit, ca sa nu fie nevoie de
 * incredere oarba in ce vede analistul.
 */
export function PipelineAi({ idCerere, ai }: { idCerere: string; ai: DosarAi | null }) {
  const router = useRouter();
  const [seRuleaza, startTransition] = useTransition();
  const [eroare, setEroare] = useState<string | null>(null);

  function ruleazaDinNou() {
    setEroare(null);
    startTransition(async () => {
      const rezultat = await ruleazaPipelineAi(idCerere);
      if (rezultat.eroare) {
        setEroare(rezultat.eroare);
        return;
      }
      router.refresh();
    });
  }

  const etapaDocumente = ai?.etape.find((e) => e.etapa === "documente");
  const etapaBrief = ai?.etape.find((e) => e.etapa === "brief");

  return (
    <section className="rounded-card border border-line bg-surface p-5">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-2.5">
          <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary-50 text-primary-600">
            <Sparkles size={14} strokeWidth={1.75} aria-hidden />
          </span>
          <div>
            <h2 className="text-[15px] font-semibold text-ink">Observații generate automat</h2>
            <p className="mt-1 text-[13px] leading-[19px] text-ink-faint">
              Nu au schimbat scorul și nu înlocuiesc decizia ta.
            </p>
          </div>
        </div>
        <Button
          varianta="ghost"
          marime="sm"
          loading={seRuleaza}
          onClick={ruleazaDinNou}
          iconaStanga={!seRuleaza ? <RefreshCw size={15} strokeWidth={1.75} aria-hidden /> : undefined}
        >
          Rulează din nou
        </Button>
      </div>

      {eroare ? (
        <div className="mt-3">
          <Banda ton="eroare">{eroare}</Banda>
        </div>
      ) : null}

      {!ai ? (
        <p className="mt-4 text-[13px] leading-[19px] text-ink-faint">
          Pipeline-ul n-a rulat încă pentru acest dosar — pornește automat la următoarea acțiune
          asupra cererii, sau poți apăsa „Rulează din nou”.
        </p>
      ) : (
        <>
          {ai.rulare.status === "esuat" ? (
            <div className="mt-3">
              <Banda ton="eroare">Ultima rulare nu s-a putut finaliza.</Banda>
            </div>
          ) : null}

          <Semnale semnale={ai.semnale} />

          {etapaDocumente && etapaDocumente.status === "reusit" ? (
            <ExtractieDocumentSectiune etapa={etapaDocumente} />
          ) : null}

          {etapaBrief && etapaBrief.status === "reusit" ? <BriefSectiune etapa={etapaBrief} /> : null}
        </>
      )}
    </section>
  );
}

function Semnale({ semnale }: { semnale: SemnalAi[] }) {
  if (semnale.length === 0) {
    return <p className="mt-4 text-[13px] leading-[19px] text-ink-faint">Niciun semnal găsit.</p>;
  }

  const sortate = [...semnale].sort(
    (a, b) => ORDINE_SEVERITATE[a.severitate] - ORDINE_SEVERITATE[b.severitate],
  );

  return (
    <ul className="mt-4 flex flex-col gap-2">
      {sortate.map((semnal, indice) => (
        <li key={`${semnal.cod}-${indice}`} className="flex items-start gap-3 rounded-field bg-muted/60 p-3">
          <span
            className={cn(
              "mt-0.5 shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium",
              STIL_SEVERITATE[semnal.severitate],
            )}
          >
            {ETICHETA_SEVERITATE[semnal.severitate]}
          </span>
          <span className="text-[13px] leading-[19px] text-ink-soft">{etichetaSemnal(semnal.cod)}</span>
        </li>
      ))}
    </ul>
  );
}

function ExtractieDocumentSectiune({ etapa }: { etapa: EtapaAi }) {
  const rezultat = etapa.rezultat as ExtractieDocument;
  const citatVenit = rezultat.citate?.venit_net;

  return (
    <div className="mt-4 rounded-field border border-line p-3.5">
      <p className="text-[12px] font-semibold text-ink">Ce a citit modelul din document</p>
      <dl className="mt-2 grid grid-cols-2 gap-3 text-[12.5px]">
        <div>
          <dt className="text-ink-faint">Venit net</dt>
          <dd className="tabular text-ink">{rezultat.venit_net ? `${lei(rezultat.venit_net)} RON` : "—"}</dd>
        </div>
        <div>
          <dt className="text-ink-faint">Angajator</dt>
          <dd className="text-ink">{rezultat.angajator ?? "—"}</dd>
        </div>
      </dl>
      {citatVenit ? (
        <p className="mt-2.5 text-[12px] italic leading-[17px] text-ink-faint">„{citatVenit}”</p>
      ) : null}
    </div>
  );
}

function BriefSectiune({ etapa }: { etapa: EtapaAi }) {
  const rezultat = etapa.rezultat as BriefRezultat;
  const recomandare = rezultat.recomandare ?? "fara_recomandare";

  return (
    <div className="mt-4 rounded-field border border-line p-3.5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-[12px] font-semibold text-ink">Brief pentru analist</p>
        <span className="rounded-full bg-primary-50 px-2.5 py-1 text-[11.5px] font-medium text-primary-700">
          {ETICHETA_RECOMANDARE[recomandare]}
          {rezultat.incredere !== undefined ? ` · ${Math.round(rezultat.incredere * 100)}%` : ""}
        </span>
      </div>

      {rezultat.rezumat ? (
        <p className="mt-2.5 text-[13px] leading-[19px] text-ink-soft">{rezultat.rezumat}</p>
      ) : null}

      <ListaBrief titlu="Riscuri" elemente={rezultat.riscuri} />
      <ListaBrief titlu="Atenuări" elemente={rezultat.atenuari} />
      <ListaBrief titlu="Întrebări de pus clientului" elemente={rezultat.intrebari_de_pus} />
    </div>
  );
}

function ListaBrief({ titlu, elemente }: { titlu: string; elemente?: string[] }) {
  if (!elemente || elemente.length === 0) return null;

  return (
    <div className="mt-3">
      <p className="text-[11.5px] font-medium uppercase tracking-wide text-ink-faint">{titlu}</p>
      <ul className="mt-1.5 flex flex-col gap-1">
        {elemente.map((element, indice) => (
          <li key={indice} className="text-[13px] leading-[19px] text-ink-soft">
            • {element}
          </li>
        ))}
      </ul>
    </div>
  );
}
