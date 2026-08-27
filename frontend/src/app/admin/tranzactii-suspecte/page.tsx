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
      "Nu am putut încărca transferurile oprite. Verifică dacă migrația 0043 a fost aplicată.";
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-[26px] font-bold leading-8 tracking-[-0.02em] text-ink">
          Transferuri oprite
        </h1>
        <p className="mt-1.5 max-w-2xl text-[15px] leading-[22px] text-ink-soft">
          Plăți individuale blocate fiindcă descrierea lor s-a potrivit cu un cuvânt din{" "}
          <Link
            href="/admin/securitate"
            className="font-semibold text-primary-600 underline-offset-2 hover:underline"
          >
            lista de securitate
          </Link>
          . Banii au fost luați din contul expeditorului, dar nu au ajuns la beneficiar:
          stau aici până iei o decizie.
        </p>
        <p className="mt-2 max-w-2xl text-[13px] leading-[19px] text-ink-faint">
          Aici banii stau pe loc și cineva așteaptă. Dacă ești în căutarea conturilor pe
          care le-a scos în evidență modelul, unde plățile au trecut deja, mergi la{" "}
          <Link
            href="/admin/tranzactii"
            className="font-semibold text-primary-600 underline-offset-2 hover:underline"
          >
            Conturi semnalate
          </Link>
          .
        </p>
      </div>

      {eroare ? <Banda ton="eroare">{eroare}</Banda> : null}

      {!eroare ? <ListaTranzactiiSemnalate tranzactii={tranzactii} /> : null}
    </div>
  );
}
