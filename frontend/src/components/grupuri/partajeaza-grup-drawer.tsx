"use client";

import { Check, Copy, Link2, Share2 } from "lucide-react";
import { useState } from "react";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { Drawer, DrawerContent, DrawerTrigger } from "@/components/ui/drawer";

type Copiat = "cod" | "link" | null;

/**
 * Invitatia intr-un grup: codul de acces si linkul care il contine.
 *
 * Linkul se construieste in client, din `window.location.origin`, ca sa fie
 * bun si pe localhost, si pe domeniul real, fara variabila de mediu in plus.
 */
export function PartajeazaGrupDrawer({ nume, token }: { nume: string; token: string }) {
  const [copiat, setCopiat] = useState<Copiat>(null);
  const [eroare, setEroare] = useState<string | null>(null);

  function link() {
    return `${window.location.origin}/grupuri?token=${token}`;
  }

  async function copiaza(ce: Exclude<Copiat, null>) {
    setEroare(null);

    try {
      await navigator.clipboard.writeText(ce === "cod" ? token : link());
      setCopiat(ce);
      setTimeout(() => setCopiat(null), 2000);
    } catch {
      setEroare("Nu am putut copia. Selectează textul manual.");
    }
  }

  async function partajeaza() {
    setEroare(null);

    // Pe telefon deschide foaia nativa de share; pe desktop, unde de obicei nu
    // exista, ramane copierea linkului.
    if (!navigator.share) {
      await copiaza("link");
      return;
    }

    try {
      await navigator.share({
        title: nume,
        text: `Intră în grupul „${nume}" din Galaxy Bank.`,
        url: link(),
      });
    } catch {
      // Utilizatorul a inchis foaia de share — nu e o eroare de aratat.
    }
  }

  return (
    <Drawer>
      <DrawerTrigger
        aria-label="Invită pe cineva în grup"
        className="flex h-9 items-center gap-1.5 rounded-full bg-primary-50 px-3 text-[13px] font-semibold text-primary-700 transition-colors hover:bg-primary-100 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
      >
        <Share2 size={16} strokeWidth={2} aria-hidden />
        Invită
      </DrawerTrigger>

      <DrawerContent
        title="Invită în grup"
        description="Oricine are codul poate intra în grup."
        footer={
          <Button className="w-full" onClick={partajeaza} iconaStanga={<Share2 size={18} strokeWidth={1.75} aria-hidden />}>
            Trimite invitația
          </Button>
        }
      >
        <div className="flex flex-col gap-4">
          {eroare ? <Banda ton="eroare">{eroare}</Banda> : null}

          <div className="rounded-card bg-primary-50 px-4 py-5 text-center">
            <p className="text-[12.5px] text-primary-700">Cod de acces</p>
            <p className="tabular mt-1 text-[22px] font-bold tracking-[0.12em] text-primary-900">
              {token}
            </p>
          </div>

          <div className="flex flex-col gap-2">
            <Button
              varianta="secondary"
              className="w-full"
              onClick={() => copiaza("cod")}
              iconaStanga={
                copiat === "cod" ? (
                  <Check size={18} strokeWidth={1.75} aria-hidden />
                ) : (
                  <Copy size={18} strokeWidth={1.75} aria-hidden />
                )
              }
            >
              {copiat === "cod" ? "Cod copiat" : "Copiază codul"}
            </Button>

            <Button
              varianta="secondary"
              className="w-full"
              onClick={() => copiaza("link")}
              iconaStanga={
                copiat === "link" ? (
                  <Check size={18} strokeWidth={1.75} aria-hidden />
                ) : (
                  <Link2 size={18} strokeWidth={1.75} aria-hidden />
                )
              }
            >
              {copiat === "link" ? "Link copiat" : "Copiază linkul"}
            </Button>
          </div>

          <p className="text-[12.5px] leading-[18px] text-ink-faint">
            Codul nu expiră. Dacă ajunge la cine nu trebuie, singura soluție acum e să
            faci un grup nou.
          </p>
        </div>
      </DrawerContent>
    </Drawer>
  );
}
