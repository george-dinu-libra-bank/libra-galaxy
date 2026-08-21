"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { ShieldCheck } from "lucide-react";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { Drawer, DrawerContent } from "@/components/ui/drawer";
import { forteazaVerificare } from "@/lib/actions/admin-verificari";

/**
 * Marcheaza manual un cont ca verificat, fara nicio dovada (OCR/selfie).
 *
 * Separat de `DeciziaCazului`: acolo exista poze de comparat, aici nu exista
 * nimic — e o decizie de alta natura ("las contul asta sa treaca, desi n-a
 * trimis nimic"), asa ca merita propriul buton si propriul text de confirmare,
 * nu reciclat din fluxul cu dovezi.
 */
export function ForteazaVerificare({ userId, nume }: { userId: string; nume: string }) {
  const router = useRouter();
  const [deschis, setDeschis] = useState(false);
  const [eroare, setEroare] = useState<string | null>(null);
  const [seTrimite, startTransition] = useTransition();

  function confirma() {
    setEroare(null);
    startTransition(async () => {
      const rezultat = await forteazaVerificare(userId);
      if (rezultat.eroare) {
        setEroare(rezultat.eroare);
        return;
      }
      setDeschis(false);
      router.refresh();
    });
  }

  return (
    <>
      <Button
        varianta="ghost"
        iconaStanga={<ShieldCheck size={16} strokeWidth={1.75} aria-hidden />}
        onClick={() => setDeschis(true)}
      >
        Marchează ca verificat
      </Button>

      <Drawer
        open={deschis}
        onOpenChange={(deschis) => {
          if (!deschis && !seTrimite) {
            setDeschis(false);
            setEroare(null);
          }
        }}
        dismissible={!seTrimite}
      >
        <DrawerContent
          title="Marchezi contul ca verificat?"
          description={`${nume} nu a trimis buletin sau selfie — nu exista nicio dovada de comparat. Contul va putea folosi aplicatia normal.`}
          cuInchidere={!seTrimite}
          footer={
            <Button varianta="primary" className="w-full" loading={seTrimite} onClick={confirma}>
              Da, marchează ca verificat
            </Button>
          }
        >
          {eroare ? <Banda ton="eroare">{eroare}</Banda> : null}
        </DrawerContent>
      </Drawer>
    </>
  );
}
