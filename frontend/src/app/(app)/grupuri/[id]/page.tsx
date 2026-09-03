import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ChevronLeft } from "lucide-react";
import { ConversatieGrup } from "@/components/grupuri/conversatie-grup";
import { DepuneInGrupDrawer } from "@/components/grupuri/depune-in-grup-drawer";
import { FundalGrupStrat } from "@/components/grupuri/fundal-grup";
import { IesiDinGrupDrawer } from "@/components/grupuri/iesi-din-grup-drawer";
import { InviteazaDinContrapartiDrawer } from "@/components/grupuri/invita-din-contraparti-drawer";
import { ListaMembriGrup } from "@/components/grupuri/lista-membri-grup";
import { PartajeazaGrupDrawer } from "@/components/grupuri/partajeaza-grup-drawer";
import { SetariGrupDrawer } from "@/components/grupuri/setari-grup-drawer";
import { StergeGrupDrawer } from "@/components/grupuri/sterge-grup-drawer";
import { VizibilitateTranzactii } from "@/components/grupuri/vizibilitate-tranzactii";
import { ScopTemaDrawer } from "@/components/ui/drawer";
import { obtineConturiUtilizator } from "@/lib/data/conturi";
import {
  obtineDrepturileMembrilor,
  obtineGrup,
  obtineMesajeleGrupului,
} from "@/lib/data/grupuri";
import { obtineContrapartiRecente } from "@/lib/data/tranzactii";
import { createClient } from "@/lib/supabase/server";
import { CLASA_TEMA_GRUP, EMBLEME_GRUP } from "@/lib/tema-grup";
import { cn, formateazaSuma } from "@/lib/utils";

export const metadata: Metadata = {
  title: "Grup · Galaxy Bank",
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

  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  const esteCreator = user?.id === grup.idCreator;

  // Drepturile vin odata cu membrii, dintr-un singur RPC: si lista, si ce poate
  // face fiecare cu soldul comun (0053_drepturi_grup.sql).
  const [membri, conturi, contraparti] = await Promise.all([
    obtineDrepturileMembrilor(idGrup),
    obtineConturiUtilizator(),
    esteCreator ? obtineContrapartiRecente() : Promise.resolve([]),
  ]);
  const mesaje = await obtineMesajeleGrupului(idGrup, membri);

  const Emblema = EMBLEME_GRUP[grup.emblema];

  return (
    // Clasa temei rescrie rampa `--color-primary-*` doar pe subarborele asta
    // (0054_tema_grup.sql, .tema-grup-* din globals.css). Nimic de mai jos nu
    // stie ce culoare are grupul: hero-ul, butoanele, membrii si conversatia se
    // recoloreaza singure, fiindca folosesc aceleasi clase ca peste tot.
    //
    // `ScopTemaDrawer` acopera ce nu poate acoperi clasa: vaul face portal in
    // document.body, deci drawerele deschise de aici (depune, invita, drepturi,
    // iesi, sterge) sunt in afara div-ului si n-ar mosteni tema.
    <ScopTemaDrawer clasa={CLASA_TEMA_GRUP[grup.tema]}>
      <div
        className={cn(
          "mx-auto w-full max-w-[440px] px-6 pb-6 pt-8 sm:max-w-2xl",
          CLASA_TEMA_GRUP[grup.tema],
        )}
      >
        {/* Inauntrul containerului temat, ca modelul sa fie desenat in culoarea
            grupului; `fixed` il duce oricum peste tot ecranul. */}
        <FundalGrupStrat fundal={grup.fundal} />

        <Link
          href="/grupuri"
          className="-ml-2 inline-flex h-10 items-center gap-1 rounded-xl px-2 text-[13px] font-medium text-ink-soft transition-colors hover:text-primary-700 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
        >
          <ChevronLeft size={18} strokeWidth={1.75} aria-hidden />
          Grupuri
        </Link>

        <div className="mt-2 flex items-start gap-3">
          <span className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary-50">
            <Emblema size={20} strokeWidth={1.75} aria-hidden className="text-primary-600" />
          </span>

          <div className="min-w-0 flex-1">
            <h1 className="truncate text-xl font-bold tracking-[-0.02em] text-ink">
              {grup.nume}
            </h1>
            <p className="mt-1 text-[13px] text-ink-faint">
              {membri.length === 1 ? "1 membru" : `${membri.length} membri`}
            </p>
          </div>

          <div className="flex shrink-0 items-center gap-2">
            <PartajeazaGrupDrawer nume={grup.nume} token={grup.tokenAcces} />
            {/* Deschis de orice membru, nu doar de creator: tema e a locului
                comun, nu o parghie asupra banilor (vezi 0054_tema_grup.sql). */}
            <SetariGrupDrawer
              idGrup={grup.id}
              nume={grup.nume}
              sold={grup.sold}
              tema={grup.tema}
              emblema={grup.emblema}
              fundal={grup.fundal}
            />
          </div>
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
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-lg font-semibold text-ink">Membri</h2>
            {esteCreator ? (
              <InviteazaDinContrapartiDrawer idGrup={grup.id} contraparti={contraparti} />
            ) : null}
          </div>

          <ListaMembriGrup
            membri={membri}
            idGrup={grup.id}
            esteCreator={esteCreator}
            idUserCurent={user?.id ?? ""}
          />

          {/* Comutatorul e al creatorului; ceilalti nici nu afla ca exista, ca sa
              nu se citeasca drept „mi se ascunde ceva" cand e pornit. */}
          {esteCreator ? (
            <VizibilitateTranzactii
              idGrup={grup.id}
              vizibile={grup.tranzactiiVizibile}
            />
          ) : null}
        </section>

        <ConversatieGrup idGrup={grup.id} mesaje={mesaje} />

        <div className="mt-8 flex flex-col gap-1">
          <IesiDinGrupDrawer idGrup={grup.id} nume={grup.nume} />
          {esteCreator ? <StergeGrupDrawer idGrup={grup.id} nume={grup.nume} /> : null}
        </div>
      </div>
    </ScopTemaDrawer>
  );
}
