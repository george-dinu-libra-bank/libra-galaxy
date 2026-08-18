"use client";

import { useState } from "react";
import { Phone } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Camp } from "@/components/ui/camp";
import {
  Drawer,
  DrawerContent,
  DrawerTrigger,
} from "@/components/ui/drawer";
import { normalizeazaTelefon, validTelefon } from "@/lib/validare";

export function EditeazaTelefonDrawer({
  telefon,
  onSalvat,
}: {
  telefon: string;
  onSalvat: (telefon: string) => void;
}) {
  const [deschis, setDeschis] = useState(false);
  const [valoare, setValoare] = useState(telefon);
  const [eroare, setEroare] = useState<string | null>(null);

  function salveaza() {
    const mesaj = validTelefon(valoare);
    if (mesaj) {
      setEroare(mesaj);
      return;
    }
    onSalvat(normalizeazaTelefon(valoare));
    setDeschis(false);
  }

  return (
    <Drawer
      open={deschis}
      onOpenChange={(v) => {
        setDeschis(v);
        if (v) {
          setValoare(telefon);
          setEroare(null);
        }
      }}
    >
      <DrawerTrigger className="text-[13px] font-semibold text-primary-600 hover:underline">
        Editează
      </DrawerTrigger>

      <DrawerContent
        title="Editează telefonul"
        description="Numărul folosit pentru confirmări și alerte de cont."
        footer={
          <Button className="w-full" onClick={salveaza}>
            Salvează
          </Button>
        }
      >
        <Camp
          eticheta="Telefon"
          icoana={Phone}
          type="tel"
          inputMode="tel"
          value={valoare}
          onChange={(e) => setValoare(e.target.value)}
          eroare={eroare}
          autoComplete="tel"
        />
      </DrawerContent>
    </Drawer>
  );
}
