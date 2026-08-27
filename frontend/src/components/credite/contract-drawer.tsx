"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Check, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Drawer, DrawerContent } from "@/components/ui/drawer";
import type { ContractCerere } from "@/lib/data/credite";

/**
 * Contractul, asa cum il citeste clientul inainte sa semneze.
 *
 * Butonul de acceptare din subsol ramane blocat pana cand textul a fost derulat
 * pana jos. Nu e o masura impotriva clientului: pana acum „Semneaza" statea
 * langa trei cifre, iar omul nu avea ce citi. Verificarea nu pretinde ca
 * dovedeste lectura — dovedeste doar ca documentul a fost parcurs, si atat
 * spune si eticheta.
 *
 * `dangerouslySetInnerHTML` peste `contract.html` e sigur aici pentru ca textul
 * trece prin `credit/contract.py:sanitizeaza` la fiecare scriere: din browser
 * nu poate intra in coloana altceva decat etichetele permise.
 */
export function ContractDrawer({
  contract,
  acceptat,
  onAccepta,
}: {
  contract: ContractCerere;
  acceptat: boolean;
  /** Primeste si cat s-a derulat (0..1), pastrat in semnatura. */
  onAccepta: (derulat: number) => void;
}) {
  const [deschis, setDeschis] = useState(false);
  const [derulat, setDerulat] = useState(0);
  const zona = useRef<HTMLDivElement>(null);

  const masoara = useCallback(() => {
    const nod = zona.current;
    if (!nod) return;

    // Un contract mai scurt decat fereastra nu are ce derula: e citit din
    // momentul in care s-a deschis, altfel butonul n-ar putea fi apasat
    // niciodata.
    const deDerulat = nod.scrollHeight - nod.clientHeight;
    if (deDerulat <= 8) {
      setDerulat(1);
      return;
    }
    setDerulat(Math.min(1, nod.scrollTop / deDerulat));
  }, []);

  // Masuratoarea se face si la deschidere, nu doar la scroll: continutul se
  // monteaza odata cu drawerul, deci inaltimea nu exista mai devreme.
  useEffect(() => {
    if (!deschis) return;
    const temporizator = setTimeout(masoara, 60);
    return () => clearTimeout(temporizator);
  }, [deschis, masoara]);

  const citit = derulat >= 0.98;

  return (
    <>
      <button
        type="button"
        onClick={() => setDeschis(true)}
        className="flex w-full items-center gap-3 rounded-field border border-line bg-muted p-3.5 text-left transition-colors hover:bg-primary-50 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
      >
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-surface">
          <FileText size={20} strokeWidth={1.75} aria-hidden className="text-primary-600" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-[14px] font-semibold text-ink">Contractul de credit</span>
          <span className="block text-[12.5px] leading-[18px] text-ink-faint">
            {acceptat ? "Citit și acceptat" : "Citește-l înainte să semnezi"}
          </span>
        </span>
        {acceptat ? (
          <Check size={20} strokeWidth={1.75} aria-hidden className="shrink-0 text-success" />
        ) : (
          <span className="shrink-0 rounded-full bg-warning/10 px-2.5 py-1 text-[11px] font-medium text-warning">
            Necitit
          </span>
        )}
      </button>

      <Drawer open={deschis} onOpenChange={setDeschis}>
        <DrawerContent
          title="Contractul de credit"
          description="Citește-l până la capăt. Butonul de acceptare se deblochează la final."
          footer={
            <div className="flex flex-col gap-2">
              {!citit ? (
                <p
                  className="text-center text-[12.5px] text-ink-faint"
                  role="status"
                  aria-live="polite"
                >
                  Ai parcurs {Math.round(derulat * 100)}% din contract
                </p>
              ) : null}
              <Button
                className="w-full"
                disabled={!citit}
                onClick={() => {
                  onAccepta(derulat);
                  setDeschis(false);
                }}
                iconaStanga={<Check size={18} strokeWidth={1.75} aria-hidden />}
              >
                {citit ? "Am citit și sunt de acord" : "Derulează până la capăt"}
              </Button>
            </div>
          }
        >
          <div
            ref={zona}
            onScroll={masoara}
            tabIndex={0}
            className="contract-text max-h-[58vh] overflow-y-auto pr-1 text-[13.5px] leading-[21px] text-ink-soft focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
            dangerouslySetInnerHTML={{ __html: contract.html }}
          />
        </DrawerContent>
      </Drawer>
    </>
  );
}
