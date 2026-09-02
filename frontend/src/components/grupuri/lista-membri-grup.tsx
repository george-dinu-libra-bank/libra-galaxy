"use client";

import { useRouter } from "next/navigation";
import { Ban, SlidersHorizontal, UserMinus } from "lucide-react";
import { useState, useTransition } from "react";
import { AvatarProfil } from "@/components/ui/avatar-profil";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { Drawer, DrawerClose, DrawerContent } from "@/components/ui/drawer";
import { DrepturiMembruDrawer } from "@/components/grupuri/drepturi-membru-drawer";
import { eliminaMembruGrup } from "@/lib/actions/grupuri";
import type { MembruCuDrepturi } from "@/lib/data/grupuri";
import { formateazaSuma } from "@/lib/utils";

/**
 * Sub numele fiecarui membru: ce poate face cu soldul comun.
 *
 * Se arata tuturor, nu doar creatorului — intr-o punga comuna e corect sa stii
 * pe ce reguli esti si cat ti-a mai ramas, fara sa incerci o plata ca sa afli.
 * Creatorul n-are randul lui de drepturi (0053_drepturi_grup.sql nu-l lasa
 * sa si le limiteze), deci pentru el linia lipseste.
 */
function Drepturi({ membru }: { membru: MembruCuDrepturi }) {
  if (membru.esteCreator) {
    return <span className="text-[12.5px] text-ink-faint">Creatorul grupului</span>;
  }

  if (!membru.poateCheltui) {
    return (
      <span className="flex items-center gap-1 text-[12.5px] text-ink-faint">
        <Ban size={11} strokeWidth={1.75} aria-hidden />
        Nu poate cheltui
      </span>
    );
  }

  if (membru.limitaLunara === null) {
    return <span className="text-[12.5px] text-ink-faint">Fără plafon lunar</span>;
  }

  const ramas = Math.max(membru.limitaLunara - membru.cheltuitLuna, 0);

  return (
    <span className="tabular text-[12.5px] text-ink-faint">
      {formateazaSuma(ramas)} din {formateazaSuma(membru.limitaLunara)} rămași luna asta
    </span>
  );
}

/**
 * Membrii grupului. Creatorul poate elimina pe oricine altcineva (nu pe sine
 * — pentru asta exista „Ieși din grup") si poate seta drepturile fiecaruia
 * asupra soldului comun — elimina_membru_grup (0046_gestiune_grup.sql) si
 * seteaza_drepturi_membru_grup (0053_drepturi_grup.sql) oricum ar refuza orice
 * altceva.
 */
export function ListaMembriGrup({
  membri,
  idGrup,
  esteCreator,
  idUserCurent,
}: {
  membri: MembruCuDrepturi[];
  idGrup: number;
  esteCreator: boolean;
  idUserCurent: string;
}) {
  const router = useRouter();
  const [deEliminat, setDeEliminat] = useState<MembruCuDrepturi | null>(null);
  const [deEditat, setDeEditat] = useState<MembruCuDrepturi | null>(null);
  const [eroare, setEroare] = useState<string | null>(null);
  const [seElimina, startTransition] = useTransition();

  function elimina() {
    if (!deEliminat) return;

    setEroare(null);

    startTransition(async () => {
      const rezultat = await eliminaMembruGrup(idGrup, deEliminat.idUser);

      if (rezultat.eroare) {
        setEroare(rezultat.eroare);
        return;
      }

      setDeEliminat(null);
      router.refresh();
    });
  }

  return (
    <>
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

            <span className="min-w-0 flex-1">
              <span className="block truncate text-[15px] text-ink">{membru.nume}</span>
              <span className="block truncate">
                <Drepturi membru={membru} />
              </span>
            </span>

            {esteCreator && membru.idUser !== idUserCurent ? (
              <>
                <button
                  type="button"
                  aria-label={`Setează drepturile lui ${membru.nume}`}
                  onClick={() => {
                    setEroare(null);
                    setDeEditat(membru);
                  }}
                  className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-ink-faint transition-colors hover:bg-primary-50 hover:text-primary-700 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
                >
                  <SlidersHorizontal size={17} strokeWidth={1.75} aria-hidden />
                </button>

                <button
                  type="button"
                  aria-label={`Elimină ${membru.nume} din grup`}
                  onClick={() => {
                    setEroare(null);
                    setDeEliminat(membru);
                  }}
                  className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-ink-faint transition-colors hover:bg-danger/8 hover:text-danger focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-danger/20"
                >
                  <UserMinus size={17} strokeWidth={1.75} aria-hidden />
                </button>
              </>
            ) : null}
          </div>
        ))}
      </div>

      {/* Cheia remonteaza drawerul la fiecare membru, ca formularul sa porneasca
          de la drepturile lui, nu de la ale celui deschis inainte. */}
      {deEditat ? (
        <DrepturiMembruDrawer
          key={deEditat.idUser}
          idGrup={idGrup}
          membru={deEditat}
          deschis
          onOpenChange={(deschis) => {
            if (!deschis) setDeEditat(null);
          }}
        />
      ) : null}

      <Drawer
        open={deEliminat !== null}
        onOpenChange={(deschis) => {
          if (!deschis) setDeEliminat(null);
        }}
      >
        {deEliminat ? (
          <DrawerContent
            title="Elimină din grup?"
            description={`${deEliminat.nume} nu va mai avea acces la grup.`}
            footer={
              <div className="flex flex-col gap-2">
                <Button varianta="danger" className="w-full" loading={seElimina} onClick={elimina}>
                  Da, elimină
                </Button>
                <DrawerClose asChild>
                  <Button varianta="ghost" className="w-full">
                    Renunță
                  </Button>
                </DrawerClose>
              </div>
            }
          >
            <div className="flex flex-col gap-4">
              {eroare ? <Banda ton="eroare">{eroare}</Banda> : null}
              <p className="text-[15px] leading-[22px] text-ink-soft">
                Poate reintra oricând, cu codul de acces al grupului — dar drepturile pe care
                i le-ai dat se pierd: la reintrare porneşte iar cu drept de cheltuială și fără
                plafon.
              </p>
            </div>
          </DrawerContent>
        ) : (
          <DrawerContent title="" description="">
            {null}
          </DrawerContent>
        )}
      </Drawer>
    </>
  );
}
