"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { IdCard } from "lucide-react";
import { BuletinCapture } from "@/components/auth/buletin-capture";
import { Banda } from "@/components/ui/banda";
import { Drawer, DrawerContent } from "@/components/ui/drawer";
import { trimiteBuletinUlterior } from "@/lib/actions/identitate";

/**
 * Contul exista deja fara buletin (userul a ales sa-l trimita mai tarziu la
 * inregistrare, vezi register-form.tsx). Refoloseste acelasi pas de captura +
 * OCR, doar ca trimiterea merge acum prin sesiunea reala a userului, nu prin
 * cheia interna a lui Next.js.
 */
export function VerificaIdentitateBanner() {
  const router = useRouter();
  const [deschis, setDeschis] = useState(false);
  const [rezultat, setRezultat] = useState<"verified" | "pending_review" | null>(null);
  const [eroare, setEroare] = useState<string | null>(null);
  const [, startTransition] = useTransition();

  function trimite(fisier: File, cnp: string) {
    setEroare(null);
    startTransition(async () => {
      const status = await trimiteBuletinUlterior(fisier, cnp);

      if (status === "eroare") {
        setEroare("Nu am putut trimite buletinul. Încearcă din nou.");
        return;
      }

      setRezultat(status);
      router.refresh();
    });
  }

  if (rezultat === "verified") {
    return <Banda ton="succes">Cont verificat — mulțumim!</Banda>;
  }

  if (rezultat === "pending_review") {
    return (
      <Banda ton="info">
        Am primit buletinul. Verificarea este în curs de revizuire manuală.
      </Banda>
    );
  }

  return (
    <>
      <Banda ton="info">
        Contul tău este activ, dar nu ai trimis încă buletinul.
        <button
          type="button"
          onClick={() => setDeschis(true)}
          className="ml-1.5 rounded font-semibold text-primary-600 underline hover:text-primary-700 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
        >
          Trimite-l acum
        </button>
      </Banda>

      <Drawer open={deschis} onOpenChange={setDeschis}>
        <DrawerContent
          title="Verificarea identității"
          description="Fotografiază buletinul ca să-ți confirmăm contul."
          ascundeTitlu
        >
          <div className="mb-1 flex items-center gap-2 text-[15px] font-semibold text-ink">
            <IdCard size={18} strokeWidth={1.75} aria-hidden className="text-primary-600" />
            Verificarea identității
          </div>

          {eroare ? (
            <div className="mb-3">
              <Banda ton="eroare">{eroare}</Banda>
            </div>
          ) : null}

          <BuletinCapture onFinalizat={trimite} />
        </DrawerContent>
      </Drawer>
    </>
  );
}
