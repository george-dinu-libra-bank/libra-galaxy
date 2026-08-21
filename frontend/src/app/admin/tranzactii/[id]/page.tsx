import Link from "next/link";
import { notFound } from "next/navigation";
import { ChevronLeft } from "lucide-react";
import { cereAdmin } from "@/lib/admin";
import { BackendError } from "@/lib/backend";
import { obtineRaport } from "@/lib/data/admin-tranzactii";
import { RaportCont } from "@/components/admin/raport-cont";

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
    </div>
  );
}
