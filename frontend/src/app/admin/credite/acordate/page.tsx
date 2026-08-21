import Link from "next/link";
import { ChevronLeft, Landmark } from "lucide-react";
import { Banda } from "@/components/ui/banda";
import { cereAdmin } from "@/lib/admin";
import { BackendError } from "@/lib/backend";
import { obtineCrediteAcordate } from "@/lib/data/admin-credite";
import { lei, type CreditAcordat } from "@/lib/tipuri-admin";
import { cn } from "@/lib/utils";

const STIL_STATUS: Record<string, string> = {
  activ: "bg-success/10 text-success",
  restant: "bg-danger/8 text-danger",
  inchis: "bg-muted text-ink-faint",
  rambursat_anticipat: "bg-primary-50 text-primary-700",
};

const ETICHETE: Record<string, string> = {
  activ: "Activ",
  restant: "Restant",
  inchis: "Închis",
  rambursat_anticipat: "Rambursat anticipat",
};

export default async function CrediteAcordatePage() {
  const admin = await cereAdmin();

  let credite: CreditAcordat[] = [];
  let eroare: string | null = null;

  try {
    credite = await obtineCrediteAcordate(admin.token);
  } catch (exc) {
    eroare =
      exc instanceof BackendError
        ? exc.message
        : "Nu am putut incarca creditele. Verifica daca backendul raspunde.";
  }

  return (
    <div className="flex flex-col gap-6">
      <Link
        href="/admin/credite"
        className="inline-flex w-fit items-center gap-1.5 text-[13px] font-semibold text-primary-600 hover:underline"
      >
        <ChevronLeft size={16} strokeWidth={2} aria-hidden />
        Înapoi la cereri
      </Link>

      <div>
        <h1 className="text-[26px] font-bold leading-8 tracking-[-0.02em] text-ink">
          Credite acordate
        </h1>
        <p className="mt-1.5 text-[15px] leading-[22px] text-ink-soft">
          Contractele semnate, cu soldul rămas la zi.
        </p>
      </div>

      {eroare ? <Banda ton="eroare">{eroare}</Banda> : null}

      {!eroare && credite.length === 0 ? (
        <section className="flex flex-col items-center gap-3 rounded-card border border-dashed border-line bg-surface p-10 text-center">
          <span className="flex h-14 w-14 items-center justify-center rounded-full bg-muted">
            <Landmark size={26} strokeWidth={1.75} aria-hidden className="text-ink-faint" />
          </span>
          <p className="text-[15px] font-semibold text-ink">Niciun credit acordat</p>
        </section>
      ) : null}

      {credite.length > 0 ? (
        <div className="overflow-hidden rounded-card border border-line bg-surface">
          {credite.map((credit) => (
            <div
              key={credit.id}
              className="flex items-center justify-between gap-4 border-b border-line p-4 last:border-b-0"
            >
              <div className="min-w-0">
                <p className="truncate text-[15px] font-semibold text-ink">{credit.nume}</p>
                <p className="text-[12.5px] text-ink-faint">
                  {lei(credit.principal)} RON pe {credit.luni} luni · rată{" "}
                  {lei(credit.rata_lunara)} RON · acordat{" "}
                  {new Date(credit.data_acordarii).toLocaleDateString("ro-RO", {
                    day: "numeric",
                    month: "short",
                    year: "numeric",
                  })}
                </p>
              </div>

              <div className="shrink-0 text-right">
                <p className="text-[15px] font-bold tabular text-ink">
                  {lei(credit.sold_ramas)} RON
                </p>
                <span
                  className={cn(
                    "mt-1 inline-flex items-center rounded-full px-2.5 py-1 text-[11.5px] font-medium",
                    STIL_STATUS[credit.status] ?? "bg-muted text-ink-faint",
                  )}
                >
                  {ETICHETE[credit.status] ?? credit.status}
                </span>
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export const dynamic = "force-dynamic";
