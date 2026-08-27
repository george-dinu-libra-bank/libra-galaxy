"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { Send } from "lucide-react";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { raspundeInvestigatie } from "@/lib/actions/investigatii";

/**
 * Caseta prin care clientul răspunde băncii.
 *
 * Fără câmpuri de bifat și fără formular: omul scrie cu cuvintele lui, iar
 * transformarea în câmpuri comparabile o face un agent, pe partea băncii. Un
 * formular ar fi fost mai ușor de citit pentru noi și mai greu de completat
 * pentru cineva speriat că i s-au luat banii.
 */
export function RaspundeInvestigatie({ idCaz }: { idCaz: string }) {
  const router = useRouter();
  const [text, setText] = useState("");
  const [seTrimite, porneste] = useTransition();
  const [eroare, setEroare] = useState<string | null>(null);

  function trimite() {
    setEroare(null);
    porneste(async () => {
      const { eroare: err } = await raspundeInvestigatie(idCaz, text);
      if (err) {
        setEroare(err);
        return;
      }
      setText("");
      router.refresh();
    });
  }

  return (
    <section className="flex flex-col gap-3 rounded-card border border-line bg-surface p-5">
      <div>
        <h2 className="text-[15px] font-semibold text-ink">Răspunsul tău</h2>
        <p className="mt-1 text-[13px] leading-[19px] text-ink-soft">
          Scrie cu cuvintele tale. Nu-ți cerem niciodată parola, PIN-ul sau codurile primite
          prin SMS — dacă cineva ți le cere, nu suntem noi.
        </p>
      </div>

      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={7}
        maxLength={4000}
        aria-label="Răspunsul tău"
        placeholder="Ex.: nu am făcut eu plățile alea, eram la muncă și cardul era la mine."
        className="rounded-field border border-line bg-surface p-3 text-[14px] leading-[21px] text-ink outline-none transition-colors focus:border-primary-500"
      />

      {eroare ? <Banda ton="eroare">{eroare}</Banda> : null}

      <Button
        marime="sm"
        className="w-fit"
        loading={seTrimite}
        disabled={!text.trim()}
        onClick={trimite}
        iconaStanga={<Send size={16} strokeWidth={1.75} aria-hidden />}
      >
        Trimite răspunsul
      </Button>
    </section>
  );
}
