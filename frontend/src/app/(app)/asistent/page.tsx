import type { Metadata } from "next";
import { Sparkles } from "lucide-react";

export const metadata: Metadata = {
  title: "Asistent · Libra",
};

/** Intrebari la care va raspunde asistentul, odata legat la backend. */
const EXEMPLE = [
  "Cât am cheltuit luna asta pe mâncare?",
  "Care sunt plățile mele recurente?",
  "Cât mi-a rămas până la salariu?",
];

/**
 * Ecranul asistentului.
 *
 * Deocamdata doar locul din navigatie: reasoning-ul sta in agentii Python din
 * spatele FastAPI (ARCHITECTURE.md 3.5 si 15), care nu exista inca in proiect.
 * Pagina spune asta pe fata, in loc sa simuleze o conversatie care n-are cu
 * cine sa vorbeasca.
 */
export default function AsistentPage() {
  return (
    <div className="mx-auto w-full max-w-[440px] px-6 pb-6 pt-8 sm:max-w-2xl">
      <h1 className="text-xl font-bold tracking-[-0.02em] text-ink">Asistent</h1>
      <p className="mt-1 text-[13px] text-ink-faint">
        Întrebări despre banii tăi, în cuvintele tale.
      </p>

      <section className="hero-gradient mt-6 rounded-card px-5 py-8 text-center shadow-md">
        <span className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-white/15">
          <Sparkles size={26} strokeWidth={1.75} aria-hidden className="text-white" />
        </span>

        <p className="mt-4 text-[17px] font-semibold text-white">În lucru</p>
        <p className="mx-auto mt-1 max-w-[280px] text-[13px] leading-[19px] text-primary-100">
          Asistentul se conectează la partea de agenți din backend. Până atunci, ecranul
          e doar rezervat.
        </p>
      </section>

      <h2 className="mt-8 text-lg font-semibold text-ink">Ce va putea răspunde</h2>

      <div className="mt-4 overflow-hidden rounded-card bg-surface shadow-sm">
        {EXEMPLE.map((exemplu, i) => (
          <p
            key={exemplu}
            className={`px-4 py-3.5 text-[15px] leading-[22px] text-ink-soft ${
              i === EXEMPLE.length - 1 ? "" : "border-b border-line"
            }`}
          >
            „{exemplu}"
          </p>
        ))}
      </div>
    </div>
  );
}
