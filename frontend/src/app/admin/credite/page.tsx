import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { Banda } from "@/components/ui/banda";
import { ListaCereriCredit } from "@/components/admin/lista-cereri-credit";
import { cereAdmin } from "@/lib/admin";
import { BackendError } from "@/lib/backend";
import { obtineCereriCredit, obtineCoadaCredite } from "@/lib/data/admin-credite";
import type { CerereCredit, StatusCerere } from "@/lib/tipuri-admin";

const STATUSURI_PERMISE: StatusCerere[] = [
  "ciorna",
  "in_analiza",
  "oferta",
  "analiza_manuala",
  "respinsa",
  "acceptata",
  "anulata",
  "expirata",
];

const STATUS_IMPLICIT: StatusCerere = "analiza_manuala";

export default async function CrediteAdminPage({
  searchParams,
}: {
  searchParams: Promise<{ status?: string }>;
}) {
  const [{ status: cerut }, admin] = await Promise.all([searchParams, cereAdmin()]);

  // Whitelist, nu valoarea din URL: `status` ajunge intr-un query parametru
  // catre backend, iar acolo o valoare necunoscuta ar da 422 in loc de o
  // pagina goala.
  const status: StatusCerere | null =
    cerut === "toate"
      ? null
      : STATUSURI_PERMISE.includes(cerut as StatusCerere)
        ? (cerut as StatusCerere)
        : STATUS_IMPLICIT;

  let cereri: CerereCredit[] = [];
  let eroare: string | null = null;

  try {
    // Coada trece prin ruta ei proprie, nu prin filtrul generic: aceea sorteaza
    // cea mai veche prima (cine asteapta de cel mai mult timp) si declanseaza
    // curatarea documentelor expirate.
    cereri =
      status === STATUS_IMPLICIT
        ? await obtineCoadaCredite(admin.token)
        : await obtineCereriCredit(admin.token, status ?? undefined);
  } catch (exc) {
    eroare =
      exc instanceof BackendError
        ? exc.message
        : "Nu am putut incarca cererile. Verifica daca backendul raspunde.";
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-[26px] font-bold leading-8 tracking-[-0.02em] text-ink">Credite</h1>
          <p className="mt-1.5 text-[15px] leading-[22px] text-ink-soft">
            Cererile pe care punctajul automat nu le-a putut hotărî singur, și istoricul
            celorlalte.
          </p>
        </div>
        <Link
          href="/admin/credite/acordate"
          className="inline-flex items-center gap-1.5 rounded-field px-3 py-2 text-[13px] font-semibold text-primary-600 transition-colors hover:bg-primary-50"
        >
          Credite acordate
          <ChevronRight size={16} strokeWidth={2} aria-hidden />
        </Link>
      </div>

      {eroare ? <Banda ton="eroare">{eroare}</Banda> : null}

      {!eroare ? <ListaCereriCredit cereri={cereri} status={status} /> : null}
    </div>
  );
}

export const dynamic = "force-dynamic";
