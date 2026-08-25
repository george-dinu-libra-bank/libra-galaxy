"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { Check, CreditCard, Plus } from "lucide-react";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { Drawer, DrawerContent, DrawerTrigger } from "@/components/ui/drawer";
import { adaugaCard } from "@/lib/actions/carduri";
import type { StilCard, TipCard } from "@/lib/data/carduri";
import type { ContBancar } from "@/lib/data/conturi";
import { ETICHETE_STIL_CARD, GRADIENTE_STIL_CARD } from "@/lib/stil-card";
import { cn, formateazaSuma } from "@/lib/utils";

const DESCRIERI_STIL_CARD: Record<StilCard, string> = {
  standard: "Albastrul Galaxy Bank, pentru orice zi.",
  silver: "Gri grafit, discret.",
  gold: "Auriu, pentru clienții premium.",
};

const TEMATICI: StilCard[] = ["standard", "silver", "gold"];

/**
 * Un card nou: contul din care plateste, tipul si tematica.
 *
 * Contul e prima alegere, nu ultima, fiindca e singura care conteaza cu
 * adevarat — el decide din ce bani se plateste si in ce valuta. Tematica e
 * doar aspectul. Numarul, CVV-ul si expirarea se genereaza la salvare.
 */
export function AdaugaCardDrawer({
  compact = false,
  conturi,
}: {
  compact?: boolean;
  conturi: ContBancar[];
}) {
  const router = useRouter();
  const [deschis, setDeschis] = useState(false);
  const [tematica, setTematica] = useState<StilCard>("standard");
  const [idCont, setIdCont] = useState<string>(conturi[0]?.id ?? "");
  const [tip, setTip] = useState<TipCard>("fizic");
  const [eroare, setEroare] = useState<string | null>(null);
  const [seTrimite, startTransition] = useTransition();

  function adauga() {
    setEroare(null);
    startTransition(async () => {
      const rezultat = await adaugaCard(tematica, idCont, tip);
      if (rezultat.eroare) {
        setEroare(rezultat.eroare);
        return;
      }
      setDeschis(false);
      setTematica("standard");
      setTip("fizic");
      router.refresh();
    });
  }

  return (
    <Drawer
      open={deschis}
      onOpenChange={(v) => {
        setDeschis(v);
        if (v) setEroare(null);
      }}
    >
      {compact ? (
        <DrawerTrigger
          aria-label="Adaugă card"
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-primary-600 text-white shadow-btn transition-colors hover:bg-primary-700 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
        >
          <Plus size={20} strokeWidth={1.75} aria-hidden />
        </DrawerTrigger>
      ) : (
        <DrawerTrigger className="flex h-[52px] w-full items-center justify-center gap-2 rounded-field bg-primary-600 text-[15px] font-semibold text-white shadow-btn transition-colors duration-150 ease-soft hover:bg-primary-700 active:scale-[0.98] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25">
          <CreditCard size={18} strokeWidth={1.75} aria-hidden />
          Adaugă cardul tău
        </DrawerTrigger>
      )}

      <DrawerContent
        title="Adaugă un card nou"
        description="Alege contul din care va plăti — restul detaliilor se generează automat."
        className="h-[90vh]"
        footer={
          <Button
            className="w-full"
            loading={seTrimite}
            disabled={!idCont}
            onClick={adauga}
          >
            Adaugă cardul
          </Button>
        }
      >
        <div className="flex flex-col gap-3">
          {eroare ? <Banda ton="eroare">{eroare}</Banda> : null}

          {conturi.length === 0 ? (
            <Banda ton="info">
              Ai nevoie întâi de un cont bancar. Deschide unul din secțiunea Conturi.
            </Banda>
          ) : null}

          <Sectiune titlu="Contul cardului" />
          {conturi.map((cont) => (
            <button
              key={cont.id}
              type="button"
              onClick={() => setIdCont(cont.id)}
              className={cn(
                "flex items-center gap-4 rounded-card border p-4 text-left transition-colors duration-150 ease-soft",
                "focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25",
                idCont === cont.id
                  ? "border-primary-500 bg-primary-500/12"
                  : "border-line bg-surface hover:bg-muted",
              )}
            >
              <span className="min-w-0 flex-1">
                <span className="block text-[15px] font-semibold text-ink">{cont.nume}</span>
                <span className="block text-[13px] text-ink-faint">
                  {formateazaSuma(cont.sold, cont.valuta)} · {cont.ibanMascat}
                </span>
              </span>
              {idCont === cont.id ? (
                <Check size={20} strokeWidth={1.75} aria-hidden className="shrink-0 text-primary-600" />
              ) : null}
            </button>
          ))}

          <Sectiune titlu="Tipul cardului" />
          {(["fizic", "virtual"] as TipCard[]).map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setTip(t)}
              className={cn(
                "flex items-center gap-4 rounded-card border p-4 text-left transition-colors duration-150 ease-soft",
                "focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25",
                tip === t
                  ? "border-primary-500 bg-primary-500/12"
                  : "border-line bg-surface hover:bg-muted",
              )}
            >
              <span className="min-w-0 flex-1">
                <span className="block text-[15px] font-semibold text-ink">
                  {t === "fizic" ? "Card fizic" : "Card virtual"}
                </span>
                <span className="block text-[13px] text-ink-faint">
                  {t === "fizic"
                    ? "Pentru plăți la magazin și online."
                    : "Doar pentru plăți online, emis instant în aplicație."}
                </span>
              </span>
              {tip === t ? (
                <Check size={20} strokeWidth={1.75} aria-hidden className="shrink-0 text-primary-600" />
              ) : null}
            </button>
          ))}

          <Sectiune titlu="Tematica" />

          {TEMATICI.map((stil) => (
            <button
              key={stil}
              type="button"
              onClick={() => setTematica(stil)}
              className={cn(
                "flex items-center gap-4 rounded-card border p-4 text-left transition-colors duration-150 ease-soft",
                "focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25",
                tematica === stil
                  ? "border-primary-500 bg-primary-500/12"
                  : "border-line bg-surface hover:bg-muted",
              )}
            >
              <span
                className="h-14 w-20 shrink-0 rounded-field shadow-sm"
                style={{ background: GRADIENTE_STIL_CARD[stil] }}
                aria-hidden
              />
              <span className="min-w-0 flex-1">
                <span className="block text-[15px] font-semibold text-ink">
                  {ETICHETE_STIL_CARD[stil]}
                </span>
                <span className="block text-[13px] text-ink-faint">{DESCRIERI_STIL_CARD[stil]}</span>
              </span>
              {tematica === stil ? (
                <Check size={20} strokeWidth={1.75} aria-hidden className="shrink-0 text-primary-600" />
              ) : null}
            </button>
          ))}
        </div>
      </DrawerContent>
    </Drawer>
  );
}

function Sectiune({ titlu }: { titlu: string }) {
  return (
    <h3 className="mt-2 text-[13px] font-semibold text-ink-faint first:mt-0">{titlu}</h3>
  );
}
