import { Lock, Wallet } from "lucide-react";
import { DeschideContDrawer } from "@/components/dashboard/deschide-cont-drawer";
import { MeniuCont } from "@/components/dashboard/meniu-cont";
import type { ContBancar } from "@/lib/data/conturi";
import { formateazaIban, formateazaSuma } from "@/lib/utils";

/**
 * Conturile bancare ale utilizatorului, cu soldul fiecaruia.
 *
 * Contul principal se marcheaza dupa `estePrincipal` (IBAN-ul din
 * `profiles.iban_cont`), nu dupa pozitia in lista. Pana acum eticheta statea pe
 * `i === 0` din lista ordonata dupa `creat_la` — coincidea, pana in ziua in care
 * cineva sterge un cont vechi.
 */
export function ListaConturi({ conturi }: { conturi: ContBancar[] }) {
  return (
    <section className="mt-8">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-ink">Conturile mele</h2>
        <DeschideContDrawer />
      </div>

      {conturi.length === 0 ? (
        <p className="mt-4 rounded-card bg-surface p-6 text-center text-[15px] text-ink-faint shadow-sm">
          Nu ai niciun cont bancar. Deschide unul ca să poți trimite și primi bani.
        </p>
      ) : (
        <div className="mt-4 flex flex-col gap-3">
          {conturi.map((cont, i) => (
            <article
              key={cont.id}
              className="animate-fade-up rounded-card bg-surface p-4 shadow-sm"
              style={{
                animationDelay: `${i * 40}ms`,
                // Acelasi tratament ca pe cardurile bancare
                // (components/carduri/lista-carduri.tsx): un cont inghetat de
                // banca aratase pana acum exact ca unul normal, iar omul afla
                // abia cand incerca un transfer si primea CONT_BLOCAT.
                opacity: cont.blocatDeBanca ? 0.7 : 1,
              }}
            >
              <div className="flex items-center gap-3">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary-50">
                  <Wallet size={18} strokeWidth={1.75} aria-hidden className="text-primary-600" />
                </span>

                <div className="min-w-0 flex-1">
                  <p className="truncate text-[15px] font-semibold text-ink">{cont.nume}</p>
                  {cont.estePrincipal ? (
                    <p className="text-[12.5px] text-ink-faint">Cont principal</p>
                  ) : null}
                </div>

                <p className="tabular shrink-0 text-[17px] font-bold text-ink">
                  {formateazaSuma(cont.sold, cont.valuta)}
                </p>

                <MeniuCont cont={cont} />
              </div>

              {cont.blocatDeBanca ? (
                <p className="mt-2 inline-flex items-center gap-1.5 rounded-full bg-danger/10 px-2.5 py-1 text-[11.5px] font-medium text-danger">
                  <Lock size={12} strokeWidth={1.75} aria-hidden />
                  Blocat de bancă
                </p>
              ) : null}

              <p className="tabular mt-3 flex items-center gap-2 truncate text-[12.5px] tracking-[0.02em] text-ink-faint">
                {formateazaIban(cont.iban)}
                <span className="rounded-full bg-muted px-1.5 py-0.5 text-[10.5px] font-semibold text-ink-soft">
                  {cont.valuta}
                </span>
              </p>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
