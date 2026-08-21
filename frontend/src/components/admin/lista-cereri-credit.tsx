"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTransition } from "react";
import { ChevronRight, Landmark } from "lucide-react";
import {
  ETICHETE_STATUS,
  lei,
  tonStatus,
  type CerereCredit,
  type StatusCerere,
} from "@/lib/tipuri-admin";
import { cn } from "@/lib/utils";

/**
 * Filtrele care conteaza pentru un analist, in ordinea in care le-ar folosi:
 * intai ce are de lucru, apoi ce a iesit din mana lui, apoi restul.
 *
 * `null` = toate. Nu e „niciun filtru", e o optiune la fel de valida ca
 * celelalte, si trebuie sa arate la fel.
 */
const FILTRE: { valoare: StatusCerere | null; eticheta: string }[] = [
  { valoare: "analiza_manuala", eticheta: "De decis" },
  { valoare: "oferta", eticheta: "Ofertă emisă" },
  { valoare: "acceptata", eticheta: "Acceptate" },
  { valoare: "respinsa", eticheta: "Respinse" },
  { valoare: null, eticheta: "Toate" },
];

const STIL_TON = {
  bun: "bg-success/10 text-success",
  rau: "bg-danger/8 text-danger",
  atentie: "bg-warning/10 text-warning",
  neutru: "bg-muted text-ink-faint",
} as const;

export function ListaCereriCredit({
  cereri,
  status,
}: {
  cereri: CerereCredit[];
  status: StatusCerere | null;
}) {
  const router = useRouter();
  const [seIncarca, startTransition] = useTransition();

  // Filtrul schimba datele, deci trece prin server. Nu se filtreaza in
  // browser: lista e taiata la 200 de randuri in backend, iar un filtru
  // aplicat peste o lista deja taiata ar minti.
  function schimbaFiltrul(nou: StatusCerere | null) {
    startTransition(() => {
      router.push(nou ? `/admin/credite?status=${nou}` : "/admin/credite");
    });
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap gap-2">
        {FILTRE.map(({ valoare, eticheta }) => (
          <button
            key={eticheta}
            type="button"
            onClick={() => schimbaFiltrul(valoare)}
            aria-pressed={valoare === status}
            className={cn(
              "rounded-full border px-3.5 py-1.5 text-[13px] font-medium transition-colors duration-150",
              valoare === status
                ? "border-primary-600 bg-primary-600 text-white"
                : "border-line bg-surface text-ink-soft hover:bg-primary-50",
              seIncarca && "opacity-60",
            )}
          >
            {eticheta}
          </button>
        ))}
      </div>

      {cereri.length === 0 ? (
        <section className="flex flex-col items-center gap-3 rounded-card border border-dashed border-line bg-surface p-10 text-center">
          <span className="flex h-14 w-14 items-center justify-center rounded-full bg-success/10">
            <Landmark size={26} strokeWidth={1.75} aria-hidden className="text-success" />
          </span>
          <p className="text-[15px] font-semibold text-ink">
            {status === "analiza_manuala" ? "Nimic de decis" : "Nicio cerere aici"}
          </p>
          <p className="max-w-sm text-[13px] leading-[19px] text-ink-faint">
            {status === "analiza_manuala"
              ? "Cererile ajung aici doar când punctajul cade în zona gri — între 45 și 69 din 100. Restul se decid singure."
              : "Schimbă filtrul de mai sus ca să vezi alte cereri."}
          </p>
        </section>
      ) : (
        <div className="flex flex-col gap-3">
          {cereri.map((cerere) => (
            <RandCerere key={cerere.id} cerere={cerere} />
          ))}
        </div>
      )}
    </div>
  );
}

function RandCerere({ cerere }: { cerere: CerereCredit }) {
  const ton = tonStatus(cerere.status);

  return (
    <Link
      href={`/admin/credite/${cerere.id}`}
      className="flex items-center gap-4 rounded-card border border-line bg-surface p-4 shadow-sm transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
    >
      <span
        className={cn(
          "flex h-14 w-14 shrink-0 flex-col items-center justify-center rounded-full",
          STIL_TON[ton],
        )}
      >
        {cerere.scor === null ? (
          <Landmark size={20} strokeWidth={1.75} aria-hidden />
        ) : (
          <>
            <span className="text-[16px] font-bold leading-5 tabular">{cerere.scor}</span>
            <span className="text-[10px] leading-3 opacity-80">din 100</span>
          </>
        )}
      </span>

      <span className="min-w-0 flex-1">
        <span className="block truncate text-[15px] font-semibold text-ink">{cerere.nume}</span>
        <span className="block truncate text-[12.5px] text-ink-faint">
          {lei(cerere.suma_ceruta)} RON · {cerere.luni} luni
        </span>
        <span className="mt-2 flex flex-wrap items-center gap-1.5">
          <span
            className={cn(
              "inline-flex items-center rounded-full px-2.5 py-1 text-[11.5px] font-medium",
              STIL_TON[ton],
            )}
          >
            {ETICHETE_STATUS[cerere.status]}
          </span>
          {cerere.dti ? (
            <span className="inline-flex items-center rounded-full bg-primary-50 px-2.5 py-1 text-[11.5px] font-medium text-primary-700">
              Grad de îndatorare {(Number(cerere.dti) * 100).toFixed(1)}%
            </span>
          ) : null}
        </span>
      </span>

      <span className="hidden shrink-0 text-right sm:block">
        <span className="block text-[12.5px] text-ink-faint">Depusă</span>
        <span className="block text-[13px] text-ink-soft">
          {new Date(cerere.creat_la).toLocaleDateString("ro-RO", {
            day: "numeric",
            month: "short",
            year: "numeric",
          })}
        </span>
      </span>

      <ChevronRight size={18} strokeWidth={1.75} aria-hidden className="shrink-0 text-ink-faint" />
    </Link>
  );
}
