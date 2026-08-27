"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { Send } from "lucide-react";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { Camp } from "@/components/ui/camp";
import { raspundeSesizare } from "@/lib/actions/admin-suport";

/**
 * Raspunsul administratorului la o sesizare.
 *
 * Doua butoane, fiindca sunt doua situatii diferite: "am rezolvat" inchide
 * cazul, "am preluat" ii spune omului ca cineva se ocupa fara sa pretinda ca
 * s-a terminat. Al doilea exista ca sa nu fie nevoie sa minti ca sa raspunzi.
 */
export function RaspunsSesizare({ idSesizare }: { idSesizare: string }) {
  const router = useRouter();
  const [raspuns, setRaspuns] = useState("");
  const [eroare, setEroare] = useState<string | null>(null);
  const [seTrimite, startTransition] = useTransition();

  const gol = raspuns.trim().length === 0;

  function trimite(status: "in_lucru" | "rezolvata") {
    if (gol) return;
    setEroare(null);
    startTransition(async () => {
      const rezultat = await raspundeSesizare(idSesizare, raspuns, status);
      if (rezultat.eroare) {
        setEroare(rezultat.eroare);
        return;
      }
      setRaspuns("");
      router.refresh();
    });
  }

  return (
    <div className="mt-4 border-t border-line pt-4">
      {eroare ? (
        <div className="mb-3">
          <Banda ton="eroare">{eroare}</Banda>
        </div>
      ) : null}

      <Camp
        eticheta="Răspunsul tău"
        value={raspuns}
        onChange={(e) => setRaspuns(e.target.value)}
        placeholder="Ex. Am verificat plățile semnalate și am deblocat contul."
        maxLength={4000}
        ajutor="Ajunge la client ca notificare, în aplicație."
        autoComplete="off"
      />

      <div className="mt-3 flex flex-col gap-2 sm:flex-row">
        <Button
          marime="sm"
          className="flex-1"
          loading={seTrimite}
          disabled={gol}
          iconaStanga={<Send size={16} strokeWidth={1.75} aria-hidden />}
          onClick={() => trimite("rezolvata")}
        >
          Trimite și închide
        </Button>
        <Button
          varianta="secondary"
          marime="sm"
          className="flex-1"
          loading={seTrimite}
          disabled={gol}
          onClick={() => trimite("in_lucru")}
        >
          Trimite, rămâne în lucru
        </Button>
      </div>
    </div>
  );
}
