"use client";

import { useState, useTransition } from "react";
import { CheckCircle2, CreditCard, Lock } from "lucide-react";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { Camp } from "@/components/ui/camp";
import { Drawer, DrawerContent, DrawerTrigger } from "@/components/ui/drawer";
import { obtineProdus } from "@/lib/data/produse";
import { formateazaSuma } from "@/lib/utils";
import { ProdusVizual } from "./produs-vizual";

/** 4111111111111111 -> "4111 1111 1111 1111", maxim 16 cifre. */
function formateazaNumarCard(valoare: string) {
  const cifre = valoare.replace(/\D/g, "").slice(0, 16);
  return (cifre.match(/.{1,4}/g) ?? []).join(" ");
}

/** 1225 -> "12/25", maxim 4 cifre. */
function formateazaExpirare(valoare: string) {
  const cifre = valoare.replace(/\D/g, "").slice(0, 4);
  if (cifre.length <= 2) return cifre;
  return `${cifre.slice(0, 2)}/${cifre.slice(2)}`;
}

function formularValid(date: {
  numarCard: string;
  numeCard: string;
  expirare: string;
  cvv: string;
}) {
  const cifreCard = date.numarCard.replace(/\D/g, "");
  const [luna] = date.expirare.split("/");

  return (
    cifreCard.length === 16 &&
    date.numeCard.trim().length >= 3 &&
    /^\d{2}\/\d{2}$/.test(date.expirare) &&
    Number(luna) >= 1 &&
    Number(luna) <= 12 &&
    /^\d{3,4}$/.test(date.cvv)
  );
}

const FORM_INITIAL = { numarCard: "", numeCard: "", expirare: "", cvv: "" };

/**
 * Drawer de cumparare: rezumatul produsului + formular de card.
 * Doar UI momentan — nu trimite nimic, doar simuleaza o plata reusita.
 *
 * Primeste doar slug-ul (nu produsul intreg): un obiect cu o componenta de
 * icoana nu poate trece ca prop dintr-o pagina server intr-un client
 * component, deci produsul se cauta aici, in client.
 */
export function CumparaDrawer({ slug }: { slug: string }) {
  const produs = obtineProdus(slug);
  const [deschis, setDeschis] = useState(false);
  const [pas, setPas] = useState<"form" | "succes">("form");
  const [date, setDate] = useState(FORM_INITIAL);
  const [eroare, setEroare] = useState<string | null>(null);
  const [seProceseaza, startTransition] = useTransition();

  if (!produs) return null;

  function reseteaza(v: boolean) {
    setDeschis(v);
    if (!v) {
      setPas("form");
      setDate(FORM_INITIAL);
      setEroare(null);
    }
  }

  function plateste() {
    setEroare(null);

    if (!formularValid(date)) {
      setEroare("Verifică datele cardului — par incomplete sau greșite.");
      return;
    }

    startTransition(async () => {
      await new Promise((resolve) => setTimeout(resolve, 900));
      setPas("succes");
    });
  }

  return (
    <Drawer open={deschis} onOpenChange={reseteaza}>
      <DrawerTrigger className="flex h-[52px] w-full items-center justify-center gap-2 rounded-field bg-primary-600 text-[15px] font-semibold text-white shadow-btn transition-colors duration-150 ease-soft hover:bg-primary-700 active:scale-[0.98] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25">
        <CreditCard size={18} strokeWidth={1.75} aria-hidden />
        Cumpără acum
      </DrawerTrigger>

      <DrawerContent
        title={pas === "succes" ? "Comandă plasată" : "Finalizează comanda"}
        description={
          pas === "succes"
            ? "Confirmarea comenzii tale."
            : "Rezumatul comenzii și datele cardului."
        }
        className="h-[92vh]"
        footer={
          pas === "form" ? (
            <Button className="w-full" loading={seProceseaza} onClick={plateste}>
              Plătește {formateazaSuma(produs.pret)}
            </Button>
          ) : (
            <Button className="w-full" onClick={() => reseteaza(false)}>
              Închide
            </Button>
          )
        }
      >
        {pas === "succes" ? (
          <div className="flex flex-col items-center gap-3 py-10 text-center">
            <CheckCircle2 size={48} strokeWidth={1.5} className="animate-pop text-success" />
            <p className="text-[16px] font-semibold text-ink">Comanda a fost plasată</p>
            <p className="max-w-xs text-[13.5px] leading-[19px] text-ink-faint">
              {produs.nume} · {formateazaSuma(produs.pret)}
            </p>
          </div>
        ) : (
          <div className="flex flex-col gap-5">
            <div className="flex items-center gap-3 rounded-card border border-line p-3">
              <ProdusVizual produs={produs} marime="mic" />
              <div className="min-w-0 flex-1">
                <p className="truncate text-[14.5px] font-semibold text-ink">{produs.nume}</p>
                <p className="tabular text-[13.5px] text-ink-faint">
                  {formateazaSuma(produs.pret)}
                </p>
              </div>
            </div>

            {eroare ? <Banda ton="eroare">{eroare}</Banda> : null}

            <div className="flex flex-col gap-4">
              <Camp
                eticheta="Număr card"
                icoana={CreditCard}
                inputMode="numeric"
                placeholder="1234 5678 9012 3456"
                value={date.numarCard}
                onChange={(e) =>
                  setDate((d) => ({ ...d, numarCard: formateazaNumarCard(e.target.value) }))
                }
              />

              <Camp
                eticheta="Nume pe card"
                placeholder="ION POPESCU"
                value={date.numeCard}
                onChange={(e) =>
                  setDate((d) => ({ ...d, numeCard: e.target.value.toUpperCase() }))
                }
              />

              <div className="grid grid-cols-2 gap-4">
                <Camp
                  eticheta="Expiră (LL/AA)"
                  inputMode="numeric"
                  placeholder="12/28"
                  value={date.expirare}
                  onChange={(e) =>
                    setDate((d) => ({ ...d, expirare: formateazaExpirare(e.target.value) }))
                  }
                />

                <Camp
                  eticheta="CVV"
                  icoana={Lock}
                  inputMode="numeric"
                  placeholder="123"
                  value={date.cvv}
                  onChange={(e) =>
                    setDate((d) => ({ ...d, cvv: e.target.value.replace(/\D/g, "").slice(0, 4) }))
                  }
                />
              </div>
            </div>

            <p className="flex items-center gap-1.5 text-[12px] text-ink-faint">
              <Lock size={13} strokeWidth={1.75} aria-hidden />
              Datele cardului nu sunt încă trimise nicăieri — doar interfața e gata.
            </p>
          </div>
        )}
      </DrawerContent>
    </Drawer>
  );
}
