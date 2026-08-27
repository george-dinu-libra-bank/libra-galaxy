"use client";

import { motion } from "motion/react";
import { TrendingUp } from "lucide-react";
import { Drawer, DrawerContent, DrawerTrigger } from "@/components/ui/drawer";
import type { Cashflow } from "@/lib/data/analiza";
import { cn, formateazaSuma } from "@/lib/utils";

/**
 * Cashflow-ul lunii curente (încasări/cheltuieli/net), stil Revolut — vizual
 * hand-rolled (bare animate cu `motion`), fără librărie de grafice nouă
 * (proiectul nu are niciuna instalată).
 *
 * `cashflow` vine deja adus pe server (dashboard/page.tsx), la fel ca la
 * `SchimbValutarDrawer` — un drawer client nu poate aduce singur date prin
 * `apelBackend` (foloseste "next/headers", interzis in bundle-ul de client;
 * verificat live, build-ul Next esua exact din cauza asta).
 */
export function CashflowDrawer({
  cashflow,
  className,
}: {
  cashflow: Cashflow | null;
  className?: string;
}) {
  const luna = cashflow?.luni[0] ?? null;
  const maxim = luna ? Math.max(luna.incasari, luna.cheltuieli, 1) : 1;

  return (
    <Drawer>
      <DrawerTrigger className={className}>
        <TrendingUp size={22} strokeWidth={1.75} aria-hidden className="text-primary-600" />
        <span className="text-center text-xs leading-4 text-ink-soft">Cashflow</span>
      </DrawerTrigger>

      <DrawerContent title="Cashflow" description="Încasări și cheltuieli în luna curentă.">
        {!luna || !cashflow ? (
          <p className="py-8 text-center text-[15px] text-ink-faint">
            Nu există date pentru luna curentă.
          </p>
        ) : (
          <div className="flex flex-col gap-6 py-2">
            <div className="text-center">
              <p className="text-[13px] text-ink-faint">Net</p>
              <p
                className={cn(
                  "tabular text-[30px] font-bold leading-[36px]",
                  luna.net >= 0 ? "text-success" : "text-danger",
                )}
              >
                {luna.net >= 0 ? "+" : ""}
                {formateazaSuma(luna.net, cashflow.valuta)}
              </p>
            </div>

            <BaraCashflow eticheta="Încasări" suma={luna.incasari} maxim={maxim} valuta={cashflow.valuta} culoare="bg-success" />
            <BaraCashflow eticheta="Cheltuieli" suma={luna.cheltuieli} maxim={maxim} valuta={cashflow.valuta} culoare="bg-danger" />

            <p className="text-center text-[12.5px] text-ink-faint">
              Media lunară de cheltuieli: {formateazaSuma(cashflow.mediaLunaraCheltuieli, cashflow.valuta)}
            </p>
          </div>
        )}
      </DrawerContent>
    </Drawer>
  );
}

function BaraCashflow({
  eticheta,
  suma,
  maxim,
  valuta,
  culoare,
}: {
  eticheta: string;
  suma: number;
  maxim: number;
  valuta: string;
  culoare: string;
}) {
  const procent = Math.max(4, Math.round((suma / maxim) * 100));

  return (
    <div>
      <div className="flex items-baseline justify-between">
        <span className="text-[13px] text-ink-soft">{eticheta}</span>
        <span className="tabular text-[15px] font-semibold text-ink">{formateazaSuma(suma, valuta)}</span>
      </div>
      <div className="mt-1.5 h-2.5 w-full overflow-hidden rounded-full bg-muted">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${procent}%` }}
          transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
          className={cn("h-full rounded-full", culoare)}
        />
      </div>
    </div>
  );
}
