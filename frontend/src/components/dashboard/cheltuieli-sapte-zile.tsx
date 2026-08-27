"use client";

import { useEffect, useMemo, useState } from "react";
import { Bar, BarChart, LabelList, ResponsiveContainer, Tooltip, XAxis } from "recharts";
import { useValutaDashboard } from "@/components/dashboard/context-valuta";
import type { TranzactieCategorizata } from "@/lib/data/analiza";
import { formateazaNumar, formateazaSuma, ziISO } from "@/lib/utils";
import { converteste, type Curs, type Valuta } from "@/lib/valute";

const ZILE = 7;

/** O zi din grafic: cheia de grupare, ce scrie sub bara, si cat s-a cheltuit. */
type Zi = {
  cheie: string;
  eticheta: string;
  etichetaLunga: string;
  total: number;
};

/** Ultimele sapte zile calendaristice, cea de azi ultima. */
function ultimeleZile(): Date[] {
  const azi = new Date();

  return Array.from({ length: ZILE }, (_, i) => {
    const zi = new Date(azi);
    zi.setDate(azi.getDate() - (ZILE - 1 - i));
    return zi;
  });
}

/** "lu." -> "Lu"; ziua de azi isi spune pe nume. */
function etichetaScurta(zi: Date, esteAzi: boolean) {
  if (esteAzi) return "Azi";

  const text = zi.toLocaleDateString("ro-RO", { weekday: "short" }).replace(".", "");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/**
 * Cheltuielile pe fiecare din ultimele sapte zile, in valuta ceruta.
 *
 * Se numara doar iesirile: un salariu intrat marti n-are ce cauta intr-un
 * grafic de cheltuieli. O tranzactie a carei valuta n-are curs fata de cea
 * ceruta se lasa afara, ca peste tot in aplicatie (lib/valute.ts) — mai bine o
 * cifra mai mica si adevarata decat una inventata.
 */
function cheltuieliPeZi(
  tranzactii: TranzactieCategorizata[],
  cursuri: Curs[],
  valuta: Valuta,
): Zi[] {
  const azi = ziISO(new Date());
  const zile = ultimeleZile().map<Zi>((zi) => {
    const cheie = ziISO(zi);
    return {
      cheie,
      eticheta: etichetaScurta(zi, cheie === azi),
      etichetaLunga: zi.toLocaleDateString("ro-RO", { weekday: "long", day: "numeric", month: "long" }),
      total: 0,
    };
  });

  const dupaCheie = new Map(zile.map((zi) => [zi.cheie, zi]));

  for (const tranzactie of tranzactii) {
    if (tranzactie.directie !== "iesire") continue;

    const zi = dupaCheie.get(ziISO(tranzactie.data));
    if (!zi) continue;

    const suma = converteste(tranzactie.suma, tranzactie.valuta as Valuta, valuta, cursuri);
    if (suma === null) continue;

    zi.total = Math.round((zi.total + suma) * 100) / 100;
  }

  return zile;
}

/**
 * Cheltuielile ultimei saptamani, o bara pe zi.
 *
 * Sta sub conturi fiindca raspunde la intrebarea urmatoare celei de acolo: nu
 * „cat am", ci „pe ce se duce". Sapte zile, nu treizeci: la latimea unui
 * telefon, o luna intreaga devine un pieptene ilizibil, iar saptamana e si
 * intervalul in care omul isi mai aminteste ce a cumparat.
 *
 * O singura serie, deci fara legenda si fara culori pe rang: toate barele au
 * aceeasi culoare, iar cifra se scrie doar deasupra celei mai mari. Restul se
 * citesc la atingere. Sub bare, un „sant" palid tine locul zilelor fara nicio
 * cheltuiala — altfel ar disparea din grafic si ziua, si explicatia ei.
 *
 * Valuta e cea aleasa pe dashboard (ValutaDashboardContext), aceeasi cu totalul
 * din conturi si cu cheltuielile pe categorie; conversia se face aici, cu
 * cursurile deja aduse de pagina.
 */
export function CheltuieliSapteZile({
  tranzactii,
  cursuri,
}: {
  tranzactii: TranzactieCategorizata[];
  cursuri: Curs[];
}) {
  const { valuta } = useValutaDashboard();
  const [animatie, setAnimatie] = useState(false);

  // DESIGN.md 7: cu `prefers-reduced-motion` barele apar direct la inaltimea
  // lor. Steagul porneste stins si se aprinde dupa montare, deci nici randarea
  // de pe server nu porneste o animatie pe care clientul ar relua-o.
  useEffect(() => {
    setAnimatie(!window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  }, []);

  const zile = useMemo(
    () => cheltuieliPeZi(tranzactii, cursuri, valuta),
    [tranzactii, cursuri, valuta],
  );

  const total = zile.reduce((suma, zi) => suma + zi.total, 0);
  const maxim = Math.max(...zile.map((zi) => zi.total));
  const indexMaxim = zile.findIndex((zi) => zi.total === maxim);

  return (
    <section className="mt-8">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="text-lg font-semibold text-ink">Cheltuieli, ultimele 7 zile</h2>
      </div>

      {total === 0 ? (
        <p className="mt-4 rounded-card bg-surface p-6 text-center text-[15px] text-ink-faint shadow-sm">
          Nu ai nicio cheltuială în ultimele 7 zile.
        </p>
      ) : (
        <div className="animate-fade-up mt-4 rounded-card bg-surface p-5 shadow-sm">
          <p className="tabular text-[26px] font-bold leading-[32px] text-ink">
            {formateazaSuma(total, valuta)}
          </p>
          <p className="mt-1 text-[13px] text-ink-faint">
            în total, adică {formateazaSuma(Math.round((total / ZILE) * 100) / 100, valuta)} pe zi
          </p>

          {/* Graficul e decorativ pentru cititorii de ecran: cifrele lui stau
              mai jos, in lista ascunsa vizual. */}
          <div className="mt-5 h-[168px] w-full" aria-hidden>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={zile} margin={{ top: 24, right: 0, bottom: 0, left: 0 }}>
                <XAxis
                  dataKey="eticheta"
                  tickLine={false}
                  axisLine={false}
                  dy={6}
                  tick={{ fill: "var(--color-ink-faint)", fontSize: 12 }}
                />

                <Tooltip
                  cursor={false}
                  animationDuration={120}
                  content={<SfatZi valuta={valuta} />}
                />

                <Bar
                  dataKey="total"
                  fill="var(--color-primary-600)"
                  radius={[6, 6, 6, 6]}
                  maxBarSize={34}
                  background={{ fill: "var(--color-muted)", radius: 6 }}
                  isAnimationActive={animatie}
                  animationBegin={60}
                  animationDuration={320}
                  animationEasing="ease-out"
                >
                  <LabelList
                    dataKey="total"
                    content={<EtichetaMaxim indexMaxim={indexMaxim} valuta={valuta} />}
                  />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          <ul className="sr-only">
            {zile.map((zi) => (
              <li key={zi.cheie}>
                {zi.etichetaLunga}: {formateazaSuma(zi.total, valuta)}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

/** Cifra de deasupra celei mai mari zile. Doar a ei — restul se citesc la atingere. */
function EtichetaMaxim({
  indexMaxim,
  valuta,
  x,
  y,
  width,
  index,
  value,
}: {
  indexMaxim: number;
  valuta: Valuta;
  // Vin de la Recharts, prin `content`, deci sunt optionale la tipare.
  x?: number | string;
  y?: number | string;
  width?: number | string;
  index?: number;
  value?: number | string;
}) {
  const suma = Number(value ?? 0);

  if (index !== indexMaxim || suma <= 0) return null;

  return (
    <text
      x={Number(x) + Number(width) / 2}
      y={Number(y) - 10}
      textAnchor="middle"
      className="tabular"
      fill="var(--color-ink)"
      fontSize={12}
      fontWeight={600}
    >
      {formateazaNumar(suma)} {valuta}
    </text>
  );
}

/** Ce se vede la atingerea unei bare: ziua intreaga si suma ei. */
function SfatZi({
  valuta,
  active,
  payload,
}: {
  valuta: Valuta;
  active?: boolean;
  payload?: { payload: Zi }[];
}) {
  const zi = payload?.[0]?.payload;

  if (!active || !zi) return null;

  return (
    <div className="rounded-field border border-line bg-surface px-3 py-2 shadow-md">
      <p className="text-[12px] capitalize text-ink-faint">{zi.etichetaLunga}</p>
      <p className="tabular mt-0.5 text-[14px] font-semibold text-ink">
        {formateazaSuma(zi.total, valuta)}
      </p>
    </div>
  );
}
