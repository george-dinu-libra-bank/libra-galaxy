"use client";

import { useState, useTransition } from "react";
import { Check, Send } from "lucide-react";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { trimiteSesizare } from "@/lib/actions/suport";

/**
 * Sesizarea pregatita de asistent, cu butonul care o trimite.
 *
 * Textul aratat aici e chiar cel care pleaca la banca — nu o repovestire.
 * Asistentul l-a compus, dar nu l-a trimis: apasarea e a clientului, dupa ce
 * citeste ce se scrie in numele lui.
 */
export function CardSesizare({ subiect, rezumat }: { subiect: string; rezumat: string }) {
  const [trimisa, setTrimisa] = useState(false);
  const [dejaDeschisa, setDejaDeschisa] = useState(false);
  const [eroare, setEroare] = useState<string | null>(null);
  const [seTrimite, startTransition] = useTransition();

  function trimite() {
    setEroare(null);
    startTransition(async () => {
      const rezultat = await trimiteSesizare(subiect || "Sesizare din asistent", rezumat);
      if (rezultat.eroare) {
        setEroare(rezultat.eroare);
        return;
      }
      setDejaDeschisa(rezultat.creataAcum === false);
      setTrimisa(true);
    });
  }

  return (
    <div className="w-full max-w-[85%] rounded-card border border-line bg-surface p-4">
      <h3 className="text-[13px] font-semibold text-ink">Sesizare către bancă</h3>
      <p className="mt-1 text-[12px] text-ink-faint">
        Asta se trimite în numele tău. Citește înainte de a apăsa.
      </p>

      <p className="mt-3 whitespace-pre-line rounded-field bg-muted p-3 text-[13px] leading-[19px] text-ink-soft">
        {rezumat}
      </p>

      {eroare ? (
        <div className="mt-3">
          <Banda ton="eroare">{eroare}</Banda>
        </div>
      ) : null}

      {trimisa ? (
        <p className="mt-3 flex items-center gap-1.5 text-[13px] font-semibold text-success">
          <Check size={15} strokeWidth={2} aria-hidden />
          {dejaDeschisa
            ? "Ai deja o sesizare deschisă — cazul tău e la un coleg."
            : "Trimisă. Vei primi răspunsul ca notificare."}
        </p>
      ) : (
        <Button
          marime="sm"
          className="mt-3 w-full"
          loading={seTrimite}
          iconaStanga={<Send size={16} strokeWidth={1.75} aria-hidden />}
          onClick={trimite}
        >
          Trimite sesizarea către bancă
        </Button>
      )}
    </div>
  );
}
