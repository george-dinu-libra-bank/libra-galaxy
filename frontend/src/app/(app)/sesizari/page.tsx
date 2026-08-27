import type { Metadata } from "next";
import { LifeBuoy } from "lucide-react";
import { FormularSesizare } from "@/components/sesizari/formular-sesizare";
import { obtineSesizarileMele } from "@/lib/data/sesizari";
import { dataSiOra } from "@/lib/momente";
import { cn } from "@/lib/utils";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Sesizări · Galaxy Bank",
};

const ETICHETE_STATUS: Record<string, { text: string; clasa: string }> = {
  deschisa: { text: "Trimisă", clasa: "bg-warning/10 text-warning" },
  in_lucru: { text: "În lucru", clasa: "bg-primary-500/10 text-primary-600" },
  rezolvata: { text: "Rezolvată", clasa: "bg-success/10 text-success" },
};

/**
 * `?subiect=` si `?rezumat=` pre-completeaza formularul — asa ajunge aici cineva
 * trimis din conversatia cu asistentul, cu textul deja scris. Se completeaza,
 * nu se trimite: apasarea ramane a omului.
 */
export default async function PaginaSesizari({
  searchParams,
}: {
  searchParams: Promise<{ subiect?: string; rezumat?: string }>;
}) {
  const [{ subiect, rezumat }, sesizari] = await Promise.all([
    searchParams,
    obtineSesizarileMele(),
  ]);

  const areDejaDeschisa = sesizari.some((s) => s.status !== "rezolvata");

  return (
    <div className="mx-auto flex w-full max-w-[440px] flex-col gap-5 px-6 pb-6 pt-8 sm:max-w-2xl">
      <div>
        <h1 className="flex items-center gap-2 text-xl font-bold tracking-[-0.02em] text-ink">
          <LifeBuoy size={20} strokeWidth={1.75} aria-hidden className="text-primary-600" />
          Sesizări
        </h1>
        <p className="mt-1 text-[13px] text-ink-faint">
          Scrie-i băncii și urmărește răspunsul.
        </p>
      </div>

      <FormularSesizare
        subiectInitial={subiect?.slice(0, 200) ?? ""}
        rezumatInitial={rezumat?.slice(0, 4000) ?? ""}
        areDejaDeschisa={areDejaDeschisa}
      />

      {sesizari.length > 0 ? (
        <section className="flex flex-col gap-3">
          <h2 className="text-[15px] font-semibold text-ink">Ce ai trimis</h2>

          {sesizari.map((s) => {
            const eticheta = ETICHETE_STATUS[s.status] ?? ETICHETE_STATUS.deschisa;
            return (
              <article key={s.id} className="rounded-card border border-line bg-surface p-4">
                <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
                  <h3 className="text-[14px] font-semibold text-ink">{s.subiect}</h3>
                  <span
                    className={cn(
                      "rounded-full px-2 py-0.5 text-[11px] font-medium",
                      eticheta.clasa,
                    )}
                  >
                    {eticheta.text}
                  </span>
                  <span className="text-[12px] text-ink-faint">{dataSiOra(s.creat_la)}</span>
                </div>

                <p className="mt-2 whitespace-pre-line text-[13px] leading-[19px] text-ink-soft">
                  {s.rezumat}
                </p>

                {s.raspuns ? (
                  <div className="mt-3 rounded-field bg-muted p-3">
                    <p className="text-[12px] font-semibold text-ink-faint">Răspunsul băncii</p>
                    <p className="mt-1 whitespace-pre-line text-[13px] leading-[19px] text-ink-soft">
                      {s.raspuns}
                    </p>
                  </div>
                ) : null}
              </article>
            );
          })}
        </section>
      ) : null}
    </div>
  );
}
