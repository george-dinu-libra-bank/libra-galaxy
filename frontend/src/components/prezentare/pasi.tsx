import { IdCard, Landmark, Mail } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { AntetSectiune } from "./antet";
import { RamaTelefon } from "./rama-telefon";
import { CAPTURI } from "./capturi";

const PASI: { icoana: LucideIcon; titlu: string; text: string }[] = [
  {
    icoana: Mail,
    titlu: "Îți faci cont",
    text: "Email, parolă și datele de bază. Fără hârtii și fără drum la ghișeu.",
  },
  {
    icoana: IdCard,
    titlu: "Îți verifici identitatea",
    text: "Fotografiezi buletinul direct din aplicație. Dacă poza e prea întunecată sau mișcată, ți-o spune pe loc, înainte să o trimiți.",
  },
  {
    icoana: Landmark,
    titlu: "Primești IBAN-ul",
    text: "Contul curent e activ, cu IBAN românesc. De aici poți trimite și primi bani.",
  },
];

export function Pasi() {
  return (
    <section id="pasi" className="scroll-mt-20 border-y border-line bg-surface/60">
      <div className="mx-auto grid w-full max-w-6xl gap-10 px-5 py-16 sm:px-8 lg:grid-cols-[1fr_320px] lg:items-center">
        <div>
          <AntetSectiune
            supratitlu="Cum începi"
            titlu="Cont în trei pași"
            subtitlu="Verificarea identității e singurul pas care cere puțină atenție — restul durează cât scrii un email."
          />

          <ol className="stagger mt-8 flex flex-col gap-4">
            {PASI.map(({ icoana: Icoana, titlu, text }, index) => (
              <li
                key={titlu}
                style={{ "--i": index } as React.CSSProperties}
                className="flex items-start gap-4 rounded-card border border-line bg-surface p-5 shadow-sm"
              >
                <span className="relative flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary-50">
                  <Icoana size={20} strokeWidth={1.75} aria-hidden className="text-primary-600" />
                  <span className="tabular absolute -right-1.5 -top-1.5 flex h-5 w-5 items-center justify-center rounded-full bg-primary-600 text-[11px] font-semibold text-white">
                    {index + 1}
                  </span>
                </span>
                <div>
                  <h3 className="text-[16px] font-semibold leading-[22px] text-ink">{titlu}</h3>
                  <p className="mt-1.5 text-[14px] leading-[21px] text-ink-soft">{text}</p>
                </div>
              </li>
            ))}
          </ol>
        </div>

        <RamaTelefon captura={CAPTURI.inregistrare} className="mx-auto lg:mx-0" />
      </div>
    </section>
  );
}
