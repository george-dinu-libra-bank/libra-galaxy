"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { Check, Copy, Eye, EyeOff, Lock, Unlock } from "lucide-react";
import { AdaugaCardDrawer } from "@/components/carduri/adauga-card-drawer";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { Drawer, DrawerContent, DrawerNested } from "@/components/ui/drawer";
import {
  comutaBlocareCard,
  obtineDateSensibileCard,
  type DateSensibileCard,
} from "@/lib/actions/carduri";
import type { CardAfisat } from "@/lib/data/carduri";
import { ETICHETE_STIL_CARD, GRADIENTE_STIL_CARD } from "@/lib/stil-card";
import { cn, formateazaSuma } from "@/lib/utils";

export function ListaCarduri({ carduri }: { carduri: CardAfisat[] }) {
  const router = useRouter();
  const [selectatId, setSelectatId] = useState<string | null>(null);
  const [seActualizeaza, startTransition] = useTransition();

  const selectat = carduri.find((c) => c.id === selectatId) ?? null;

  function comutaBlocare(card: CardAfisat) {
    startTransition(async () => {
      await comutaBlocareCard(card.id, !card.blocat);
      router.refresh();
    });
  }

  return (
    <div className="mx-auto w-full max-w-[440px] px-6 pb-6 pt-8 sm:max-w-2xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-[-0.02em] text-ink">Carduri</h1>
          <p className="mt-1 text-[15px] text-ink-soft">Cardurile asociate contului tău Galaxy Bank.</p>
        </div>
        {carduri.length > 0 ? <AdaugaCardDrawer compact /> : null}
      </div>

      {carduri.length === 0 ? (
        <section className="mt-6 flex flex-col items-center gap-4 rounded-card border border-dashed border-line bg-surface p-6 text-center shadow-sm">
          <p className="text-[15px] leading-[22px] text-ink-soft">
            Nu ai niciun card încă. Adaugă unul ca să poți trimite și primi bani.
          </p>
          <AdaugaCardDrawer />
        </section>
      ) : (
        <div className="mt-6 flex flex-col gap-4">
          {carduri.map((card) => (
            <button
              key={card.id}
              type="button"
              onClick={() => setSelectatId(card.id)}
              className="animate-fade-up rounded-card p-5 text-left text-white shadow-lg transition-transform duration-150 ease-soft active:scale-[0.98] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
              style={{
                background: GRADIENTE_STIL_CARD[card.stil],
                opacity: card.blocat ? 0.7 : 1,
              }}
            >
              <div className="flex items-start justify-between">
                <span className="text-[13px] text-white/80">Card {ETICHETE_STIL_CARD[card.stil]}</span>
                {card.blocat ? (
                  <span className="flex items-center gap-1 rounded-full bg-white/15 px-2.5 py-1 text-[11px] font-medium text-white">
                    <Lock size={12} strokeWidth={1.75} aria-hidden />
                    Blocat
                  </span>
                ) : null}
              </div>

              <p className="tabular mt-6 text-[19px] tracking-[0.08em]">{card.numarMascat}</p>

              <div className="mt-4 flex items-end justify-between">
                <div>
                  <p className="text-[10px] uppercase tracking-wide text-white/70">Sold</p>
                  <p className="tabular text-[13px]">{formateazaSuma(card.soldCurent)}</p>
                </div>
                <div className="text-right">
                  <p className="text-[10px] uppercase tracking-wide text-white/70">Expira</p>
                  <p className="tabular text-[13px]">{card.dataExpirare}</p>
                </div>
              </div>
            </button>
          ))}
        </div>
      )}

      <Drawer
        open={selectat !== null}
        onOpenChange={(deschis) => {
          if (!deschis) setSelectatId(null);
        }}
      >
        <DrawerContent
          title={selectat ? `Card ${ETICHETE_STIL_CARD[selectat.stil]}` : ""}
          description={selectat?.numarMascat ?? ""}
          footer={
            selectat ? (
              <Button
                varianta={selectat.blocat ? "primary" : "danger"}
                className="w-full"
                loading={seActualizeaza}
                iconaStanga={
                  selectat.blocat ? (
                    <Unlock size={18} strokeWidth={1.75} aria-hidden />
                  ) : (
                    <Lock size={18} strokeWidth={1.75} aria-hidden />
                  )
                }
                onClick={() => comutaBlocare(selectat)}
              >
                {selectat.blocat ? "Deblochează cardul" : "Blochează cardul"}
              </Button>
            ) : undefined
          }
        >
          {selectat ? <DetaliuCard key={selectat.id} card={selectat} /> : null}
        </DrawerContent>
      </Drawer>
    </div>
  );
}

function DetaliuCard({ card }: { card: CardAfisat }) {
  const [dateSensibile, setDateSensibile] = useState<DateSensibileCard | null>(null);
  const [confirmareDeschisa, setConfirmareDeschisa] = useState(false);
  const [eroare, setEroare] = useState<string | null>(null);
  const [seIncarca, startTransition] = useTransition();

  function confirmaAfisarea() {
    setEroare(null);
    startTransition(async () => {
      const rezultat = await obtineDateSensibileCard(card.id);
      if (rezultat.eroare || !rezultat.date) {
        setEroare(rezultat.eroare ?? "Nu am putut afisa datele cardului.");
        return;
      }
      setDateSensibile(rezultat.date);
      setConfirmareDeschisa(false);
    });
  }

  return (
    <div>
      <Rand eticheta="Tematica" valoare={ETICHETE_STIL_CARD[card.stil]} />
      <Rand
        eticheta="Numar"
        valoare={dateSensibile?.numar ?? card.numarMascat}
        mono
        copiabil={Boolean(dateSensibile)}
      />
      <Rand eticheta="CCV" valoare={dateSensibile?.ccv ?? "•••"} mono />
      <Rand eticheta="Expira" valoare={card.dataExpirare} mono />
      <Rand eticheta="Sold" valoare={formateazaSuma(card.soldCurent)} mono />
      <Rand eticheta="Stare" valoare={card.blocat ? "Blocat" : "Activ"} />

      <Button
        varianta="secondary"
        marime="sm"
        className="mt-4 w-full"
        iconaStanga={
          dateSensibile ? (
            <EyeOff size={18} strokeWidth={1.75} aria-hidden />
          ) : (
            <Eye size={18} strokeWidth={1.75} aria-hidden />
          )
        }
        onClick={() => {
          if (dateSensibile) {
            setDateSensibile(null);
            return;
          }
          setEroare(null);
          setConfirmareDeschisa(true);
        }}
      >
        {dateSensibile ? "Ascunde datele sensibile" : "Afiseaza datele sensibile"}
      </Button>

      <DrawerNested
        open={confirmareDeschisa}
        onOpenChange={(deschis) => {
          setConfirmareDeschisa(deschis);
          if (!deschis) setEroare(null);
        }}
      >
        <DrawerContent
          title="Afisezi datele sensibile?"
          description="Numarul complet si CCV-ul vor fi vizibile pe ecran. Asigura-te ca nu te vede nimeni."
          footer={
            <div className="flex flex-col gap-2">
              <Button className="w-full" loading={seIncarca} onClick={confirmaAfisarea}>
                Da, afiseaza datele
              </Button>
              <Button
                varianta="ghost"
                className="w-full"
                disabled={seIncarca}
                onClick={() => setConfirmareDeschisa(false)}
              >
                Renunta
              </Button>
            </div>
          }
        >
          <div className="flex flex-col gap-3">
            {eroare ? <Banda ton="eroare">{eroare}</Banda> : null}
            <p className="text-[15px] leading-[22px] text-ink-soft">
              Cardul {ETICHETE_STIL_CARD[card.stil]} — {card.numarMascat}
            </p>
          </div>
        </DrawerContent>
      </DrawerNested>
    </div>
  );
}

function Rand({
  eticheta,
  valoare,
  mono,
  copiabil,
}: {
  eticheta: string;
  valoare: string;
  mono?: boolean;
  copiabil?: boolean;
}) {
  const [copiat, setCopiat] = useState(false);

  async function copiaza() {
    try {
      await navigator.clipboard.writeText(valoare.replace(/\s+/g, ""));
      setCopiat(true);
      setTimeout(() => setCopiat(false), 1500);
    } catch {
      // clipboard indisponibil (ex. context non-securizat) — nu blocam UI-ul
    }
  }

  return (
    <div className="flex items-center justify-between gap-4 border-b border-line py-3 last:border-0">
      <span className="text-[13px] text-ink-faint">{eticheta}</span>
      <span className="flex items-center gap-2">
        <span className={cn("text-right text-[15px] text-ink", mono && "tabular")}>{valoare}</span>
        {copiabil ? (
          <button
            type="button"
            onClick={copiaza}
            aria-label={copiat ? "Copiat" : `Copiaza ${eticheta.toLowerCase()}`}
            className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-ink-faint transition-colors hover:bg-primary-50 hover:text-primary-600 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
          >
            {copiat ? (
              <Check size={14} strokeWidth={1.75} aria-hidden className="text-success" />
            ) : (
              <Copy size={14} strokeWidth={1.75} aria-hidden />
            )}
          </button>
        ) : null}
      </span>
    </div>
  );
}
