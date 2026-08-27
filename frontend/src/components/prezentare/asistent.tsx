"use client";

import { Sparkles, User } from "lucide-react";
import AnimatedList from "@/components/reactbits/AnimatedList";
import { useMiscareRedusa } from "@/hooks/use-miscare-redusa";
import { AntetSectiune } from "./antet";
import { RamaTelefon } from "./rama-telefon";
import { CAPTURI } from "./capturi";

type Mesaj = { de_la: "tu" | "asistent"; text: string };

const CONVERSATIE: Mesaj[] = [
  { de_la: "tu", text: "Cât am cheltuit pe mâncare în ultimele trei luni?" },
  {
    de_la: "asistent",
    text: "4.320,00 RON, adică 1.440,00 RON pe lună. Cel mai mult în mai, cu 1.680,00 RON.",
  },
  { de_la: "tu", text: "Și abonamentele care mi se iau lunar?" },
  {
    de_la: "asistent",
    text: "Am găsit patru plăți recurente, în total 213,00 RON pe lună. Vrei lista?",
  },
];

/**
 * Traseul unei intrebari, exact cel din ARCHITECTURE.md 15: modelul cere o
 * capabilitate, aplicatia decide daca are voie si de unde vin datele.
 */
const TRASEU = [
  "Next.js trimite întrebarea",
  "FastAPI stabilește cine ești",
  "Agentul alege unealta potrivită",
  "Unealta cheamă serviciul",
  "Repository-ul citește din PostgreSQL",
];

function Bula({ mesaj }: { mesaj: Mesaj }) {
  const eAsistent = mesaj.de_la === "asistent";
  const Icoana = eAsistent ? Sparkles : User;

  return (
    <div className={`flex items-start gap-2.5 ${eAsistent ? "" : "flex-row-reverse"}`}>
      <span
        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${
          eAsistent ? "bg-primary-50" : "bg-muted"
        }`}
      >
        <Icoana
          size={16}
          strokeWidth={1.75}
          aria-hidden
          className={eAsistent ? "text-primary-600" : "text-ink-faint"}
        />
      </span>
      <p
        className={`max-w-[80%] rounded-card px-4 py-2.5 text-[14px] leading-[21px] ${
          eAsistent
            ? "bg-primary-50 text-primary-900"
            : "border border-line bg-surface text-ink-soft"
        }`}
      >
        <span className="sr-only">{eAsistent ? "Asistentul: " : "Tu: "}</span>
        {mesaj.text}
      </p>
    </div>
  );
}

export function Asistent() {
  const miscareRedusa = useMiscareRedusa();
  const bule = CONVERSATIE.map((mesaj) => <Bula key={mesaj.text} mesaj={mesaj} />);

  return (
    <section id="asistent" className="mx-auto w-full max-w-6xl scroll-mt-20 px-5 py-16 sm:px-8">
      <AntetSectiune
        supratitlu="Asistent"
        titlu="Întrebi în română, răspunsul vine din datele tale"
        subtitlu="Modelul nu are acces la baza de date. Cere o capabilitate anume, iar aplicația decide dacă are voie și de unde ia datele."
      />

      <div className="mt-8 grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px] lg:items-start">
        <div className="rounded-card border border-line bg-surface p-6 shadow-sm">
          {miscareRedusa ? (
            <div className="flex flex-col gap-3">{bule}</div>
          ) : (
            <AnimatedList items={bule} showGradients={false} />
          )}

          <div className="mt-6 border-t border-line pt-5">
            <p className="text-[12.5px] font-semibold uppercase tracking-[0.08em] text-ink-faint">
              Ce se întâmplă dedesubt
            </p>
            <ol className="mt-3 flex flex-col gap-2">
              {TRASEU.map((pas, index) => (
                <li key={pas} className="flex items-center gap-3 text-[13.5px] text-ink-soft">
                  <span className="tabular flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-muted text-[11px] font-semibold text-ink-faint">
                    {index + 1}
                  </span>
                  {pas}
                </li>
              ))}
            </ol>
            <p className="mt-4 text-[12.5px] leading-[18px] text-ink-faint">
              Niciun pas nu lasă modelul să scrie SQL și niciunul nu-l lasă să aleagă în numele cui
              întreabă.
            </p>
          </div>
        </div>

        <RamaTelefon captura={CAPTURI.asistent} className="mx-auto lg:mx-0" />
      </div>
    </section>
  );
}
