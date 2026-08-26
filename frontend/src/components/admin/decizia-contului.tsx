"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { Check, Lock, ShieldAlert, Unlock } from "lucide-react";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { Camp } from "@/components/ui/camp";
import { Drawer, DrawerContent } from "@/components/ui/drawer";
import { decideCont } from "@/lib/actions/admin-analiza";
import type { IstoricAnaliza } from "@/lib/tipuri-admin";
import { dataSiOra } from "@/lib/momente";

/**
 * Ce poate face un administrator cu un cont semnalat.
 *
 * Doua sectiuni, fiindca sunt doua lucruri diferite: a scrie ce ai constatat,
 * si a lua o masura. Nimic nu se aplica pe contul cuiva ca efect secundar al
 * unei observatii — blocarea si deblocarea au butoanele lor, spun exact ce fac,
 * si se intampla doar cand le apesi.
 */

type Actiune = "acceptat" | "suspiciune" | "blocheaza" | "deblocheaza";

const TEXTE: Record<
  Actiune,
  {
    titlu: string;
    descriere: (nume: string) => string;
    buton: string;
    exemplu: string;
    cereObservatie: boolean;
  }
> = {
  acceptat: {
    titlu: "Închizi analiza fără măsuri?",
    descriere: (n) =>
      `Rămâne consemnat că ai verificat contul lui ${n} și nu s-a confirmat nimic. Contul nu e atins și clientul nu e notificat.`,
    buton: "Da, închide analiza",
    exemplu: "Ex. am sunat clientul, confirmă toate plățile",
    cereObservatie: false,
  },
  suspiciune: {
    titlu: "Consemnezi suspiciunea de fraudă?",
    descriere: (n) =>
      `Se scrie în istoricul lui ${n} că semnalele s-au confirmat. Contul NU se blochează și clientul nu e notificat — blocarea e un buton separat.`,
    buton: "Da, consemnează",
    exemplu: "Ex. plăți către conturi nou create, negate de titular",
    cereObservatie: true,
  },
  blocheaza: {
    titlu: "Blochezi conturile acestui client?",
    descriere: (n) =>
      `Conturile lui ${n} vor fi blocate imediat: nu mai pot pleca bani nici prin card, nici prin transfer. Banii care vin către el intră normal. Va primi o notificare cu motivul.`,
    buton: "Da, blochează conturile",
    exemplu: "Ex. blocat preventiv până la clarificarea plăților din 21.08",
    cereObservatie: true,
  },
  deblocheaza: {
    titlu: "Deblochezi conturile?",
    descriere: (n) => `${n} își va putea folosi din nou conturile și va fi anunțat.`,
    buton: "Da, deblochează",
    exemplu: "Ex. clientul a confirmat plățile, documente verificate",
    cereObservatie: true,
  },
};

export function DeciziaContului({
  idUtilizator,
  nume,
  gravitate,
  numarSemnalari,
  zile,
  esteBlocat,
  conturiTotal,
  istoric,
}: {
  idUtilizator: string;
  nume: string;
  gravitate: number;
  numarSemnalari: number;
  zile: number;
  esteBlocat: boolean;
  conturiTotal: number;
  istoric: IstoricAnaliza[];
}) {
  const router = useRouter();
  const [actiune, setActiune] = useState<Actiune | null>(null);
  const [observatie, setObservatie] = useState("");
  const [eroare, setEroare] = useState<string | null>(null);
  const [seTrimite, startTransition] = useTransition();

  const texte = actiune ? TEXTE[actiune] : null;
  const observatieLipsa = Boolean(texte?.cereObservatie) && observatie.trim().length === 0;

  function confirma() {
    if (!actiune || observatieLipsa) return;
    setEroare(null);

    // Verdictul si masura merg pe acelasi drum catre server, dar blocarea se
    // cere anume prin `aplicaBlocarea` — nu se deduce din verdict.
    const decizie =
      actiune === "acceptat" ? "acceptat" : actiune === "deblocheaza" ? "deblocat" : "frauda";

    startTransition(async () => {
      const rezultat = await decideCont(idUtilizator, decizie, observatie, {
        gravitate,
        numarSemnalari,
        zile,
        aplicaBlocarea: actiune === "blocheaza",
      });
      if (rezultat.eroare) {
        setEroare(rezultat.eroare);
        return;
      }
      setActiune(null);
      setObservatie("");
      router.refresh();
    });
  }

  return (
    <div className="flex flex-col gap-4">
      <section className="rounded-card border border-line bg-surface p-5">
        <h2 className="text-[15px] font-semibold text-ink">Analiza ta</h2>
        <p className="mt-1 text-[13px] leading-[19px] text-ink-faint">
          Ce constați rămâne în istoricul contului, cu numele tău. Nu schimbă nimic pe cont.
        </p>

        {eroare ? (
          <div className="mt-4">
            <Banda ton="eroare">{eroare}</Banda>
          </div>
        ) : null}

        <div className="mt-4 flex flex-col gap-3 sm:flex-row">
          <Button
            varianta="secondary"
            className="flex-1"
            iconaStanga={<Check size={18} strokeWidth={1.75} aria-hidden />}
            onClick={() => setActiune("acceptat")}
          >
            Fără probleme
          </Button>
          <Button
            varianta="secondary"
            className="flex-1"
            iconaStanga={<ShieldAlert size={18} strokeWidth={1.75} aria-hidden />}
            onClick={() => setActiune("suspiciune")}
          >
            Consemnează suspiciune
          </Button>
        </div>
      </section>

      <section className="rounded-card border border-line bg-surface p-5">
        <h2 className="text-[15px] font-semibold text-ink">Măsuri asupra contului</h2>
        <p className="mt-1 text-[13px] leading-[19px] text-ink-faint">
          Se aplică doar când apeși tu. Nimic nu se blochează automat.
        </p>

        <div className="mt-4">
          <Banda ton={esteBlocat ? "eroare" : "info"}>
            {esteBlocat ? (
              <>
                Conturile acestui client sunt <strong className="font-semibold">blocate</strong>.
                Nu mai pot pleca bani nici prin card, nici prin transfer.
              </>
            ) : (
              <>
                Conturile sunt active ({conturiTotal}
                {conturiTotal === 1 ? " cont" : " conturi"}).
              </>
            )}
          </Banda>
        </div>

        <div className="mt-4">
          {esteBlocat ? (
            <Button
              className="w-full sm:w-auto"
              iconaStanga={<Unlock size={18} strokeWidth={1.75} aria-hidden />}
              onClick={() => setActiune("deblocheaza")}
            >
              Deblochează conturile
            </Button>
          ) : (
            <Button
              varianta="danger"
              className="w-full sm:w-auto"
              disabled={conturiTotal === 0}
              iconaStanga={<Lock size={18} strokeWidth={1.75} aria-hidden />}
              onClick={() => setActiune("blocheaza")}
            >
              Blochează conturile
            </Button>
          )}
        </div>
      </section>

      {istoric.length > 0 ? <Istoric randuri={istoric} /> : null}

      <Drawer
        open={actiune !== null}
        onOpenChange={(deschis) => {
          if (!deschis && !seTrimite) {
            setActiune(null);
            setEroare(null);
          }
        }}
        dismissible={!seTrimite}
      >
        <DrawerContent
          title={texte?.titlu ?? ""}
          description={texte?.descriere(nume) ?? ""}
          cuInchidere={!seTrimite}
          footer={
            <Button
              varianta={actiune === "blocheaza" ? "danger" : "primary"}
              className="w-full"
              loading={seTrimite}
              disabled={observatieLipsa}
              onClick={confirma}
            >
              {texte?.buton ?? ""}
            </Button>
          }
        >
          <Camp
            eticheta={texte?.cereObservatie ? "Observație" : "Observație (opțional)"}
            value={observatie}
            onChange={(e) => setObservatie(e.target.value)}
            placeholder={texte?.exemplu ?? ""}
            maxLength={2000}
            ajutor={
              actiune === "blocheaza" || actiune === "deblocheaza"
                ? "Rămâne în istoric și ajunge la client, în notificare."
                : "Rămâne în istoricul contului, alături de numele tău."
            }
            autoComplete="off"
          />
        </DrawerContent>
      </Drawer>
    </div>
  );
}

/** Aceeasi decizie inseamna altceva daca s-au atins conturi sau nu. */
function eticheta(r: IstoricAnaliza): string {
  if (r.decizie === "acceptat") return "Verificat, fără probleme";
  if (r.decizie === "deblocat") return "Conturile au fost deblocate";
  return r.conturi_blocate > 0 ? "Conturile au fost blocate" : "Suspiciune de fraudă consemnată";
}

function Istoric({ randuri }: { randuri: IstoricAnaliza[] }) {
  return (
    <section className="rounded-card border border-line bg-surface p-5">
      <h2 className="text-[15px] font-semibold text-ink">Ce s-a hotărât până acum</h2>
      <ul className="mt-3 flex flex-col gap-3">
        {randuri.map((r) => (
          <li key={r.id} className="text-[13px] leading-[19px]">
            <div className="flex flex-wrap items-baseline gap-x-2">
              <span className="font-semibold text-ink">{eticheta(r)}</span>
              <span className="text-ink-faint">
                {dataSiOra(r.creat_la)}
              </span>
              {r.gravitate !== null ? (
                <span className="text-ink-faint">· gravitate {r.gravitate}</span>
              ) : null}
            </div>
            {r.observatie ? <p className="mt-0.5 text-ink-soft">{r.observatie}</p> : null}
          </li>
        ))}
      </ul>
    </section>
  );
}
