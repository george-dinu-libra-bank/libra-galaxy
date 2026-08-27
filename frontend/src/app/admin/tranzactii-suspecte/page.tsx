import Link from "next/link";
import { cereAdmin } from "@/lib/admin";
import { obtineTranzactiiSemnalate, type TranzactieSemnalata } from "@/lib/data/admin-securitate";
import { Banda } from "@/components/ui/banda";
import { ListaTranzactiiSemnalate } from "@/components/admin/lista-tranzactii-semnalate";

export const dynamic = "force-dynamic";

export default async function PaginaTranzactiiSuspecte() {
  await cereAdmin();

  let tranzactii: TranzactieSemnalata[] = [];
  let eroare: string | null = null;

  try {
    tranzactii = await obtineTranzactiiSemnalate();
  } catch (exc) {
    console.error("ERROR PaginaTranzactiiSuspecte:", exc);
    eroare =
      "Nu am putut încărca transferurile oprite. Verifică dacă migrația 0036 a fost aplicată.";
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-[26px] font-bold leading-8 tracking-[-0.02em] text-ink">
          Tranzacții suspecte
        </h1>
        <p className="mt-1.5 max-w-2xl text-[15px] leading-[22px] text-ink-soft">
          Transferuri oprite fiindcă descrierea lor s-a potrivit cu un cuvânt din{" "}
          <Link
            href="/admin/securitate"
            className="font-semibold text-primary-600 underline-offset-2 hover:underline"
          >
            lista de securitate
          </Link>
          . Banii au fost luați din contul expeditorului, dar nu au ajuns la beneficiar:
          stau aici până iei o decizie.
        </p>
      </div>

      {eroare ? <Banda ton="eroare">{eroare}</Banda> : null}

      {!eroare ? <ListaTranzactiiSemnalate tranzactii={tranzactii} /> : null}
    </div>
  );
}
