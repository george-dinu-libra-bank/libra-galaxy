import type { Metadata } from "next";
import { CreeazaGrupDrawer } from "@/components/grupuri/creeaza-grup-drawer";
import { IntraInGrupDrawer } from "@/components/grupuri/intra-in-grup-drawer";
import { InvitatiileMele } from "@/components/grupuri/invitatiile-mele";
import { ListaGrupuri } from "@/components/grupuri/lista-grupuri";
import { obtineGrupurileMele, obtineInvitatiileMele } from "@/lib/data/grupuri";
import { obtineContrapartiRecente } from "@/lib/data/tranzactii";

export const metadata: Metadata = {
  title: "Grupuri · Galaxy Bank",
};

/**
 * Lista grupurilor din care faci parte.
 *
 * Pagina e si tinta linkurilor de invitatie: `/grupuri?token=XXXXXXXXXXXX`
 * deschide direct drawerul de intrare, cu codul deja completat.
 */
export default async function GrupuriPage({
  searchParams,
}: {
  searchParams: Promise<{ token?: string | string[] }>;
}) {
  const { token } = await searchParams;
  const tokenInitial = Array.isArray(token) ? token[0] : token;

  const [grupuri, invitatii, contraparti] = await Promise.all([
    obtineGrupurileMele(),
    obtineInvitatiileMele(),
    obtineContrapartiRecente(),
  ]);

  return (
    <div className="mx-auto w-full max-w-[440px] px-6 pb-6 pt-8 sm:max-w-2xl">
      <h1 className="text-xl font-bold tracking-[-0.02em] text-ink">Grupuri</h1>
      <p className="mt-1 text-[13px] text-ink-faint">
        Un sold comun și o conversație, pentru oamenii cu care împarți cheltuieli.
      </p>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <CreeazaGrupDrawer contraparti={contraparti} />
        {/* `key` pe token: un link nou de invitatie remonteaza drawerul, deci
            cauta din nou grupul in loc sa ramana pe rezultatul precedent. */}
        <IntraInGrupDrawer key={tokenInitial ?? "manual"} tokenInitial={tokenInitial} />
      </div>

      <div className="mt-6">
        <InvitatiileMele invitatii={invitatii} />
      </div>

      <ListaGrupuri grupuri={grupuri} />
    </div>
  );
}
