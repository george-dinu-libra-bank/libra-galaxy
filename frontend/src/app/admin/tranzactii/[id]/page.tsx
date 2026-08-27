import Link from "next/link";
import { notFound } from "next/navigation";
import { ChevronLeft } from "lucide-react";
import { cereAdmin } from "@/lib/admin";
import { BackendError } from "@/lib/backend";
import { obtineRaport, obtineStareCont } from "@/lib/data/admin-tranzactii";
import type { StareCont } from "@/lib/tipuri-admin";
import { Banda } from "@/components/ui/banda";
import { RaportCont } from "@/components/admin/raport-cont";
import { DeciziaContului } from "@/components/admin/decizia-contului";
import { DeschideInvestigatie } from "@/components/admin/deschide-investigatie";

export const dynamic = "force-dynamic";

const ZILE_PERMISE = [7, 30, 90, 180, 365];
const ZILE_IMPLICIT = 180;

export default async function PaginaRaport({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ zile?: string; sinteza?: string }>;
}) {
  const [{ id }, { zile: zileBrut, sinteza }, admin] = await Promise.all([
    params,
    searchParams,
    cereAdmin(),
  ]);

  const cerut = Number(zileBrut);
  const zile = ZILE_PERMISE.includes(cerut) ? cerut : ZILE_IMPLICIT;

  // Sinteza costa un apel la model, deci se cere explicit, nu din oficiu.
  const cuSinteza = sinteza === "1";

  const raport = await obtineRaport(admin.token, id, zile, cuSinteza).catch((exc) => {
    if (exc instanceof BackendError && exc.status === 404) notFound();
    throw exc;
  });

  // Starea si istoricul nu blocheaza raportul: daca ruta cade, faptele trebuie
  // sa se vada oricum, chiar daca deciziile nu se pot lua acum. Motivul se
  // arata insa pe ecran — o sectiune care lipseste fara explicatie il lasa pe
  // administrator sa creada ca functionalitatea nu exista.
  let stare: StareCont | null = null;
  let eroareStare: string | null = null;
  try {
    stare = await obtineStareCont(admin.token, id);
  } catch (exc) {
    eroareStare =
      exc instanceof BackendError
        ? exc.message
        : "Nu am putut încărca istoricul deciziilor.";
  }

  return (
    <div className="flex flex-col gap-6">
      <Link
        href={`/admin/tranzactii?zile=${zile}`}
        className="inline-flex w-fit items-center gap-1.5 text-[13px] font-semibold text-primary-600 hover:underline"
      >
        <ChevronLeft size={16} strokeWidth={2} aria-hidden />
        Toate conturile semnalate
      </Link>

      <RaportCont raport={raport} zile={zile} zilePermise={ZILE_PERMISE} cuSinteza={cuSinteza} />

      {eroareStare ? (
        <Banda ton="info">
          <strong className="font-semibold">Analiza contului nu e disponibilă.</strong>{" "}
          {eroareStare} Dacă migrarea{" "}
          <code className="tabular">0020_analize_si_notificari.sql</code> nu a fost rulată
          încă, tabelele necesare lipsesc.
        </Banda>
      ) : null}

      {stare ? (
        <DeciziaContului
          idUtilizator={id}
          nume={raport.nume}
          gravitate={Math.round(raport.scor_maxim)}
          numarSemnalari={raport.numar_semnalari}
          zile={zile}
          esteBlocat={stare.conturi_blocate > 0}
          conturiTotal={stare.conturi_total}
          istoric={stare.analize}
        />
      ) : null}

      <DeschideInvestigatie
        idUtilizator={id}
        nume={raport.nume}
        gravitate={Math.round(raport.scor_maxim)}
        numarSemnalari={raport.numar_semnalari}
        constatari={raport.constatari}
      />
    </div>
  );
}
