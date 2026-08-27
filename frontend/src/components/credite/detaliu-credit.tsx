"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { CalendarClock, CheckCircle2, FastForward, FileText, TriangleAlert } from "lucide-react";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { Drawer, DrawerContent, DrawerTrigger } from "@/components/ui/drawer";
import { avanseazaTimp, ramburseazaAnticipat } from "@/lib/actions/credite";
import type { CalculRambursare, DetaliuCredit, RataCredit } from "@/lib/data/credite";
import { cn, formateazaSuma } from "@/lib/utils";

/**
 * Detaliul unui credit: cât mai e de plătit, când, și cum se poate stinge mai devreme.
 *
 * Graficul se arată integral, nu doar următoarele rate. Un client care semnează
 * pe 60 de luni are dreptul să vadă de la început cât din fiecare rată e
 * dobândă — e diferența dintre un grafic și o cifră lunară.
 */

const ETICHETE_STARE: Record<string, { text: string; clasa: string }> = {
  activ: { text: "Activ", clasa: "bg-primary-50 text-primary-700" },
  restant: { text: "Restant", clasa: "bg-danger/10 text-danger" },
  inchis: { text: "Închis", clasa: "bg-muted text-ink-soft" },
  rambursat_anticipat: { text: "Rambursat anticipat", clasa: "bg-success/10 text-success" },
};

export function DetaliuCreditVizual({
  detaliu,
  calcul,
}: {
  detaliu: DetaliuCredit;
  calcul: CalculRambursare | null;
}) {
  const router = useRouter();
  const { credit, rate, urmatoareaRata, ratePlatite } = detaliu;
  const [eroare, setEroare] = useState<string | null>(null);
  const [seLucreaza, startTransition] = useTransition();

  const inchis = credit.status === "inchis" || credit.status === "rambursat_anticipat";
  const stare = ETICHETE_STARE[credit.status] ?? ETICHETE_STARE.activ;
  const progres = credit.luni > 0 ? (ratePlatite / credit.luni) * 100 : 0;

  function ruleaza(actiune: () => Promise<{ eroare?: string }>) {
    setEroare(null);
    startTransition(async () => {
      const rezultat = await actiune();
      if (rezultat.eroare) {
        setEroare(rezultat.eroare);
        return;
      }
      router.refresh();
    });
  }

  return (
    <div className="mt-6 space-y-5">
      <section className="rounded-card bg-surface p-5 shadow-sm">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-[13px] text-ink-faint">
              {inchis ? "Credit stins" : "Rămas de plată"}
            </p>
            <p className="tabular mt-1 text-[30px] font-bold leading-[36px] text-ink">
              {formateazaSuma(credit.soldRamas)}
            </p>
          </div>
          <span className={cn("shrink-0 rounded-full px-2.5 py-1 text-[11px] font-medium", stare.clasa)}>
            {stare.text}
          </span>
        </div>

        <div className="mt-4 h-1.5 w-full rounded-full bg-muted">
          <div
            className="h-1.5 rounded-full bg-primary-600 transition-[width] duration-500 ease-soft"
            style={{ width: `${progres}%` }}
          />
        </div>
        <p className="mt-2 text-[13px] text-ink-faint">
          {ratePlatite} din {credit.luni} rate plătite
        </p>

        <dl className="mt-5 space-y-2 border-t border-line pt-4">
          <Rand eticheta="Credit acordat" valoare={formateazaSuma(credit.principal)} />
          <Rand eticheta="Rată lunară" valoare={formateazaSuma(credit.rataLunara)} />
          <Rand eticheta="Dobândă" valoare={procent(credit.dobandaAnuala)} />
          {credit.dae ? <Rand eticheta="DAE" valoare={procent(credit.dae)} /> : null}
          <Rand eticheta="Acordat pe" valoare={dataRo(credit.dataAcordarii)} />
        </dl>

        {/* Contractul semnat. Linkul e semnat si expira in cateva minute, deci
            se deschide, nu se copiaza — de aceea nu il aratam ca text. */}
        {credit.contractUrl ? (
          <a
            href={credit.contractUrl}
            target="_blank"
            rel="noreferrer"
            className="mt-4 flex h-11 w-full items-center justify-center gap-2 rounded-field border border-primary-100 bg-primary-50 text-[14px] font-semibold text-primary-700 transition-colors hover:bg-primary-100 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
          >
            <FileText size={18} strokeWidth={1.75} aria-hidden />
            Contractul semnat (PDF)
          </a>
        ) : null}
      </section>

      {urmatoareaRata && !inchis ? (
        <section className="flex items-center gap-3 rounded-card bg-surface p-5 shadow-sm">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-primary-50 text-primary-600">
            {urmatoareaRata.status === "restanta" ? (
              <TriangleAlert size={20} strokeWidth={1.75} aria-hidden />
            ) : (
              <CalendarClock size={20} strokeWidth={1.75} aria-hidden />
            )}
          </span>
          <div className="min-w-0 flex-1">
            <p className="text-[13px] text-ink-faint">
              {urmatoareaRata.status === "restanta" ? "Rată restantă" : "Următoarea rată"}
            </p>
            <p className="text-[15px] font-medium text-ink">
              {formateazaSuma(urmatoareaRata.rataTotala)} · {dataRo(urmatoareaRata.scadenta)}
            </p>
          </div>
        </section>
      ) : null}

      {urmatoareaRata?.status === "restanta" ? (
        <Banda ton="eroare">
          Nu au fost destui bani în cont la scadență. Alimentează contul —
          rata se reîncearcă la următoarea verificare.
        </Banda>
      ) : null}

      {eroare ? <Banda ton="eroare">{eroare}</Banda> : null}

      {!inchis && calcul ? (
        <RambursareDrawer
          idCredit={credit.id}
          calcul={calcul}
          seLucreaza={seLucreaza}
          onConfirma={(suma) => ruleaza(() => ramburseazaAnticipat(credit.id, suma))}
        />
      ) : null}

      <GraficRate rate={rate} />

      {!inchis ? (
        <section className="rounded-card border border-dashed border-line p-4">
          <p className="text-[13px] leading-[19px] text-ink-faint">
            <FastForward size={14} strokeWidth={2} aria-hidden className="mr-1 inline align--2" />
            Unealtă de demonstrație: mută scadențele înainte, ca să vezi ratele
            încasându-se fără să aștepți o lună.
          </p>
          <div className="mt-3 flex gap-2">
            {[1, 3, 6].map((luni) => (
              <Button
                key={luni}
                varianta="secondary"
                marime="sm"
                loading={seLucreaza}
                onClick={() => ruleaza(() => avanseazaTimp(credit.id, luni))}
              >
                +{luni} {luni === 1 ? "lună" : "luni"}
              </Button>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}

function RambursareDrawer({
  idCredit,
  calcul,
  seLucreaza,
  onConfirma,
}: {
  idCredit: string;
  calcul: CalculRambursare;
  seLucreaza: boolean;
  onConfirma: (suma?: number) => void;
}) {
  const [deschis, setDeschis] = useState(false);

  return (
    <Drawer open={deschis} onOpenChange={setDeschis}>
      <DrawerTrigger asChild>
        <Button className="w-full" varianta="secondary">
          Rambursează anticipat
        </Button>
      </DrawerTrigger>

      <DrawerContent
        title="Rambursare anticipată"
        description="Stinge creditul înainte de termen și economisește dobânda rămasă."
        footer={
          <Button
            className="w-full"
            loading={seLucreaza}
            onClick={() => {
              onConfirma(undefined);
              setDeschis(false);
            }}
          >
            Plătește {formateazaSuma(calcul.totalDePlata)}
          </Button>
        }
      >
        <dl className="space-y-2 px-5 pb-2">
          <Rand eticheta="Sold rămas" valoare={formateazaSuma(calcul.sold)} />
          <Rand
            eticheta={`Dobândă pentru ${calcul.zileDeLaUltimaScadenta} zile`}
            valoare={formateazaSuma(calcul.dobandaAcumulata)}
          />
          <div className="border-t border-line pt-2">
            <Rand eticheta="Total de plată" valoare={formateazaSuma(calcul.totalDePlata)} />
          </div>
        </dl>

        <div className="mx-5 mt-4 rounded-field bg-success/10 p-4">
          <p className="text-[13px] leading-[19px] text-success">
            Economisești {formateazaSuma(calcul.economieDobanda)} din dobânda pe
            care ai fi plătit-o mergând până la capăt.
          </p>
        </div>

        <p className="mt-4 px-5 text-[13px] leading-[19px] text-ink-faint">
          Galaxy Bank nu percepe comision de rambursare anticipată pentru acest
          produs. Suma se ia din contul în care ai primit creditul.
        </p>
      </DrawerContent>
    </Drawer>
  );
}

function GraficRate({ rate }: { rate: RataCredit[] }) {
  const active = rate.filter((rata) => rata.status !== "anulata");
  if (active.length === 0) return null;

  return (
    <section className="rounded-card bg-surface shadow-sm">
      <h2 className="px-5 pt-5 text-[15px] font-semibold text-ink">Grafic de rambursare</h2>

      <div className="mt-3 max-h-[420px] overflow-y-auto">
        <ul className="divide-y divide-line">
          {active.map((rata) => (
            <li key={rata.numarRata} className="flex items-center gap-3 px-5 py-3">
              <span
                className={cn(
                  "flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-[11px] font-medium",
                  rata.status === "platita"
                    ? "bg-success/10 text-success"
                    : rata.status === "restanta"
                      ? "bg-danger/10 text-danger"
                      : "bg-muted text-ink-faint",
                )}
              >
                {rata.status === "platita" ? (
                  <CheckCircle2 size={16} strokeWidth={2} aria-hidden />
                ) : (
                  rata.numarRata
                )}
              </span>

              <div className="min-w-0 flex-1">
                <p className="text-[15px] text-ink">{dataRo(rata.scadenta)}</p>
                <p className="tabular text-[11px] text-ink-faint">
                  {formateazaSuma(rata.principalRata)} principal ·{" "}
                  {formateazaSuma(rata.dobandaRata)} dobândă
                </p>
              </div>

              <span className="tabular shrink-0 text-[15px] font-medium text-ink">
                {formateazaSuma(rata.rataTotala)}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

function Rand({ eticheta, valoare }: { eticheta: string; valoare: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4">
      <dt className="text-[13px] text-ink-soft">{eticheta}</dt>
      <dd className="tabular text-[15px] font-medium text-ink">{valoare}</dd>
    </div>
  );
}

function procent(fractie: number) {
  return `${(fractie * 100).toFixed(2).replace(".", ",")}%`;
}

/** Data lunii in romana, cu fus fixat — ca in lib/utils.ts, ca sa nu difere server de client. */
function dataRo(zi: string) {
  return new Date(`${zi}T12:00:00Z`).toLocaleDateString("ro-RO", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "Europe/Bucharest",
  });
}
