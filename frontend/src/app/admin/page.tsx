import Link from "next/link";
import { ChevronRight, ScanFace, ShieldCheck } from "lucide-react";
import { cereAdmin } from "@/lib/admin";
import { obtineCazuriDeRevizuit } from "@/lib/data/admin-verificari";
import type { CazVerificare } from "@/lib/tipuri-admin";
import { BackendError } from "@/lib/backend";
import { Banda } from "@/components/ui/banda";
import { EticheteCaz } from "@/components/admin/etichete-caz";

export default async function AdminPage() {
  const admin = await cereAdmin();

  let cazuri: CazVerificare[] = [];
  let eroare: string | null = null;

  try {
    cazuri = await obtineCazuriDeRevizuit(admin.token);
  } catch (exc) {
    eroare =
      exc instanceof BackendError
        ? exc.message
        : "Nu am putut incarca lista. Verifica daca backendul raspunde.";
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-[26px] font-bold leading-8 tracking-[-0.02em] text-ink">
          Verificări de identitate
        </h1>
        <p className="mt-1.5 text-[15px] leading-[22px] text-ink-soft">
          Conturile pe care verificarea automată nu le-a putut confirma singură.
        </p>
      </div>

      {eroare ? <Banda ton="eroare">{eroare}</Banda> : null}

      {!eroare && cazuri.length === 0 ? (
        <section className="flex flex-col items-center gap-3 rounded-card border border-dashed border-line bg-surface p-10 text-center">
          <span className="flex h-14 w-14 items-center justify-center rounded-full bg-success/10">
            <ShieldCheck size={26} strokeWidth={1.75} aria-hidden className="text-success" />
          </span>
          <p className="text-[15px] font-semibold text-ink">Nimic de revizuit</p>
          <p className="max-w-sm text-[13px] leading-[19px] text-ink-faint">
            Toate verificările au trecut automat. Cazurile ajung aici doar când fețele nu
            se potrivesc destul de bine sau CNP-ul citit nu coincide cu cel declarat.
          </p>
        </section>
      ) : null}

      {cazuri.length > 0 ? (
        <div className="flex flex-col gap-3">
          {cazuri.map((caz) => (
            <RandCaz key={caz.id} caz={caz} />
          ))}
        </div>
      ) : null}
    </div>
  );
}

function RandCaz({ caz }: { caz: CazVerificare }) {
  return (
    <Link
      href={`/admin/verificari/${caz.id}`}
      className="flex items-center gap-4 rounded-card border border-line bg-surface p-4 shadow-sm transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
    >
      <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-warning/10">
        <ScanFace size={20} strokeWidth={1.75} aria-hidden className="text-warning" />
      </span>

      <span className="min-w-0 flex-1">
        <span className="block truncate text-[15px] font-semibold text-ink">{caz.nume}</span>
        <span className="block truncate text-[12.5px] text-ink-faint">{caz.email}</span>
        <EticheteCaz caz={caz} className="mt-2" />
      </span>

      <span className="hidden shrink-0 text-right sm:block">
        <span className="block text-[12.5px] text-ink-faint">Trimis</span>
        <span className="block text-[13px] text-ink-soft">
          {new Date(caz.creat_la).toLocaleDateString("ro-RO", {
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

export const dynamic = "force-dynamic";
