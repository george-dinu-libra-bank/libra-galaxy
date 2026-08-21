"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState, useTransition } from "react";
import { ChevronRight, Search, ShieldCheck } from "lucide-react";
import { Camp } from "@/components/ui/camp";
import { etichetaTip, tonScor, type ContSemnalat } from "@/lib/tipuri-admin";
import { cn, formateazaSuma } from "@/lib/utils";

type Sortare = "scor" | "suma" | "numar";

const SORTARI: { valoare: Sortare; eticheta: string }[] = [
  { valoare: "scor", eticheta: "Cel mai grav" },
  { valoare: "suma", eticheta: "Sumă totală" },
  { valoare: "numar", eticheta: "Câte semnalări" },
];

/** Culorile pornesc de la gravitatea din tipuri-admin, ca sa nu existe doua praguri. */
const STIL_GRAVITATE = {
  grav: { text: "text-danger", fundal: "bg-danger/8" },
  atentie: { text: "text-warning", fundal: "bg-warning/10" },
  usor: { text: "text-ink-soft", fundal: "bg-muted" },
} as const;

export function ListaConturiSemnalate({
  conturi,
  zile,
  zilePermise,
}: {
  conturi: ContSemnalat[];
  zile: number;
  zilePermise: number[];
}) {
  const router = useRouter();
  const [cautare, setCautare] = useState("");
  const [sortare, setSortare] = useState<Sortare>("scor");
  const [seIncarca, startTransition] = useTransition();

  function schimbaPerioada(zileNoi: number) {
    startTransition(() => {
      router.push(`/admin/tranzactii?zile=${zileNoi}`);
    });
  }

  const afisate = useMemo(() => {
    const q = cautare.trim().toLowerCase();
    const filtrate = q
      ? conturi.filter(
          (c) => c.nume.toLowerCase().includes(q) || c.email.toLowerCase().includes(q),
        )
      : conturi;

    const dupa = {
      scor: (a: ContSemnalat, b: ContSemnalat) => b.scor_maxim - a.scor_maxim,
      suma: (a: ContSemnalat, b: ContSemnalat) => b.suma_totala - a.suma_totala,
      numar: (a: ContSemnalat, b: ContSemnalat) => b.numar_semnalari - a.numar_semnalari,
    }[sortare];

    return [...filtrate].sort(dupa);
  }, [conturi, cautare, sortare]);

  return (
    <div className="flex flex-col gap-5">
      {/* Perioada schimba datele, deci trece prin server; restul filtrelor
          lucreaza pe ce e deja adus, ca sa raspunda instant. */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[13px] font-medium text-ink-faint">Perioadă:</span>
        {zilePermise.map((z) => (
          <button
            key={z}
            type="button"
            onClick={() => schimbaPerioada(z)}
            aria-pressed={z === zile}
            className={cn(
              "rounded-full border px-3.5 py-1.5 text-[13px] font-medium transition-colors duration-150",
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

      <div className="grid gap-3 sm:grid-cols-[1fr_auto] sm:items-end">
        <Camp
          eticheta="Caută"
          icoana={Search}
          value={cautare}
          onChange={(e) => setCautare(e.target.value)}
          placeholder="Nume sau email"
          autoComplete="off"
        />

        <div className="flex flex-col gap-1.5">
          <span className="text-[13px] font-medium text-ink-soft">Ordonează după</span>
          <div className="flex gap-1 rounded-field border border-line bg-surface p-1">
            {SORTARI.map(({ valoare, eticheta }) => (
              <button
                key={valoare}
                type="button"
                onClick={() => setSortare(valoare)}
                aria-pressed={sortare === valoare}
                className={cn(
                  "rounded-[10px] px-3 py-2 text-[13px] font-medium transition-colors",
                  sortare === valoare
                    ? "bg-primary-50 text-primary-700"
                    : "text-ink-faint hover:text-ink-soft",
                )}
              >
                {eticheta}
              </button>
            ))}
          </div>
        </div>
      </div>

      {conturi.length === 0 ? (
        <section className="flex flex-col items-center gap-3 rounded-card border border-dashed border-line bg-surface p-10 text-center">
          <span className="flex h-14 w-14 items-center justify-center rounded-full bg-success/10">
            <ShieldCheck size={26} strokeWidth={1.75} aria-hidden className="text-success" />
          </span>
          <p className="text-[15px] font-semibold text-ink">Niciun cont semnalat</p>
          <p className="max-w-sm text-[13px] leading-[19px] text-ink-faint">
            În perioada aleasă, nicio plată nu a ieșit din tiparul obișnuit al vreunui cont.
          </p>
        </section>
      ) : afisate.length === 0 ? (
        <p className="py-10 text-center text-[15px] text-ink-faint">
          Niciun cont nu se potrivește căutării.
        </p>
      ) : (
        <div className="flex flex-col gap-3">
          <p className="text-[13px] text-ink-faint">
            {afisate.length} {afisate.length === 1 ? "cont" : "conturi"}
            {cautare ? ` din ${conturi.length}` : ""}
          </p>

          {afisate.map((cont) => (
            <RandCont key={cont.id_utilizator} cont={cont} zile={zile} />
          ))}
        </div>
      )}
    </div>
  );
}

function RandCont({ cont, zile }: { cont: ContSemnalat; zile: number }) {
  const ton = STIL_GRAVITATE[tonScor(cont.scor_maxim)];

  return (
    <Link
      href={`/admin/tranzactii/${cont.id_utilizator}?zile=${zile}`}
      className="flex items-center gap-4 rounded-card border border-line bg-surface p-4 shadow-sm transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
    >
      <span
        className={cn(
          "flex h-14 w-14 shrink-0 flex-col items-center justify-center rounded-full",
          ton.fundal,
        )}
      >
        <span className={cn("tabular text-[15px] font-bold leading-4", ton.text)}>
          {cont.scor_maxim.toFixed(0)}
        </span>
        <span className={cn("text-[9px] uppercase tracking-wide", ton.text)}>scor</span>
      </span>

      <span className="min-w-0 flex-1">
        <span className="block truncate text-[15px] font-semibold text-ink">{cont.nume}</span>
        <span className="block truncate text-[12.5px] text-ink-faint">{cont.email}</span>

        <span className="mt-2 flex flex-wrap gap-1.5">
          {cont.tipuri.map((tip) => (
            <span
              key={tip}
              className="rounded-full bg-primary-50 px-2.5 py-1 text-[11.5px] font-medium text-primary-700"
            >
              {etichetaTip(tip)}
            </span>
          ))}
        </span>
      </span>

      <span className="hidden shrink-0 text-right sm:block">
        <span className="tabular block text-[15px] font-semibold text-ink">
          {formateazaSuma(cont.suma_totala)}
        </span>
        <span className="block text-[12.5px] text-ink-faint">
          {cont.numar_semnalari} {cont.numar_semnalari === 1 ? "semnalare" : "semnalări"}
        </span>
      </span>

      <ChevronRight size={18} strokeWidth={1.75} aria-hidden className="shrink-0 text-ink-faint" />
    </Link>
  );
}
