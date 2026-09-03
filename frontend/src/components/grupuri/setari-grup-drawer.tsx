"use client";

import { useRouter } from "next/navigation";
import { Check, Settings } from "lucide-react";
import { useState, useTransition } from "react";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { Drawer, DrawerContent, DrawerTrigger } from "@/components/ui/drawer";
import { seteazaTemaGrup } from "@/lib/actions/grupuri";
import {
  CLASA_FUNDAL_GRUP,
  CLASA_TEMA_GRUP,
  EMBLEME_GRUP,
  EMBLEME_LISTA,
  ETICHETE_EMBLEMA_GRUP,
  ETICHETE_FUNDAL_GRUP,
  ETICHETE_TEMA_GRUP,
  FUNDALURI_GRUP,
  TEME_GRUP,
  type EmblemaGrup,
  type FundalGrup,
  type TemaGrup,
} from "@/lib/tema-grup";
import { cn, formateazaSuma } from "@/lib/utils";

/**
 * Setarile de aspect ale grupului: culoarea de accent si emblema
 * (0054_tema_grup.sql).
 *
 * Deschis de oricine e in grup, nu doar de creator — tema nu e o parghie asupra
 * banilor, e felul in care arata locul comun. Din acelasi motiv se salveaza pe
 * grup, nu pe participant: doi membri deschid grupul si vad acelasi lucru.
 *
 * Salvarea e explicita, nu la fiecare atingere: previzualizarea de sus e vie,
 * deci omul incearca trei culori inainte sa se hotarasca, si n-are rost sa
 * scriem in baza de fiecare data. Diferenta fata de `VizibilitateTranzactii`,
 * unde comutatorul e o singura decizie binara si salvarea optimista e potrivita.
 */
export function SetariGrupDrawer({
  idGrup,
  nume,
  sold,
  tema,
  emblema,
  fundal,
}: {
  idGrup: number;
  nume: string;
  sold: number;
  tema: TemaGrup;
  emblema: EmblemaGrup;
  fundal: FundalGrup;
}) {
  const router = useRouter();
  const [deschis, setDeschis] = useState(false);
  const [temaAleasa, setTemaAleasa] = useState<TemaGrup>(tema);
  const [emblemaAleasa, setEmblemaAleasa] = useState<EmblemaGrup>(emblema);
  const [fundalAles, setFundalAles] = useState<FundalGrup>(fundal);
  const [eroare, setEroare] = useState<string | null>(null);
  const [seSalveaza, startTransition] = useTransition();

  function comutaDeschis(valoare: boolean) {
    setDeschis(valoare);

    // Inchis fara sa salveze, drawerul nu tine minte incercarile: la
    // redeschidere arata ce e efectiv salvat pe grup (DESIGN.md #8.4 — drawerul
    // nu tine stare critica).
    if (!valoare) {
      setTemaAleasa(tema);
      setEmblemaAleasa(emblema);
      setFundalAles(fundal);
      setEroare(null);
    }
  }

  function salveaza() {
    setEroare(null);

    startTransition(async () => {
      const rezultat = await seteazaTemaGrup({
        idGrup,
        tema: temaAleasa,
        emblema: emblemaAleasa,
        fundal: fundalAles,
      });

      if (rezultat.eroare) {
        setEroare(rezultat.eroare);
        return;
      }

      setDeschis(false);
      router.refresh();
    });
  }

  const Emblema = EMBLEME_GRUP[emblemaAleasa];

  return (
    <Drawer open={deschis} onOpenChange={comutaDeschis}>
      <DrawerTrigger
        aria-label="Setările grupului"
        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary-50 text-primary-700 transition-colors hover:bg-primary-100 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
      >
        <Settings size={16} strokeWidth={2} aria-hidden />
      </DrawerTrigger>

      {/* `clasaTema` e tema ALEASA acum, nu cea salvata: fiecare atingere de
          pastila se vede pe loc pe tot drawerul, nu doar pe previzualizare
          (suprascrie scopul paginii, care poarta inca tema veche).

          Butonul din footer nu se dezactiveaza cand nimic nu s-a schimbat:
          DESIGN.md #9 cere ca primarul sa ramana apasabil pana la trimitere,
          iar salvarea aceleiasi teme e oricum idempotenta. */}
      <DrawerContent
        clasaTema={CLASA_TEMA_GRUP[temaAleasa]}
        title="Tema grupului"
        description="Culoarea și emblema se văd la fel pentru toți membrii."
        footer={
          <Button className="w-full" onClick={salveaza} loading={seSalveaza}>
            Salvează tema
          </Button>
        }
      >
        <div className="flex flex-col gap-6">
          {eroare ? <Banda ton="eroare">{eroare}</Banda> : null}

          {/* Previzualizarea e chiar cardul de sold al grupului pe fundalul
              ales, la scara mica — nu un dreptunghi cu gradient: omul alege
              uitandu-se la ce primeste, si vede cele trei alegeri impreuna,
              fiindca impreuna se si vad pe ecran. Acelasi principiu ca
              <FataCard miniatura> din selectorul de tematica de card.

              Pentru `implicit` nu exista clasa (acolo se vede cerul aplicatiei,
              care e un strat fix si nu poate fi randat intr-o miniatura), deci
              cade pe `bg-bg` — fundalul obisnuit al aplicatiei. */}
          <section
            aria-hidden
            className={cn(
              // `relative` din acelasi motiv ca la miniaturi: modelele cu masca
              // isi deseneaza forma pe un `::before` absolut.
              "relative overflow-hidden rounded-card p-4",
              fundalAles === "implicit" ? "bg-bg" : CLASA_FUNDAL_GRUP[fundalAles],
            )}
          >
            {/* `relative` ridica si cardul peste model, altfel ar fi acoperit. */}
            <div className="hero-gradient relative flex items-center gap-3 rounded-card px-4 py-4 shadow-md">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-white/15">
                <Emblema size={20} strokeWidth={1.75} className="text-white" />
              </span>

              <div className="min-w-0 flex-1">
                <p className="truncate text-[15px] font-semibold text-white">{nume}</p>
                <p className="tabular mt-0.5 text-[19px] font-bold leading-6 text-white">
                  {formateazaSuma(sold)}
                </p>
              </div>
            </div>
          </section>

          <section>
            <h3 className="text-[13px] font-semibold text-ink-faint">Culoare</h3>

            <div role="radiogroup" aria-label="Culoarea grupului" className="mt-3 flex flex-wrap gap-3">
              {TEME_GRUP.map((optiune) => (
                <button
                  key={optiune}
                  type="button"
                  role="radio"
                  aria-checked={temaAleasa === optiune}
                  aria-label={ETICHETE_TEMA_GRUP[optiune]}
                  title={ETICHETE_TEMA_GRUP[optiune]}
                  onClick={() => setTemaAleasa(optiune)}
                  className={cn(
                    // Tinta de 44px ceruta de DESIGN.md #10; pastila colorata
                    // dinauntru e mai mica, ca sa nu para butoane lipite.
                    "flex h-11 w-11 items-center justify-center rounded-full transition-colors duration-150 ease-soft",
                    "focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25",
                    temaAleasa === optiune ? "bg-primary-100" : "hover:bg-muted",
                  )}
                >
                  {/* Pastila isi poarta propria clasa de tema, deci `bg-primary-600`
                      inseamna aici culoarea EI, nu a temei selectate. Asa nu
                      intra niciun hex in componenta (DESIGN.md #12). */}
                  <span
                    className={cn(
                      "flex h-8 w-8 items-center justify-center rounded-full bg-primary-600",
                      CLASA_TEMA_GRUP[optiune],
                    )}
                  >
                    {temaAleasa === optiune ? (
                      <Check size={16} strokeWidth={2.5} className="text-white" aria-hidden />
                    ) : null}
                  </span>
                </button>
              ))}
            </div>
          </section>

          <section>
            <h3 className="text-[13px] font-semibold text-ink-faint">Emblemă</h3>

            <div role="radiogroup" aria-label="Emblema grupului" className="mt-3 grid grid-cols-4 gap-2">
              {EMBLEME_LISTA.map((optiune) => {
                const Icoana = EMBLEME_GRUP[optiune];
                const aleasa = emblemaAleasa === optiune;

                return (
                  <button
                    key={optiune}
                    type="button"
                    role="radio"
                    aria-checked={aleasa}
                    aria-label={ETICHETE_EMBLEMA_GRUP[optiune]}
                    title={ETICHETE_EMBLEMA_GRUP[optiune]}
                    onClick={() => setEmblemaAleasa(optiune)}
                    className={cn(
                      "flex h-14 items-center justify-center rounded-field border transition-colors duration-150 ease-soft",
                      "focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25",
                      aleasa
                        ? "border-primary-500 bg-primary-500/12 text-primary-700"
                        : "border-line bg-surface text-ink-faint hover:bg-muted",
                    )}
                  >
                    <Icoana size={20} strokeWidth={1.75} aria-hidden />
                  </button>
                );
              })}
            </div>
          </section>

          <section>
            <h3 className="text-[13px] font-semibold text-ink-faint">Fundal</h3>

            <div role="radiogroup" aria-label="Fundalul grupului" className="mt-3 grid grid-cols-4 gap-2">
              {FUNDALURI_GRUP.map((optiune) => {
                const ales = fundalAles === optiune;

                return (
                  <button
                    key={optiune}
                    type="button"
                    role="radio"
                    aria-checked={ales}
                    aria-label={ETICHETE_FUNDAL_GRUP[optiune]}
                    title={ETICHETE_FUNDAL_GRUP[optiune]}
                    onClick={() => setFundalAles(optiune)}
                    className={cn(
                      "relative flex h-14 items-center justify-center overflow-hidden rounded-field border transition-colors duration-150 ease-soft",
                      "focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25",
                      // Miniatura poarta chiar clasa modelului, deci se
                      // deseneaza cu acelasi CSS ca stratul de pe pagina — nu
                      // exista o a doua reprezentare care sa devieze.
                      // `relative` e obligatoriu: modelele cu masca isi deseneaza
                      // forma pe un `::before` absolut, care altfel ar iesi din
                      // miniatura si s-ar intinde peste tot drawerul.
                      optiune === "implicit" ? "bg-bg" : CLASA_FUNDAL_GRUP[optiune],
                      ales ? "border-primary-500 ring-2 ring-primary-500/40" : "border-line",
                    )}
                  >
                    {/* `relative` ridica bifa peste `::before`-ul modelului:
                        un pseudo-element absolut se picteaza deasupra
                        continutului nepozitionat, deci altfel ar acoperi-o. */}
                    {ales ? (
                      <span className="relative flex h-6 w-6 items-center justify-center rounded-full bg-primary-600">
                        <Check size={14} strokeWidth={2.5} className="text-white" aria-hidden />
                      </span>
                    ) : null}
                  </button>
                );
              })}
            </div>

            <p className="mt-2 text-[12.5px] leading-[18px] text-ink-faint">
              Modelul se desenează în culoarea aleasă mai sus. „Cerul Galaxy” lasă
              fundalul obișnuit al aplicației.
            </p>
          </section>
        </div>
      </DrawerContent>
    </Drawer>
  );
}
