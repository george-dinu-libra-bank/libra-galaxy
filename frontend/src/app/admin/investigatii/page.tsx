import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { cereAdmin } from "@/lib/admin";
import {
  ETICHETA_STARE,
  obtineCoada,
  type Investigatie,
} from "@/lib/data/investigatii";
import { Banda } from "@/components/ui/banda";
import { cn } from "@/lib/utils";

export const dynamic = "force-dynamic";

/**
 * Coada investigațiilor, cea mai veche prima.
 *
 * Ordinea e inversă față de restul listelor din panou: aici nu contează ce e
 * nou, ci cine așteaptă de cel mai mult timp — de regulă cu contul blocat.
 */

const TON_STARE: Record<string, string> = {
  nou: "bg-primary-50 text-primary-700",
  in_analiza: "bg-primary-50 text-primary-700",
  asteptam_clientul: "bg-warning/10 text-warning",
  client_a_raspuns: "bg-success/10 text-success",
  rezolvat: "bg-line/60 text-ink-faint",
  escalat: "bg-danger/8 text-danger",
  inchis: "bg-line/60 text-ink-faint",
};

function zileDe(la: string): number {
  return Math.floor((Date.now() - new Date(la).getTime()) / 86_400_000);
}

function Rand({ caz }: { caz: Investigatie }) {
  const zile = zileDe(caz.deschis_la);

  return (
    <li>
      <Link
        href={`/admin/investigatii/${caz.id}`}
        className="flex items-center gap-4 rounded-card border border-line bg-surface p-4 transition-colors hover:border-primary-300"
      >
        <div className="min-w-0 flex-1">
          <p className="truncate text-[14px] font-medium text-ink">{caz.motiv_deschidere}</p>
          <p className="mt-1 text-[12px] text-ink-faint tabular">
            Deschisă {zile === 0 ? "azi" : zile === 1 ? "ieri" : `acum ${zile} zile`}
            {caz.gravitate !== null ? ` · gravitate ${caz.gravitate}/100` : ""}
            {caz.numar_semnalari !== null ? ` · ${caz.numar_semnalari} semnalări` : ""}
          </p>
        </div>

        <span
          className={cn(
            "shrink-0 rounded-full px-2.5 py-1 text-[11px] font-semibold",
            TON_STARE[caz.stare] ?? "bg-line/60 text-ink-faint",
          )}
        >
          {ETICHETA_STARE[caz.stare]}
        </span>

        <ChevronRight size={16} strokeWidth={2} aria-hidden className="shrink-0 text-ink-faint" />
      </Link>
    </li>
  );
}

export default async function PaginaInvestigatii({
  searchParams,
}: {
  searchParams: Promise<{ toate?: string }>;
}) {
  const [{ toate }, admin] = await Promise.all([searchParams, cereAdmin()]);
  const doarDeschise = toate !== "1";

  let cazuri: Investigatie[] = [];
  let eroare: string | null = null;

  try {
    cazuri = await obtineCoada(admin.token, doarDeschise);
  } catch (exc) {
    console.error("ERROR PaginaInvestigatii:", exc);
    eroare =
      "Nu am putut încărca investigațiile. Verifică dacă migrarea 0051_caz_investigatie.sql a fost rulată.";
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-[26px] font-bold leading-8 tracking-[-0.02em] text-ink">
          Investigații
        </h1>
        <p className="mt-1.5 max-w-2xl text-[15px] leading-[22px] text-ink-soft">
          Firele de discuție deschise de bancă pentru plăți semnalate. Se pornesc din{" "}
          <Link
            href="/admin/tranzactii"
            className="font-semibold text-primary-600 underline-offset-2 hover:underline"
          >
            conturile semnalate
          </Link>
          , de pe raportul unui client.
        </p>
      </div>

      <div className="flex gap-1.5">
        <Link
          href="/admin/investigatii"
          aria-current={doarDeschise ? "page" : undefined}
          className={cn(
            "rounded-full px-3.5 py-1.5 text-[13px] font-medium transition-colors",
            doarDeschise
              ? "bg-primary-600 text-white"
              : "border border-line text-ink-soft hover:text-primary-700",
          )}
        >
          Nerezolvate
        </Link>
        <Link
          href="/admin/investigatii?toate=1"
          aria-current={!doarDeschise ? "page" : undefined}
          className={cn(
            "rounded-full px-3.5 py-1.5 text-[13px] font-medium transition-colors",
            !doarDeschise
              ? "bg-primary-600 text-white"
              : "border border-line text-ink-soft hover:text-primary-700",
          )}
        >
          Toate
        </Link>
      </div>

      {eroare ? <Banda ton="eroare">{eroare}</Banda> : null}

      {!eroare && cazuri.length === 0 ? (
        <p className="rounded-card border border-dashed border-line p-6 text-center text-[14px] text-ink-soft">
          {doarDeschise
            ? "Nicio investigație nerezolvată."
            : "Nicio investigație deschisă până acum."}
        </p>
      ) : null}

      {cazuri.length > 0 ? (
        <ol className="flex flex-col gap-2">
          {cazuri.map((caz) => (
            <Rand key={caz.id} caz={caz} />
          ))}
        </ol>
      ) : null}
    </div>
  );
}
