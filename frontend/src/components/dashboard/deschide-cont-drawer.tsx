"use client";

import { useRouter } from "next/navigation";
import { Plus } from "lucide-react";
import { useState, useTransition } from "react";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { Camp } from "@/components/ui/camp";
import { Drawer, DrawerContent, DrawerTrigger } from "@/components/ui/drawer";
import { deschideCont } from "@/lib/actions/conturi";

/** Sugestii uzuale, ca sa nu ramana campul gol la prima deschidere. */
const SUGESTII = ["Economii", "Cheltuieli", "Vacanță", "Chirie"];

/**
 * Deschiderea unui cont bancar nou. IBAN-ul se genereaza in baza de date;
 * utilizatorul alege doar numele sub care il vede in lista.
 */
export function DeschideContDrawer() {
  const router = useRouter();
  const [deschis, setDeschis] = useState(false);
  const [nume, setNume] = useState("");
  const [eroare, setEroare] = useState<string | null>(null);
  const [seTrimite, startTransition] = useTransition();

  function trimite() {
    setEroare(null);

    startTransition(async () => {
      const rezultat = await deschideCont(nume);

      if (rezultat.eroare) {
        setEroare(rezultat.eroare);
        return;
      }

      setDeschis(false);
      setNume("");
      router.refresh();
    });
  }

  return (
    <Drawer
      open={deschis}
      onOpenChange={(valoare) => {
        setDeschis(valoare);
        if (valoare) setEroare(null);
      }}
    >
      <DrawerTrigger
        aria-label="Deschide un cont nou"
        className="flex h-9 items-center gap-1.5 rounded-full bg-primary-50 px-3 text-[13px] font-semibold text-primary-700 transition-colors hover:bg-primary-100 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
      >
        <Plus size={16} strokeWidth={2} aria-hidden />
        Cont nou
      </DrawerTrigger>

      <DrawerContent
        title="Deschide un cont nou"
        description="Primești un IBAN Galaxy Bank nou, cu sold 0."
        footer={
          <Button className="w-full" loading={seTrimite} onClick={trimite}>
            Deschide contul
          </Button>
        }
      >
        <div className="flex flex-col gap-4">
          {eroare ? <Banda ton="eroare">{eroare}</Banda> : null}

          <Camp
            eticheta="Numele contului"
            placeholder="Ex. Economii"
            value={nume}
            onChange={(e) => setNume(e.target.value)}
            maxLength={60}
            ajutor="Doar pentru tine — îl vezi în lista de conturi."
          />

          <div className="flex flex-wrap gap-2">
            {SUGESTII.map((sugestie) => (
              <button
                key={sugestie}
                type="button"
                onClick={() => setNume(sugestie)}
                className="rounded-full border border-line bg-surface px-3 py-1.5 text-[13px] text-ink-soft transition-colors hover:border-primary-300 hover:bg-primary-50 hover:text-primary-700 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
              >
                {sugestie}
              </button>
            ))}
          </div>
        </div>
      </DrawerContent>
    </Drawer>
  );
}
