"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { inchideInvestigatie } from "@/lib/actions/investigatii";
import type { RezultatInvestigatie } from "@/lib/data/investigatii";
import { cn } from "@/lib/utils";

/**
 * Încheierea investigației: administratorul alege urmarea și scrie de ce.
 *
 * Niciuna dintre cele patru urmări nu atinge contul. Chiar și „Deblochează
 * contul" doar consemnează decizia — deblocarea propriu-zisă e butonul din
 * ecranul contului, apăsat separat. Textul de sub opțiune spune asta pe față,
 * ca nimeni să nu creadă că a deblocat pe cineva de aici.
 */

const URMARI: {
  valoare: RezultatInvestigatie;
  eticheta: string;
  explicatie: string;
  ton: "neutru" | "bun" | "grav";
}[] = [
  {
    valoare: "fara_masuri",
    eticheta: "Fără măsuri",
    explicatie: "Răspunsul lămurește plățile. Nu se schimbă nimic la cont.",
    ton: "bun",
  },
  {
    valoare: "deblocat",
    eticheta: "De deblocat",
    explicatie:
      "Se consemnează că ai decis deblocarea. Contul se deblochează separat, din ecranul lui.",
    ton: "bun",
  },
  {
    valoare: "sucursala",
    eticheta: "Chemat la sucursală",
    explicatie: "Situația nu se poate lămuri în scris. Clientul vine în persoană.",
    ton: "neutru",
  },
  {
    valoare: "anaf",
    eticheta: "Predat conformității",
    explicatie:
      "Dosarul merge la echipa de conformitate. Sesizarea către o autoritate are procedura ei și nu se face de aici.",
    ton: "grav",
  },
];

const STIL_TON = {
  bun: "border-success/30 bg-success/5",
  neutru: "border-line bg-surface",
  grav: "border-danger/30 bg-danger/5",
} as const;

export function IncheieInvestigatie({ idCaz }: { idCaz: string }) {
  const router = useRouter();
  const [aleasa, setAleasa] = useState<RezultatInvestigatie | null>(null);
  const [nota, setNota] = useState("");
  const [seLucreaza, porneste] = useTransition();
  const [eroare, setEroare] = useState<string | null>(null);

  function incheie() {
    if (!aleasa) return;
    setEroare(null);
    porneste(async () => {
      const { eroare: err } = await inchideInvestigatie(idCaz, aleasa, nota);
      if (err) {
        setEroare(err);
        return;
      }
      router.refresh();
    });
  }

  return (
    <section className="flex flex-col gap-4 rounded-card border border-line bg-surface p-5">
      <div>
        <h2 className="text-[15px] font-semibold text-ink">Încheie investigația</h2>
        <p className="mt-1 max-w-2xl text-[13px] leading-[19px] text-ink-soft">
          Alege urmarea și scrie pe scurt de ce. Rămâne în dosar și se poate citi mai târziu.
        </p>
      </div>

      <div className="grid gap-2 sm:grid-cols-2">
        {URMARI.map((urmare) => {
          const activa = aleasa === urmare.valoare;
          return (
            <button
              key={urmare.valoare}
              type="button"
              aria-pressed={activa}
              onClick={() => setAleasa(activa ? null : urmare.valoare)}
              className={cn(
                "flex flex-col gap-1 rounded-field border p-3 text-left transition-all",
                STIL_TON[urmare.ton],
                activa ? "ring-2 ring-primary-500/40" : "hover:border-primary-300",
              )}
            >
              <span className="text-[14px] font-semibold text-ink">{urmare.eticheta}</span>
              <span className="text-[12px] leading-[17px] text-ink-soft">
                {urmare.explicatie}
              </span>
            </button>
          );
        })}
      </div>

      <div className="flex flex-col gap-1.5">
        <label htmlFor="nota-inchidere" className="text-[13px] font-medium text-ink-soft">
          De ce ai decis așa
        </label>
        <textarea
          id="nota-inchidere"
          value={nota}
          onChange={(e) => setNota(e.target.value)}
          rows={3}
          maxLength={4000}
          placeholder="Ex.: clientul a confirmat plățile și a explicat de ce au fost făcute în aceeași zi."
          className="rounded-field border border-line bg-surface p-3 text-[14px] leading-[21px] text-ink outline-none transition-colors focus:border-primary-500"
        />
      </div>

      {eroare ? <Banda ton="eroare">{eroare}</Banda> : null}

      <Button
        marime="sm"
        className="w-fit"
        loading={seLucreaza}
        disabled={!aleasa}
        onClick={incheie}
      >
        Încheie investigația
      </Button>
    </section>
  );
}
