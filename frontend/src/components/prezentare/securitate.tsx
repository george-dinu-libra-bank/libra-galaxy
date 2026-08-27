import { Database, FileSearch, Lock, ScanFace, ShieldCheck, SpellCheck } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import StarBorder from "@/components/reactbits/StarBorder";
import { AntetSectiune } from "./antet";
import { Captura } from "./captura";
import { CAPTURI } from "./capturi";

const MASURI: { icoana: LucideIcon; titlu: string; text: string }[] = [
  {
    icoana: Database,
    titlu: "Fiecare vede doar ce e al lui",
    text: "Regulile de acces stau în baza de date (RLS), nu în interfață. Un ecran care greșește tot nu poate citi contul altcuiva.",
  },
  {
    icoana: Lock,
    titlu: "Banii se mișcă doar prin servicii",
    text: "Validare, limite, execuție atomică și eveniment de audit. Nicio pagină nu scade un sold direct.",
  },
  {
    icoana: ScanFace,
    titlu: "Verificarea identității",
    text: "Ce nu confirmă verificarea automată ajunge într-o coadă de revizuit, cu decizie luată de un om.",
  },
  {
    icoana: FileSearch,
    titlu: "Tranzacții semnalate",
    text: "Plățile care ies din tipar sunt marcate și așteaptă o privire, cu motivul semnalării scris pe fiecare rând.",
  },
  {
    icoana: SpellCheck,
    titlu: "Cuvinte sensibile",
    text: "Detaliile transferurilor sunt scanate după o listă editabilă din panoul de administrare.",
  },
  {
    icoana: ShieldCheck,
    titlu: "Chei care nu ajung în browser",
    text: "Credențialele privilegiate rămân în backend. Browserul primește doar cheia publică.",
  },
];

export function Securitate() {
  return (
    <section id="securitate" className="scroll-mt-20 border-t border-line bg-surface/60">
      <div className="mx-auto w-full max-w-6xl px-5 py-16 sm:px-8">
        <AntetSectiune
          supratitlu="Securitate și administrare"
          titlu="Regulile stau cât mai aproape de date"
          subtitlu="Verificările din interfață fac experiența plăcută. Cele din bază și din servicii sunt cele care contează."
        />

        <div className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {MASURI.map(({ icoana: Icoana, titlu, text }) => (
            <div
              key={titlu}
              className="rounded-card border border-line bg-surface p-5 shadow-sm"
            >
              <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary-50">
                <Icoana size={20} strokeWidth={1.75} aria-hidden className="text-primary-600" />
              </span>
              <h3 className="mt-4 text-[16px] font-semibold leading-[22px] text-ink">{titlu}</h3>
              <p className="mt-2 text-[14px] leading-[21px] text-ink-soft">{text}</p>
            </div>
          ))}
        </div>

        {/* Scanteia din StarBorder e animatie CSS, deci regula globala de
            `prefers-reduced-motion` din globals.css o opreste singura. */}
        <StarBorder
          as="div"
          className="mt-10 block w-full"
          speed="8s"
          thickness={2}
          innerClassName="px-6 py-8 sm:px-8"
        >
          <h3 className="text-[18px] font-semibold leading-6 text-ink">Panoul de administrare</h3>
          <p className="mt-2 max-w-[60ch] text-[14px] leading-[21px] text-ink-soft">
            Verificări de identitate, tranzacții semnalate, conturi, dosare de credit și lista de
            cuvinte sensibile — toate într-un singur loc, separat de aplicația clientului.
          </p>

          <div className="mt-6 grid gap-4 sm:grid-cols-2">
            <Captura {...CAPTURI.suspecte} />
            <Captura {...CAPTURI.securitate} />
          </div>
        </StarBorder>
      </div>
    </section>
  );
}
