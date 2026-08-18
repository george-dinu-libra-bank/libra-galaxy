"use client";

import { Mail } from "lucide-react";
import { useEffect, useState, useTransition } from "react";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { Camp } from "@/components/ui/camp";
import { Drawer, DrawerContent, DrawerTrigger } from "@/components/ui/drawer";
import { trimiteResetareParola } from "@/lib/actions/auth";

/**
 * Resetarea parolei nu merita o pagina proprie (DESIGN.md 8.1) — un singur
 * camp si un buton, deci sta intr-un drawer peste ecranul de login.
 */
export function ResetareParolaDrawer({ emailInitial = "" }: { emailInitial?: string }) {
  const [deschis, setDeschis] = useState(false);
  const [email, setEmail] = useState(emailInitial);
  const [rezultat, setRezultat] = useState<{ eroare?: string; mesaj?: string }>({});
  const [seTrimite, startTransition] = useTransition();

  // Preia emailul deja tastat in formularul de login la fiecare deschidere.
  useEffect(() => {
    if (deschis) {
      setEmail(emailInitial);
      setRezultat({});
    }
  }, [deschis, emailInitial]);

  function trimite() {
    startTransition(async () => {
      setRezultat(await trimiteResetareParola(email));
    });
  }

  return (
    <Drawer open={deschis} onOpenChange={setDeschis}>
      <DrawerTrigger className="rounded text-[13px] font-medium text-primary-600 transition-colors hover:text-primary-700 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25">
        Ai uitat parola?
      </DrawerTrigger>

      <DrawerContent
        title="Reseteaza parola"
        description="Iti trimitem pe email un link de resetare, valabil o ora."
        footer={
          <Button
            onClick={trimite}
            loading={seTrimite}
            disabled={Boolean(rezultat.mesaj)}
            className="w-full"
          >
            {rezultat.mesaj ? "Email trimis" : "Trimite linkul"}
          </Button>
        }
      >
        <div className="flex flex-col gap-4">
          {rezultat.eroare ? <Banda ton="eroare">{rezultat.eroare}</Banda> : null}
          {rezultat.mesaj ? <Banda ton="succes">{rezultat.mesaj}</Banda> : null}

          <Camp
            eticheta="Email"
            icoana={Mail}
            type="email"
            inputMode="email"
            autoComplete="email"
            placeholder="nume@exemplu.ro"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            disabled={Boolean(rezultat.mesaj)}
            ajutor="Foloseste adresa cu care ti-ai deschis contul."
          />
        </div>
      </DrawerContent>
    </Drawer>
  );
}
