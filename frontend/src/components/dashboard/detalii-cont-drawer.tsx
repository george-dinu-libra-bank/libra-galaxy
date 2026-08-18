"use client";

import { Check, Copy, LogOut, ShieldCheck } from "lucide-react";
import { useState, useTransition } from "react";
import { Button } from "@/components/ui/button";
import { Drawer, DrawerContent, DrawerTrigger } from "@/components/ui/drawer";
import { deconecteaza } from "@/lib/actions/auth";
import { formateazaIban, mascheazaCnp } from "@/lib/utils";

type Profil = {
  nume: string;
  cnp: string;
  telefon: string;
  email: string;
  iban_cont: string;
  creat_la: string;
};

function Rand({ eticheta, valoare, mono }: { eticheta: string; valoare: string; mono?: boolean }) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-line py-3 last:border-0">
      <span className="text-[13px] text-ink-faint">{eticheta}</span>
      <span className={`text-right text-[15px] text-ink ${mono ? "tabular" : ""}`}>
        {valoare}
      </span>
    </div>
  );
}

/**
 * Detaliile contului nu merita o pagina proprie (DESIGN.md 8.1) — se deschid
 * intr-un drawer peste dashboard.
 */
export function DetaliiContDrawer({ profil }: { profil: Profil }) {
  const [copiat, setCopiat] = useState(false);
  const [seIese, startTransition] = useTransition();

  async function copiazaIban() {
    await navigator.clipboard.writeText(profil.iban_cont);
    setCopiat(true);
    setTimeout(() => setCopiat(false), 2000);
  }

  return (
    <Drawer>
      <DrawerTrigger className="w-full rounded-field border border-line bg-surface py-3 text-[13px] font-semibold text-primary-600 transition-colors hover:bg-primary-50 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25">
        Vezi detaliile contului
      </DrawerTrigger>

      <DrawerContent
        title="Detaliile contului"
        description="Datele cu care ti-am deschis contul curent Libra."
        footer={
          <Button
            varianta="ghost"
            loading={seIese}
            onClick={() => startTransition(async () => { await deconecteaza(); })}
            iconaStanga={!seIese ? <LogOut size={18} strokeWidth={1.75} aria-hidden /> : undefined}
            className="w-full"
          >
            Deconecteaza-te
          </Button>
        }
      >
        <div className="flex flex-col gap-4">
          <div className="rounded-field bg-primary-50 p-4">
            <p className="text-[13px] text-primary-700">IBAN cont curent</p>
            <p className="tabular mt-1 text-[15px] font-semibold tracking-[0.02em] text-primary-900">
              {formateazaIban(profil.iban_cont)}
            </p>
            <Button
              varianta="secondary"
              marime="sm"
              onClick={copiazaIban}
              iconaStanga={
                copiat ? (
                  <Check size={16} strokeWidth={1.75} aria-hidden className="animate-pop" />
                ) : (
                  <Copy size={16} strokeWidth={1.75} aria-hidden />
                )
              }
              className="mt-3"
            >
              {copiat ? "Copiat" : "Copiaza IBAN"}
            </Button>
          </div>

          <div>
            <Rand eticheta="Titular" valoare={profil.nume} />
            <Rand eticheta="CNP" valoare={mascheazaCnp(profil.cnp)} mono />
            <Rand eticheta="Telefon" valoare={profil.telefon} mono />
            <Rand eticheta="Email" valoare={profil.email} />
            <Rand
              eticheta="Cont deschis la"
              valoare={new Date(profil.creat_la).toLocaleDateString("ro-RO", {
                day: "numeric",
                month: "long",
                year: "numeric",
              })}
            />
          </div>

          <div className="flex gap-3 rounded-field bg-muted p-4">
            <ShieldCheck size={20} strokeWidth={1.75} aria-hidden className="mt-0.5 shrink-0 text-success" />
            <p className="text-[13px] leading-[19px] text-ink-soft">
              CNP-ul este afisat partial. Nu il comunica nimanui, nici macar unui
              angajat Libra.
            </p>
          </div>
        </div>
      </DrawerContent>
    </Drawer>
  );
}
