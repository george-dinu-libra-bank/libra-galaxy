"use client";

import { useRouter } from "next/navigation";
import { Trash2 } from "lucide-react";
import { useState, useTransition } from "react";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { Drawer, DrawerClose, DrawerContent, DrawerTrigger } from "@/components/ui/drawer";
import { stergeGrup } from "@/lib/actions/grupuri";

/**
 * Stergerea definitiva a grupului, cu confirmare. Doar creatorul o vede
 * (decis de parinte, GrupPage) — sterge_grup (0046_gestiune_grup.sql) oricum
 * ar refuza pe oricine altcineva. Blocata cat timp mai e sold in grup: mesajul
 * de eroare (SOLD_NEZERO) spune exact ce mai e de facut.
 */
export function StergeGrupDrawer({ idGrup, nume }: { idGrup: number; nume: string }) {
  const router = useRouter();
  const [deschis, setDeschis] = useState(false);
  const [eroare, setEroare] = useState<string | null>(null);
  const [seSterge, startTransition] = useTransition();

  function sterge() {
    setEroare(null);

    startTransition(async () => {
      const rezultat = await stergeGrup(idGrup);

      if (rezultat.eroare) {
        setEroare(rezultat.eroare);
        return;
      }

      setDeschis(false);
      router.replace("/grupuri");
      router.refresh();
    });
  }

  return (
    <Drawer open={deschis} onOpenChange={setDeschis}>
      <DrawerTrigger className="flex h-11 w-full items-center justify-center gap-2 rounded-field text-[15px] font-semibold text-danger transition-colors hover:bg-danger/8 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-danger/20">
        <Trash2 size={18} strokeWidth={1.75} aria-hidden />
        Șterge grupul
      </DrawerTrigger>

      <DrawerContent
        title="Șterge grupul?"
        description={`„${nume}" va dispărea definitiv, pentru toți membrii.`}
        footer={
          <div className="flex flex-col gap-2">
            <Button varianta="danger" className="w-full" loading={seSterge} onClick={sterge}>
              Da, șterge grupul
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
            Conversația, membrii și invitațiile în așteptare dispar odată cu grupul. Nu se poate
            anula.
          </p>
        </div>
      </DrawerContent>
    </Drawer>
  );
}
