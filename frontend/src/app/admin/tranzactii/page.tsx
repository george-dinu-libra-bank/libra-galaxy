import { cereAdmin } from "@/lib/admin";
import { BackendError } from "@/lib/backend";
import { obtineConturiSemnalate } from "@/lib/data/admin-tranzactii";
import type { ContSemnalat } from "@/lib/tipuri-admin";
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

  try {
    conturi = await obtineConturiSemnalate(admin.token, zile);
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
          Tranzacții suspecte
        </h1>
        <p className="mt-1.5 text-[15px] leading-[22px] text-ink-soft">
          Conturile cu plăți care ies din tiparul lor obișnuit. Sunt constatări statistice,
          nu fraude dovedite.
        </p>
      </div>

      {eroare ? <Banda ton="eroare">{eroare}</Banda> : null}

      {!eroare ? (
        <ListaConturiSemnalate conturi={conturi} zile={zile} zilePermise={ZILE_PERMISE} />
      ) : null}
    </div>
  );
}
