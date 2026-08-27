"use client";

import { useRouter } from "next/navigation";
import { UserMinus } from "lucide-react";
import { useState, useTransition } from "react";
import { AvatarProfil } from "@/components/ui/avatar-profil";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { Drawer, DrawerClose, DrawerContent } from "@/components/ui/drawer";
import { eliminaMembruGrup } from "@/lib/actions/grupuri";
import type { MembruGrup } from "@/lib/data/grupuri";

/**
 * Membrii grupului. Creatorul poate elimina pe oricine altcineva (nu pe sine
 * — pentru asta exista „Ieși din grup") — elimina_membru_grup
 * (0046_gestiune_grup.sql) oricum ar refuza orice altceva.
 */
export function ListaMembriGrup({
  membri,
  idGrup,
  esteCreator,
  idUserCurent,
}: {
  membri: MembruGrup[];
  idGrup: number;
  esteCreator: boolean;
  idUserCurent: string;
}) {
  const router = useRouter();
  const [deEliminat, setDeEliminat] = useState<MembruGrup | null>(null);
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

            <p className="min-w-0 flex-1 truncate text-[15px] text-ink">{membru.nume}</p>

            {esteCreator && membru.idUser !== idUserCurent ? (
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
            ) : null}
          </div>
        ))}
      </div>

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
                Poate reintra oricând, cu codul de acces al grupului.
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
