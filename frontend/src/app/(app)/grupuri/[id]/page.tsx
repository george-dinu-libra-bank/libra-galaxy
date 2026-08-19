import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ChevronLeft } from "lucide-react";
import { ConversatieGrup } from "@/components/grupuri/conversatie-grup";
import { DepuneInGrupDrawer } from "@/components/grupuri/depune-in-grup-drawer";
import { IesiDinGrupDrawer } from "@/components/grupuri/iesi-din-grup-drawer";
import { PartajeazaGrupDrawer } from "@/components/grupuri/partajeaza-grup-drawer";
import { AvatarProfil } from "@/components/ui/avatar-profil";
import { obtineConturiUtilizator } from "@/lib/data/conturi";
import {
  obtineGrup,
  obtineMembriiGrupului,
  obtineMesajeleGrupului,
} from "@/lib/data/grupuri";
import { formateazaSuma } from "@/lib/utils";

export const metadata: Metadata = {
  title: "Grup · Libra",
};

/**
 * Un grup: soldul comun, membrii si conversatia.
 *
 * Daca utilizatorul nu e in grup, `obtineGrup` intoarce null — politica de
 * select din 0008_grupuri.sql nu ii arata randul — si pagina devine 404. Un id
 * ghicit nu spune nici macar daca grupul exista.
 */
export default async function GrupPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const idGrup = Number(id);

  if (!Number.isSafeInteger(idGrup) || idGrup <= 0) notFound();

  const grup = await obtineGrup(idGrup);

  if (!grup) notFound();

  const membri = await obtineMembriiGrupului(idGrup);
  const mesaje = await obtineMesajeleGrupului(idGrup, membri);
  const conturi = await obtineConturiUtilizator();

  return (
    <div className="mx-auto w-full max-w-[440px] px-6 pb-6 pt-8 sm:max-w-2xl">
      <Link
        href="/grupuri"
        className="-ml-2 inline-flex h-10 items-center gap-1 rounded-xl px-2 text-[13px] font-medium text-ink-soft transition-colors hover:text-primary-700 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
      >
        <ChevronLeft size={18} strokeWidth={1.75} aria-hidden />
        Grupuri
      </Link>

      <div className="mt-2 flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-xl font-bold tracking-[-0.02em] text-ink">
            {grup.nume}
          </h1>
          <p className="mt-1 text-[13px] text-ink-faint">
            {membri.length === 1 ? "1 membru" : `${membri.length} membri`}
          </p>
        </div>

        <PartajeazaGrupDrawer nume={grup.nume} token={grup.tokenAcces} />
      </div>

      <section className="hero-gradient mt-6 flex items-center gap-4 rounded-card px-5 py-6 shadow-md">
        <div className="min-w-0 flex-1">
          <p className="text-[12.5px] text-primary-100">Sold grup</p>
          <p className="tabular mt-1 text-[30px] font-bold leading-[36px] text-white">
            {formateazaSuma(grup.sold)}
          </p>
          <p className="mt-1 text-[12.5px] text-primary-100">
            Oricine din grup poate plăti din soldul comun.
          </p>
        </div>

        <DepuneInGrupDrawer idGrup={grup.id} conturi={conturi} />
      </section>

      <section className="mt-8">
        <h2 className="text-lg font-semibold text-ink">Membri</h2>

        <div className="mt-4 overflow-hidden rounded-card bg-surface shadow-sm">
          {membri.map((membru, i) => (
            <div
              key={membru.idUser}
              className={`flex items-center gap-3 px-4 py-3 ${
                i === membri.length - 1 ? "" : "border-b border-line"
              }`}
            >
              <span className="h-10 w-10 shrink-0">
                <AvatarProfil url={membru.avatarUrl} nume={membru.nume} />
              </span>

              <p className="min-w-0 flex-1 truncate text-[15px] text-ink">{membru.nume}</p>
            </div>
          ))}
        </div>
      </section>

      <ConversatieGrup idGrup={grup.id} mesaje={mesaje} />

      <div className="mt-8">
        <IesiDinGrupDrawer idGrup={grup.id} nume={grup.nume} />
      </div>
    </div>
  );
}
