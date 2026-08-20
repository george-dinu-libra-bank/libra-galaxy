"use client";

import { useRouter } from "next/navigation";
import { LogOut } from "lucide-react";
import { useState, useTransition } from "react";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { Drawer, DrawerClose, DrawerContent, DrawerTrigger } from "@/components/ui/drawer";
import { iesiDinGrup } from "@/lib/actions/grupuri";

/**
 * Iesirea din grup, cu confirmare. Mesajele scrise raman in grup — se pierde
 * doar accesul la el, care se poate recapata cu acelasi cod.
 */
export function IesiDinGrupDrawer({ idGrup, nume }: { idGrup: number; nume: string }) {
  const router = useRouter();
  const [deschis, setDeschis] = useState(false);
  const [eroare, setEroare] = useState<string | null>(null);
  const [sePleaca, startTransition] = useTransition();

  function iesi() {
    setEroare(null);

    startTransition(async () => {
      const rezultat = await iesiDinGrup(idGrup);

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
        <LogOut size={18} strokeWidth={1.75} aria-hidden />
        Ieși din grup
      </DrawerTrigger>

      <DrawerContent
        title="Ieși din grup?"
        description={`Nu vei mai vedea conversația și soldul grupului „${nume}".`}
        footer={
          <div className="flex flex-col gap-2">
            <Button varianta="danger" className="w-full" loading={sePleaca} onClick={iesi}>
              Da, ies din grup
            </Button>
            <DrawerClose asChild>
              <Button varianta="ghost" className="w-full">
                Rămân în grup
              </Button>
            </DrawerClose>
          </div>
        }
      >
        <div className="flex flex-col gap-4">
          {eroare ? <Banda ton="eroare">{eroare}</Banda> : null}

          <p className="text-[15px] leading-[22px] text-ink-soft">
            Mesajele tale rămân în grup. Poți reveni oricând cu același cod de acces,
            dacă îl mai ai.
          </p>
        </div>
      </DrawerContent>
    </Drawer>
  );
}
