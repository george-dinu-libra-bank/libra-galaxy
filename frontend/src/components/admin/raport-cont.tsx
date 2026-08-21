"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState, useTransition } from "react";
import {
  ChevronDown,
  FileSpreadsheet,
  FileText,
  Loader2,
  Sparkles,
} from "lucide-react";
import {
  etichetaTip,
  tonScor,
  type Constatare,
  type Raport,
} from "@/lib/tipuri-admin";
import { cn, formateazaSuma } from "@/lib/utils";

/** Culoarea porneste de la gravitatea din tipuri-admin: un singur set de praguri. */
const CULOARE_GRAVITATE = {
  grav: "text-danger",
  atentie: "text-warning",
  usor: "text-ink-soft",
} as const;

function culoareScor(scor: number): string {
  return CULOARE_GRAVITATE[tonScor(scor)];
}

export function RaportCont({
  raport,
  zile,
  zilePermise,
  cuSinteza,
}: {
  raport: Raport;
  zile: number;
  zilePermise: number[];
  cuSinteza: boolean;
}) {
  const router = useRouter();
  const [tipAles, setTipAles] = useState<string | null>(null);
  const [desfasurata, setDesfasurata] = useState<string | null>(null);
  const [seIncarca, startTransition] = useTransition();

  const baza = `/admin/tranzactii/${raport.id_utilizator}`;

  function mergiLa(zileNoi: number, sinteza: boolean) {
    startTransition(() => {
      router.push(`${baza}?zile=${zileNoi}${sinteza ? "&sinteza=1" : ""}`);
    });
  }

  const constatari = useMemo(
    () => (tipAles ? raport.constatari.filter((c) => c.tip === tipAles) : raport.constatari),
    [raport.constatari, tipAles],
  );

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-[26px] font-bold leading-8 tracking-[-0.02em] text-ink">
          {raport.nume}
        </h1>
        <p className="mt-1 text-[15px] text-ink-soft">{raport.email}</p>
        <p className="tabular mt-1 text-[13px] text-ink-faint">{raport.iban}</p>
      </div>

      {/* Perioada */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[13px] font-medium text-ink-faint">Perioadă:</span>
        {zilePermise.map((z) => (
          <button
            key={z}
            type="button"
            onClick={() => mergiLa(z, cuSinteza)}
            aria-pressed={z === zile}
            className={cn(
              "rounded-full border px-3.5 py-1.5 text-[13px] font-medium transition-colors",
              z === zile
                ? "border-primary-600 bg-primary-600 text-white"
                : "border-line bg-surface text-ink-soft hover:bg-primary-50",
              seIncarca && "opacity-60",
            )}
          >
            {z === 365 ? "1 an" : `${z} zile`}
          </button>
        ))}
      </div>

      {/* Cifrele mari */}
      <div className="grid gap-3 sm:grid-cols-4">
        <Cifra eticheta="Semnalări" valoare={String(raport.numar_semnalari)} />
        <Cifra eticheta="Sumă semnalată" valoare={formateazaSuma(raport.suma_semnalata)} />
        <Cifra
          eticheta="Cel mai mare scor"
          valoare={raport.scor_maxim.toFixed(2)}
          ton={culoareScor(raport.scor_maxim)}
        />
        <Cifra eticheta="Tranzacții analizate" valoare={String(raport.total_tranzactii)} />
      </div>

      <Sinteza
        text={raport.sinteza}
        cerut={cuSinteza}
        seIncarca={seIncarca}
        onCere={() => mergiLa(zile, true)}
      />

      <Descarcari idUtilizator={raport.id_utilizator} zile={zile} />

      {/* Filtrul pe tip lucreaza pe datele deja aduse, deci raspunde instant. */}
      {raport.numar_semnalari > 0 ? (
        <section>
          <div className="flex flex-wrap items-center gap-2">
            <Chip activ={tipAles === null} onClick={() => setTipAles(null)}>
              Toate ({raport.numar_semnalari})
            </Chip>
            {Object.entries(raport.pe_tip)
              .sort(([, a], [, b]) => b - a)
              .map(([tip, cate]) => (
                <Chip key={tip} activ={tipAles === tip} onClick={() => setTipAles(tip)}>
                  {etichetaTip(tip)} ({cate})
                </Chip>
              ))}
          </div>

          <div className="mt-4 overflow-hidden rounded-card border border-line bg-surface">
            {constatari.map((c, i) => (
              <RandConstatare
                key={c.id_tranzactie}
                constatare={c}
                ultimul={i === constatari.length - 1}
                desfasurata={desfasurata === c.id_tranzactie}
                onComuta={() =>
                  setDesfasurata((d) => (d === c.id_tranzactie ? null : c.id_tranzactie))
                }
              />
            ))}
          </div>
        </section>
      ) : (
        <p className="rounded-card border border-dashed border-line bg-surface p-10 text-center text-[15px] text-ink-faint">
          Nicio plată nu a ieșit din tiparul obișnuit al acestui cont în perioada aleasă.
        </p>
      )}

      <p className="text-[12.5px] leading-[18px] text-ink-faint">
        <strong className="font-semibold text-ink-soft">
          Constatările sunt statistice, nu fraude dovedite.
        </strong>{" "}
        Arată plăți care ies din tiparul obișnuit al contului și care merită verificate.
        Orice măsură se ia după verificare, nu pe baza acestui raport singur.
      </p>
    </div>
  );
}

function Cifra({
  eticheta,
  valoare,
  ton,
}: {
  eticheta: string;
  valoare: string;
  ton?: string;
}) {
  return (
    <div className="rounded-card border border-line bg-surface p-4">
      <p className="text-[12.5px] text-ink-faint">{eticheta}</p>
      <p className={cn("tabular mt-1 text-[22px] font-bold leading-7 text-ink", ton)}>
        {valoare}
      </p>
    </div>
  );
}

function Chip({
  activ,
  onClick,
  children,
}: {
  activ: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={activ}
      className={cn(
        "rounded-full border px-3.5 py-1.5 text-[13px] font-medium transition-colors",
        activ
          ? "border-primary-600 bg-primary-600 text-white"
          : "border-line bg-surface text-ink-soft hover:bg-primary-50",
      )}
    >
      {children}
    </button>
  );
}

function Sinteza({
  text,
  cerut,
  seIncarca,
  onCere,
}: {
  text: string | null;
  cerut: boolean;
  seIncarca: boolean;
  onCere: () => void;
}) {
  if (text) {
    return (
      <section className="rounded-card border border-primary-100 bg-primary-50 p-5">
        <div className="flex items-center gap-2">
          <Sparkles size={16} strokeWidth={1.75} aria-hidden className="text-primary-600" />
          <h2 className="text-[15px] font-semibold text-primary-900">Sinteză</h2>
        </div>
        <p className="mt-2 text-[14px] leading-[21px] text-primary-900">{text}</p>
        <p className="mt-3 text-[12px] leading-[17px] text-primary-700">
          Scrisă automat. Faptele pe care se bazează sunt în tabelul de mai jos; în caz de
          nepotrivire, tabelul are dreptate.
        </p>
      </section>
    );
  }

  return (
    <section className="flex flex-wrap items-center justify-between gap-3 rounded-card border border-dashed border-line bg-surface p-4">
      <div className="flex items-center gap-2">
        <Sparkles size={16} strokeWidth={1.75} aria-hidden className="text-ink-faint" />
        <p className="text-[13px] text-ink-soft">
          {cerut
            ? "Sinteza nu a putut fi generată. Faptele de mai jos rămân neschimbate."
            : "Poți cere un rezumat în cuvinte al semnalărilor."}
        </p>
      </div>

      {!cerut ? (
        <button
          type="button"
          onClick={onCere}
          disabled={seIncarca}
          className="inline-flex items-center gap-2 rounded-field bg-primary-600 px-4 py-2 text-[13px] font-semibold text-white transition-colors hover:bg-primary-700 disabled:opacity-60"
        >
          {seIncarca ? (
            <Loader2 size={15} strokeWidth={2} aria-hidden className="animate-spin" />
          ) : null}
          Generează sinteza
        </button>
      ) : null}
    </section>
  );
}

function Descarcari({ idUtilizator, zile }: { idUtilizator: string; zile: number }) {
  // Link-uri simple, nu fetch: descarcarea trece prin proxy-ul /api/backend,
  // care adauga tokenul si transmite numele fisierului mai departe.
  const baza = `/api/backend/api/v1/admin/raport/${idUtilizator}`;

  return (
    <section className="flex flex-wrap items-center gap-3 rounded-card border border-line bg-surface p-4">
      <span className="text-[13px] font-medium text-ink-soft">Descarcă raportul:</span>

      <a
        href={`${baza}/pdf?zile=${zile}&sinteza=true`}
        className="inline-flex items-center gap-2 rounded-field border border-line px-4 py-2 text-[13px] font-semibold text-ink-soft transition-colors hover:bg-muted"
      >
        <FileText size={16} strokeWidth={1.75} aria-hidden />
        PDF
      </a>

      <a
        href={`${baza}/csv?zile=${zile}`}
        className="inline-flex items-center gap-2 rounded-field border border-line px-4 py-2 text-[13px] font-semibold text-ink-soft transition-colors hover:bg-muted"
      >
        <FileSpreadsheet size={16} strokeWidth={1.75} aria-hidden />
        CSV
      </a>
    </section>
  );
}

function RandConstatare({
  constatare,
  ultimul,
  desfasurata,
  onComuta,
}: {
  constatare: Constatare;
  ultimul: boolean;
  desfasurata: boolean;
  onComuta: () => void;
}) {
  return (
    <div className={cn(!ultimul && "border-b border-line")}>
      <button
        type="button"
        onClick={onComuta}
        aria-expanded={desfasurata}
        className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-muted"
      >
        <span className="w-[70px] shrink-0 text-[12.5px] text-ink-faint">
          {new Date(constatare.data).toLocaleDateString("ro-RO", {
            day: "numeric",
            month: "short",
          })}
        </span>

        <span className="min-w-0 flex-1">
          <span className="block truncate text-[14px] text-ink">{constatare.comerciant}</span>
          <span className="block text-[12px] text-ink-faint">
            {etichetaTip(constatare.tip)}
          </span>
        </span>

        <span className="tabular shrink-0 text-[14px] font-semibold text-ink">
          {formateazaSuma(constatare.suma, constatare.valuta)}
        </span>

        <span
          className={cn(
            "tabular w-12 shrink-0 text-right text-[13px] font-bold",
            culoareScor(constatare.scor),
          )}
        >
          {constatare.scor.toFixed(1)}
        </span>

        <ChevronDown
          size={16}
          strokeWidth={2}
          aria-hidden
          className={cn(
            "shrink-0 text-ink-faint transition-transform duration-150",
            desfasurata && "rotate-180",
          )}
        />
      </button>

      {desfasurata ? (
        <div className="animate-fade-up bg-muted px-4 py-3">
          <p className="text-[13px] leading-[19px] text-ink-soft">{constatare.explicatie}</p>
          <p className="tabular mt-2 text-[11.5px] text-ink-faint">
            ID tranzacție: {constatare.id_tranzactie}
          </p>
        </div>
      ) : null}
    </div>
  );
}
