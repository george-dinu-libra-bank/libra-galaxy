"use client";

import { useState } from "react";
import { Lock, Unlock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Drawer, DrawerContent } from "@/components/ui/drawer";
import type { Card } from "@/lib/mock-data";
import { cn, formateazaSuma } from "@/lib/utils";

export function ListaCarduri({ carduri: initiale }: { carduri: Card[] }) {
  const [carduri, setCarduri] = useState(initiale);
  const [selectatId, setSelectatId] = useState<string | null>(null);

  const selectat = carduri.find((c) => c.id === selectatId) ?? null;

  function comutaBlocare(id: string) {
    setCarduri((prev) =>
      prev.map((c) => (c.id === id ? { ...c, stare: c.stare === "activ" ? "blocat" : "activ" } : c)),
    );
  }

  return (
    <div className="mx-auto w-full max-w-[440px] px-6 pb-6 pt-8 sm:max-w-2xl">
      <h1 className="text-xl font-bold tracking-[-0.02em] text-ink">Carduri</h1>
      <p className="mt-1 text-[15px] text-ink-soft">Cardurile asociate contului tău Libra.</p>

      <div className="mt-6 flex flex-col gap-4">
        {carduri.map((card) => (
          <button
            key={card.id}
            type="button"
            onClick={() => setSelectatId(card.id)}
            className="animate-fade-up rounded-card p-5 text-left text-white shadow-lg transition-transform duration-150 ease-soft active:scale-[0.98]"
            style={{
              background:
                card.culoare === "primar"
                  ? "linear-gradient(160deg, var(--color-primary-500) 0%, var(--color-primary-600) 55%, var(--color-primary-700) 100%)"
                  : "linear-gradient(160deg, var(--color-ink-soft) 0%, var(--color-ink) 100%)",
              opacity: card.stare === "blocat" ? 0.7 : 1,
            }}
          >
            <div className="flex items-start justify-between">
              <span className="text-[13px] text-white/80">
                {card.tip === "debit" ? "Card de debit" : "Card de credit"}
              </span>
              {card.stare === "blocat" ? (
                <span className="flex items-center gap-1 rounded-full bg-white/15 px-2.5 py-1 text-[11px] font-medium text-white">
                  <Lock size={12} strokeWidth={1.75} aria-hidden />
                  Blocat
                </span>
              ) : null}
            </div>

            <p className="tabular mt-6 text-[19px] tracking-[0.08em]">{card.numarMascat}</p>

            <div className="mt-4 flex items-end justify-between">
              <div>
                <p className="text-[10px] uppercase tracking-wide text-white/70">Titular</p>
                <p className="text-[13px]">{card.detinator}</p>
              </div>
              <div className="text-right">
                <p className="text-[10px] uppercase tracking-wide text-white/70">Expira</p>
                <p className="tabular text-[13px]">{card.expira}</p>
              </div>
            </div>
          </button>
        ))}
      </div>

      <Drawer
        open={selectat !== null}
        onOpenChange={(deschis) => {
          if (!deschis) setSelectatId(null);
        }}
      >
        <DrawerContent
          title={selectat ? (selectat.tip === "debit" ? "Card de debit" : "Card de credit") : ""}
          description={selectat?.numarMascat ?? ""}
          footer={
            selectat ? (
              <Button
                varianta={selectat.stare === "activ" ? "danger" : "primary"}
                className="w-full"
                iconaStanga={
                  selectat.stare === "activ" ? (
                    <Lock size={18} strokeWidth={1.75} aria-hidden />
                  ) : (
                    <Unlock size={18} strokeWidth={1.75} aria-hidden />
                  )
                }
                onClick={() => comutaBlocare(selectat.id)}
              >
                {selectat.stare === "activ" ? "Blochează cardul" : "Deblochează cardul"}
              </Button>
            ) : undefined
          }
        >
          {selectat ? <DetaliuCard card={selectat} /> : null}
        </DrawerContent>
      </Drawer>
    </div>
  );
}

function DetaliuCard({ card }: { card: Card }) {
  const procent = Math.min(100, Math.round((card.cheltuitAstazi / card.limitaZilnica) * 100));

  return (
    <div className="flex flex-col gap-4">
      <div className="rounded-field bg-muted p-4">
        <div className="flex items-center justify-between text-[13px]">
          <span className="text-ink-soft">Cheltuit astăzi</span>
          <span className={cn("font-medium", card.stare === "blocat" ? "text-ink-faint" : "text-ink")}>
            {formateazaSuma(card.cheltuitAstazi)} / {formateazaSuma(card.limitaZilnica)}
          </span>
        </div>
        <div className="mt-2 h-2 overflow-hidden rounded-full bg-line">
          <div
            className={cn("h-full rounded-full", card.stare === "blocat" ? "bg-ink-faint" : "bg-primary-600")}
            style={{ width: `${procent}%` }}
          />
        </div>
      </div>

      <div>
        <Rand eticheta="Titular" valoare={card.detinator} />
        <Rand eticheta="Numar" valoare={card.numarMascat} mono />
        <Rand eticheta="Expira" valoare={card.expira} mono />
        <Rand eticheta="Stare" valoare={card.stare === "activ" ? "Activ" : "Blocat"} />
      </div>
    </div>
  );
}

function Rand({ eticheta, valoare, mono }: { eticheta: string; valoare: string; mono?: boolean }) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-line py-3 last:border-0">
      <span className="text-[13px] text-ink-faint">{eticheta}</span>
      <span className={cn("text-right text-[15px] text-ink", mono && "tabular")}>{valoare}</span>
    </div>
  );
}
