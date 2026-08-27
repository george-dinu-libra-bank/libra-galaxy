"use client";

import Link from "next/link";
import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { Bell, CheckCheck } from "lucide-react";
import { Banda } from "@/components/ui/banda";
import { Bulina } from "@/components/ui/bulina";
import { Drawer, DrawerContent } from "@/components/ui/drawer";
import { marcheazaToateCitite } from "@/lib/actions/notificari";
import type { Notificare } from "@/lib/data/notificari";
import {
  idCerereDinNotificare,
  idInvestigatieDinNotificare,
  textFaraMarcaj,
} from "@/lib/notificari-credit";
import { cn, etichetaZi, formateazaOra as ora } from "@/lib/utils";

/**
 * Clopotelul cu notificarile utilizatorului.
 *
 * Primeste randurile ca props, citite pe server de `obtineNotificari`
 * (lib/data/notificari.ts) — nu-si mai face propria citire din browser. Existau
 * doua drumuri catre aceeasi tabela: cardul de pe dashboard (RSC + server
 * action) si clopotelul (client Supabase). REGULI.md #2 — s-a pastrat cel mai
 * integrat cu restul proiectului, iar clopotelul a ramas doar suprafata.
 *
 * Efect secundar util: filtrul pe utilizator vine acum din acelasi loc pentru
 * amandoua. Cat timp clopotelul citea singur, un administrator vedea in el
 * notificarile tuturor (politica de select o permite), dar putea marca doar
 * randurile proprii — deci "marcheaza toate ca citite" parea ca nu merge.
 */

const STIL_TIP: Record<string, string> = {
  info: "bg-primary-50 text-primary-700",
  atentionare: "bg-warning/10 text-warning",
  blocare: "bg-danger/8 text-danger",
  deblocare: "bg-success/10 text-success",
};

const ETICHETA_TIP: Record<string, string> = {
  info: "Informare",
  atentionare: "Atenție",
  blocare: "Blocare",
  deblocare: "Deblocare",
};

export function ClopotelNotificari({ notificari }: { notificari: Notificare[] }) {
  const router = useRouter();
  const [deschis, setDeschis] = useState(false);
  const [eroare, setEroare] = useState<string | null>(null);
  const [seTrimite, startTransition] = useTransition();

  const necitite = notificari.filter((n) => n.citita_la === null).length;

  function marcheaza() {
    setEroare(null);
    startTransition(async () => {
      const rezultat = await marcheazaToateCitite();
      if (rezultat.eroare) {
        // Fara citirea erorii, interfata mintea: bulina disparea, iar la
        // reincarcare notificarile erau tot necitite.
        setEroare(rezultat.eroare);
        return;
      }
      router.refresh();
    });
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setDeschis(true)}
        aria-expanded={deschis}
        aria-label={necitite > 0 ? `Notificări, ${necitite} necitite` : "Notificări"}
        className="relative flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-surface text-ink-soft shadow-sm transition-colors hover:text-ink focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
      >
        <Bell size={20} strokeWidth={1.75} aria-hidden />
        <Bulina numar={necitite} className="absolute -right-0.5 -top-0.5" />
      </button>

      <Drawer open={deschis} onOpenChange={setDeschis}>
        <DrawerContent
          title="Notificări"
          description={
            necitite > 0
              ? `${necitite} ${necitite === 1 ? "necitită" : "necitite"}`
              : "Ești la zi."
          }
          cuInchidere
        >
          {eroare ? (
            <div className="mb-3">
              <Banda ton="eroare">{eroare}</Banda>
            </div>
          ) : null}

          {notificari.length === 0 ? (
            <p className="py-6 text-center text-[13px] text-ink-faint">
              Nicio notificare încă.
            </p>
          ) : (
            <>
              {necitite > 0 ? (
                <button
                  type="button"
                  onClick={marcheaza}
                  disabled={seTrimite}
                  className="mb-3 inline-flex items-center gap-1.5 text-[13px] font-semibold text-primary-600 hover:underline disabled:opacity-50"
                >
                  <CheckCheck size={15} strokeWidth={2} aria-hidden />
                  Marchează toate ca citite
                </button>
              ) : null}

              <ul className="flex flex-col gap-2">
                {notificari.map((notificare) => {
                  const idCerere = idCerereDinNotificare(notificare.mesaj);
                  const idInvestigatie = idInvestigatieDinNotificare(notificare.mesaj);

                  return (
                    <li
                      key={notificare.id}
                      // Necitit = accent pe muchia din stanga, nu un voal peste
                      // tot cardul: o culoare deschisa la 40% peste fundal spala
                      // textul in tema intunecata si face necititele sa para
                      // dezactivate — exact invers decat trebuie.
                      className={cn(
                        "rounded-field border border-l-[3px] bg-surface p-3.5",
                        notificare.citita_la === null
                          ? "border-line border-l-danger"
                          : "border-line border-l-line",
                      )}
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        <span
                          className={cn(
                            "rounded-full px-2 py-0.5 text-[11px] font-medium",
                            STIL_TIP[notificare.tip] ?? STIL_TIP.info,
                          )}
                        >
                          {ETICHETA_TIP[notificare.tip] ?? ETICHETA_TIP.info}
                        </span>
                        <span className="text-[11.5px] text-ink-faint">
                          {etichetaZi(notificare.creat_la)} · {ora(notificare.creat_la)}
                        </span>
                      </div>

                      <p className="mt-1.5 text-[13.5px] font-semibold text-ink">
                        {notificare.titlu}
                      </p>
                      <p className="mt-0.5 whitespace-pre-line text-[13px] leading-[19px] text-ink-soft">
                        {textFaraMarcaj(notificare.mesaj)}
                      </p>

                      {idCerere ? (
                        <Link
                          href={`/credite?discutie=${idCerere}`}
                          onClick={() => setDeschis(false)}
                          className="mt-2 inline-block text-[12.5px] font-semibold text-primary-600 hover:underline"
                        >
                          Deschide discuția →
                        </Link>
                      ) : null}

                      {idInvestigatie ? (
                        <Link
                          href={`/investigatii/${idInvestigatie}`}
                          onClick={() => setDeschis(false)}
                          className="mt-2 inline-block text-[12.5px] font-semibold text-primary-600 hover:underline"
                        >
                          Vezi mesajul băncii →
                        </Link>
                      ) : null}
                    </li>
                  );
                })}
              </ul>
            </>
          )}
        </DrawerContent>
      </Drawer>
    </>
  );
}
