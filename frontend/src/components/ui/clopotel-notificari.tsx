"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Bell, CheckCheck } from "lucide-react";
import { Banda } from "@/components/ui/banda";
import { Bulina } from "@/components/ui/bulina";
import { Drawer, DrawerContent } from "@/components/ui/drawer";
import { createClient } from "@/lib/supabase/client";
import { cn, etichetaZi, formateazaOra as ora } from "@/lib/utils";

/**
 * Clopotelul cu notificarile utilizatorului.
 *
 * Citeste **direct din Supabase**, nu prin FastAPI: tabela `notificari` are
 * politici RLS care lasa fiecare om sa-si vada si sa-si marcheze doar propriile
 * randuri, deci e exact cazul de la ARCHITECTURE.md 4.1 — citire simpla,
 * scopata pe utilizator, unde backendul n-ar adauga nimic. Scrierea ramane a
 * lui (nu exista politica de INSERT).
 *
 * Pana acum clopotelul din dashboard era un `<span>` decorativ: notificarile se
 * scriau in baza, dar nu le vedea nimeni.
 */

type Notificare = {
  id: string;
  titlu: string;
  mesaj: string;
  tip: "info" | "atentionare" | "blocare" | "deblocare";
  citita_la: string | null;
  creat_la: string;
};

const STIL_TIP: Record<Notificare["tip"], string> = {
  info: "bg-primary-50 text-primary-700",
  atentionare: "bg-warning/10 text-warning",
  blocare: "bg-danger/8 text-danger",
  deblocare: "bg-success/10 text-success",
};

/**
 * Notificarile de credit poarta id-ul cererii intr-un marcaj la finalul
 * mesajului. Tabela `notificari` nu e a noastra — n-are migratie in repo — deci
 * nu i-am adaugat o coloana; marcajul o lasa neatinsa si face notificarea
 * utilizabila, nu doar informativa.
 */
const MARCAJ_CERERE = /\n*\[cerere:([0-9a-f-]{36})\]\s*$/i;

function idCerere(mesaj: string): string | null {
  return MARCAJ_CERERE.exec(mesaj)?.[1] ?? null;
}

function textCurat(mesaj: string): string {
  return mesaj.replace(MARCAJ_CERERE, "").trim();
}

const ETICHETA_TIP: Record<Notificare["tip"], string> = {
  info: "Informare",
  atentionare: "Atenție",
  blocare: "Blocare",
  deblocare: "Deblocare",
};

export function ClopotelNotificari() {
  const [notificari, setNotificari] = useState<Notificare[]>([]);
  const [deschis, setDeschis] = useState(false);
  const [eroare, setEroare] = useState<string | null>(null);

  const incarca = useCallback(async () => {
    const supabase = createClient();
    const {
      data: { user },
    } = await supabase.auth.getUser();
    if (!user) return;

    // Filtrul pe utilizator e OBLIGATORIU, nu redundant fata de RLS: politica
    // de select e `auth.uid() = id_utilizator OR este_administrator()`, deci un
    // administrator vedea aici notificarile tuturor. Politica de update, in
    // schimb, permite doar randurile proprii — asa ca "marcheaza toate ca
    // citite" atingea 0 randuri pentru cele straine si parea ca nu merge.
    //
    // Clopotelul e personal: arata ce e al tau, indiferent ce drepturi ai.
    const { data, error: eroareCitire } = await supabase
      .from("notificari")
      .select("id,titlu,mesaj,tip,citita_la,creat_la")
      .eq("id_utilizator", user.id)
      .order("creat_la", { ascending: false })
      .limit(30);

    if (eroareCitire) {
      setEroare("Nu am putut încărca notificările.");
      return;
    }
    setEroare(null);
    setNotificari((data as Notificare[] | null) ?? []);
  }, []);

  useEffect(() => {
    void incarca();
  }, [incarca]);

  const necitite = notificari.filter((n) => n.citita_la === null).length;

  async function marcheazaCitite() {
    const deMarcat = notificari.filter((n) => n.citita_la === null).map((n) => n.id);
    if (deMarcat.length === 0) return;

    // Optimist, dar verificat: fara citirea erorii, interfata mintea — bulina
    // disparea, iar la reincarcare notificarile erau tot necitite.
    const acum = new Date().toISOString();
    setNotificari((vechi) =>
      vechi.map((n) => (n.citita_la === null ? { ...n, citita_la: acum } : n)),
    );

    const supabase = createClient();
    const { error: eroareScriere } = await supabase
      .from("notificari")
      .update({ citita_la: acum })
      .in("id", deMarcat);

    if (eroareScriere) {
      setEroare("Nu am putut marca notificările. Încearcă din nou.");
    }
    // Se reciteste oricum din baza: ecranul trebuie sa arate ce e chiar acolo,
    // nu ce am presupus noi.
    await incarca();
  }

  return (
    <>
      <button
        type="button"
        onClick={() => {
          setDeschis(true);
          void incarca();
        }}
        aria-label={
          necitite > 0 ? `Notificări, ${necitite} necitite` : "Notificări"
        }
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
                  onClick={marcheazaCitite}
                  className="mb-3 inline-flex items-center gap-1.5 text-[13px] font-semibold text-primary-600 hover:underline"
                >
                  <CheckCheck size={15} strokeWidth={2} aria-hidden />
                  Marchează toate ca citite
                </button>
              ) : null}

              <ul className="flex flex-col gap-2">
                {notificari.map((notificare) => (
                  <li
                    key={notificare.id}
                    // Necitit = accent pe muchia din stanga, nu un voal peste
                    // tot cardul: `bg-primary-50/40` e o culoare deschisa pusa
                    // la 40% peste fundal, care in tema intunecata spala textul
                    // si face necititele sa para dezactivate — exact invers.
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
                          STIL_TIP[notificare.tip],
                        )}
                      >
                        {ETICHETA_TIP[notificare.tip]}
                      </span>
                      <span className="text-[11.5px] text-ink-faint">
                        {etichetaZi(notificare.creat_la)} · {ora(notificare.creat_la)}
                      </span>
                    </div>

                    <p className="mt-1.5 text-[13.5px] font-semibold text-ink">
                      {notificare.titlu}
                    </p>
                    <p className="mt-0.5 whitespace-pre-line text-[13px] leading-[19px] text-ink-soft">
                      {textCurat(notificare.mesaj)}
                    </p>

                    {idCerere(notificare.mesaj) ? (
                      <Link
                        href={`/credite?discutie=${idCerere(notificare.mesaj)}`}
                        onClick={() => setDeschis(false)}
                        className="mt-2 inline-block text-[12.5px] font-semibold text-primary-600 hover:underline"
                      >
                        Deschide discuția →
                      </Link>
                    ) : null}
                  </li>
                ))}
              </ul>
            </>
          )}
        </DrawerContent>
      </Drawer>
    </>
  );
}
