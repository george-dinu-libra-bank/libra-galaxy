import { notFound } from "next/navigation";
import { Building2, User } from "lucide-react";
import { ETICHETA_STARE, obtineFirul } from "@/lib/data/investigatii";
import { Banda } from "@/components/ui/banda";
import { RaspundeInvestigatie } from "@/components/investigatii/raspunde-investigatie";
import { cn } from "@/lib/utils";

export const dynamic = "force-dynamic";

/**
 * Firul de discuție cu banca, pe partea clientului.
 *
 * Se vede doar ce a scris banca și ce a răspuns el. Mesajele interne — citirea
 * structurată a răspunsului și analiza pentru administrator — sunt filtrate în
 * backend, nu aici: un filtru pe client ar însemna că datele au ajuns oricum
 * până la browser.
 */

const STARI_INCHISE = ["rezolvat", "escalat", "inchis"];

export default async function PaginaInvestigatieClient({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const fir = await obtineFirul(id);

  // Un dosar care nu e al tău arată exact ca unul care nu există.
  if (!fir) notFound();

  const inchisa = STARI_INCHISE.includes(fir.caz.stare);
  const poateRaspunde = fir.caz.stare === "asteptam_clientul";

  return (
    // Acelasi container ca restul ecranelor de client (/sesizari, /setari):
    // fara el pagina se intindea pe toata latimea ferestrei, iar randurile de
    // text ajungeau imposibil de urmarit cu ochiul de la un capat la altul.
    <div className="mx-auto flex w-full max-w-[440px] flex-col gap-5 px-6 pb-6 pt-8 sm:max-w-2xl">
      <div>
        <h1 className="text-[26px] font-bold leading-8 tracking-[-0.02em] text-ink">
          Mesaj de la bancă
        </h1>
        <p className="mt-1.5 max-w-2xl text-[15px] leading-[22px] text-ink-soft">
          Avem nevoie de o lămurire în legătură cu câteva plăți de pe contul tău.
        </p>
      </div>

      {inchisa ? (
        <Banda ton="info">
          Discuția s-a încheiat ({ETICHETA_STARE[fir.caz.stare].toLowerCase()}). Dacă mai ai
          nelămuriri, ne poți scrie din secțiunea de sesizări.
        </Banda>
      ) : null}

      <ol className="flex flex-col gap-3">
        {fir.mesaje.map((mesaj) => {
          const eBanca = mesaj.autor === "banca";
          const Icoana = eBanca ? Building2 : User;

          return (
            <li
              key={mesaj.id}
              className={cn(
                "rounded-card border p-4",
                eBanca ? "border-primary-100 bg-primary-50/40" : "border-line bg-surface",
              )}
            >
              <div className="flex items-center justify-between gap-3">
                <span
                  className={cn(
                    "flex items-center gap-1.5 text-[12px] font-semibold",
                    eBanca ? "text-primary-700" : "text-ink",
                  )}
                >
                  <Icoana size={14} strokeWidth={1.75} aria-hidden />
                  {eBanca ? "Galaxy Bank" : "Tu"}
                </span>
                <time dateTime={mesaj.creat_la} className="text-[11px] tabular text-ink-faint">
                  {new Date(mesaj.creat_la).toLocaleString("ro-RO", {
                    day: "2-digit",
                    month: "2-digit",
                    year: "numeric",
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </time>
              </div>

              <p className="mt-2 whitespace-pre-wrap text-[14px] leading-[21px] text-ink">
                {mesaj.text}
              </p>
            </li>
          );
        })}
      </ol>

      {poateRaspunde ? <RaspundeInvestigatie idCaz={id} /> : null}

      {!poateRaspunde && !inchisa ? (
        <Banda ton="info">
          Ți-am primit răspunsul. Un coleg îl citește și revine cu un mesaj.
        </Banda>
      ) : null}
    </div>
  );
}
