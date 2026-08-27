import Link from "next/link";
import { cereAdmin } from "@/lib/admin";
import { BackendError } from "@/lib/backend";
import { obtineConturiSemnalate, obtineStareDetectie } from "@/lib/data/admin-tranzactii";
import type { ContSemnalat, StareDetectie } from "@/lib/tipuri-admin";
import { Banda } from "@/components/ui/banda";
import { ListaConturiSemnalate } from "@/components/admin/lista-conturi-semnalate";

export const dynamic = "force-dynamic";

const ZILE_IMPLICIT = 30;
const ZILE_PERMISE = [7, 30, 90, 365];

export default async function PaginaTranzactii({
  searchParams,
}: {
  searchParams: Promise<{ zile?: string }>;
}) {
  const [{ zile: zileBrut }, admin] = await Promise.all([searchParams, cereAdmin()]);

  // Perioada vine din URL, deci poate fi orice; o aducem la una dintre valorile
  // pe care le ofera si interfata.
  const cerut = Number(zileBrut);
  const zile = ZILE_PERMISE.includes(cerut) ? cerut : ZILE_IMPLICIT;

  let conturi: ContSemnalat[] = [];
  let eroare: string | null = null;
  // Starea detectiei se cere separat si nu blocheaza lista: daca ruta lipseste
  // sau cade, pagina trebuie sa se vada oricum.
  let stare: StareDetectie | null = null;

  try {
    [conturi, stare] = await Promise.all([
      obtineConturiSemnalate(admin.token, zile),
      obtineStareDetectie(admin.token).catch(() => null),
    ]);
  } catch (exc) {
    eroare =
      exc instanceof BackendError
        ? exc.message
        : "Nu am putut încărca lista. Verifică dacă backendul răspunde.";
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-[26px] font-bold leading-8 tracking-[-0.02em] text-ink">
          Conturi semnalate
        </h1>
        <p className="mt-1.5 max-w-2xl text-[15px] leading-[22px] text-ink-soft">
          Conturile cu plăți care ies din tiparul lor obișnuit. Sunt constatări statistice,
          nu fraude dovedite.
        </p>
        <p className="mt-2 max-w-2xl text-[13px] leading-[19px] text-ink-faint">
          Plățile de aici au trecut deja; te uiți în urmă și decizi. Transferurile prinse
          de scanerul de cuvinte, cu banii încă blocați, sunt la{" "}
          <Link
            href="/admin/tranzactii-suspecte"
            className="font-semibold text-primary-600 underline-offset-2 hover:underline"
          >
            Transferuri oprite
          </Link>
          .
        </p>
      </div>

      {eroare ? <Banda ton="eroare">{eroare}</Banda> : null}

      {stare && !stare.activ ? (
        <Banda ton="info">
          <strong className="font-semibold">Detecția rulează parțial.</strong>{" "}
          {stare.explicatie} Lista de mai jos poate fi incompletă.
        </Banda>
      ) : null}

      {!eroare ? (
        <ListaConturiSemnalate conturi={conturi} zile={zile} zilePermise={ZILE_PERMISE} />
      ) : null}
    </div>
  );
}
