"use client";

import Link from "next/link";
import { useState, useTransition, type ReactNode } from "react";
import { Bell, ChevronRight, LogOut, Moon, UserCog, Users, LifeBuoy } from "lucide-react";
import { AvatarProfil } from "@/components/ui/avatar-profil";
import { Button } from "@/components/ui/button";
import { Comutator } from "@/components/ui/comutator";
import { EditeazaTelefonDrawer } from "@/components/setari/editeaza-telefon-drawer";
import { InchideContul } from "@/components/setari/inchide-contul";
import { SecuritateDrawer } from "@/components/setari/securitate-drawer";
import { deconecteaza } from "@/lib/actions/auth";
import type { DispozitivAfisat } from "@/lib/data/dispozitive";
import { aplicaTema, type Tema } from "@/lib/tema";
import { Banda } from "@/components/ui/banda";
import type { StareStergere } from "@/lib/actions/stergere-cont";
import { cn, formateazaIban, mascheazaCnp } from "@/lib/utils";

type Profil = {
  nume: string;
  cnp: string;
  telefon: string;
  email: string;
  iban_cont: string;
  creat_la: string;
  /** URL public din Supabase Storage (lib/actions/profil.ts), null fara poza. */
  avatar_url: string | null;
  verification_status: string;
};

function initiale(nume: string) {
  return nume
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((parte) => parte[0]?.toUpperCase())
    .join("");
}

function Rand({
  eticheta,
  valoare,
  mono,
  actiune,
}: {
  eticheta: string;
  valoare: string;
  mono?: boolean;
  actiune?: ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-line py-3 last:border-0">
      <span className="text-[13px] text-ink-faint">{eticheta}</span>
      <div className="flex items-center gap-3">
        <span className={cn("text-right text-[15px] text-ink", mono && "tabular")}>{valoare}</span>
        {actiune}
      </div>
    </div>
  );
}

export function SetariClient({
  profil,
  tema,
  esteAdmin = false,
  biometrieActivata,
  dispozitive,
  stareStergere,
}: {
  profil: Profil;
  tema: Tema;
  esteAdmin?: boolean;
  biometrieActivata: boolean;
  dispozitive: DispozitivAfisat[];
  stareStergere: StareStergere | null;
}) {
  const [telefon, setTelefon] = useState(profil.telefon);
  const [notificari, setNotificari] = useState(true);
  const [temaIntunecata, setTemaIntunecata] = useState(tema === "dark");
  const [seIese, startTransition] = useTransition();

  function comutaTema() {
    const noua = temaIntunecata ? "light" : "dark";
    aplicaTema(noua);
    setTemaIntunecata(noua === "dark");
  }

  return (
    <div className="mx-auto w-full max-w-[440px] px-6 pb-6 pt-8 sm:max-w-2xl">
      <h1 className="text-xl font-bold tracking-[-0.02em] text-ink">Setări</h1>

      {/* O cerere de inchidere e o stare importanta a relatiei cu banca, nu un
          detaliu. Prima varianta o lasa ascunsa la doi taps sub o iconita fara
          eticheta: omul depunea cererea si pe urma nu mai avea de unde sa stie
          ca exista. */}
      {stareStergere?.cerere ? (
        <div className="mt-4">
          <Banda ton="info">
            Ai o cerere de închidere a contului în analiză. O poți retrage din secțiunea
            „Închiderea contului", mai jos.
          </Banda>
        </div>
      ) : null}

      <div className="mt-6 flex items-center gap-4 rounded-card bg-surface p-4 shadow-sm">
        {/* Cu poza incarcata din dashboard se arata poza; fara ea raman
            initialele, care spun mai mult decat iconita generica din AvatarProfil. */}
        {profil.avatar_url ? (
          <span className="h-14 w-14 shrink-0 overflow-hidden rounded-full">
            <AvatarProfil url={profil.avatar_url} nume={profil.nume} />
          </span>
        ) : (
          <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-primary-100 text-[18px] font-semibold text-primary-700">
            {initiale(profil.nume)}
          </span>
        )}
        <div className="min-w-0">
          <p className="truncate text-[17px] font-semibold text-ink">{profil.nume}</p>
          <p className="truncate text-[13px] text-ink-faint">{profil.email}</p>
        </div>
      </div>

      <h2 className="mb-2 mt-8 text-[13px] font-medium text-ink-faint">Date personale</h2>
      <div className="rounded-card bg-surface px-4 shadow-sm">
        <Rand eticheta="Titular" valoare={profil.nume} />
        <Rand eticheta="CNP" valoare={mascheazaCnp(profil.cnp)} mono />
        <Rand
          eticheta="Telefon"
          valoare={telefon}
          mono
          actiune={<EditeazaTelefonDrawer telefon={telefon} onSalvat={setTelefon} />}
        />
        <Rand eticheta="Email" valoare={profil.email} />
        <Rand eticheta="IBAN cont curent" valoare={formateazaIban(profil.iban_cont)} mono />
        <Rand
          eticheta="Client din"
          valoare={new Date(profil.creat_la).toLocaleDateString("ro-RO", {
            day: "numeric",
            month: "long",
            timeZone: "Europe/Bucharest",
            year: "numeric",
          })}
        />
      </div>

      <h2 className="mb-2 mt-6 text-[13px] font-medium text-ink-faint">Preferințe</h2>
      <div className="flex flex-col gap-2">
        <Link
          href="/beneficiari"
          className="flex items-center gap-3 rounded-card bg-surface px-4 py-3.5 shadow-sm transition-colors hover:bg-muted"
        >
          <Users size={20} strokeWidth={1.75} aria-hidden className="text-ink-faint" />
          <span className="flex-1 text-[15px] text-ink">Beneficiari</span>
          <ChevronRight size={18} strokeWidth={1.75} aria-hidden className="text-ink-faint" />
        </Link>

        <Link
          href="/sesizari"
          className="flex items-center gap-3 rounded-card bg-surface px-4 py-3.5 shadow-sm transition-colors hover:bg-muted"
        >
          <LifeBuoy size={20} strokeWidth={1.75} aria-hidden className="text-ink-faint" />
          <span className="flex-1 text-[15px] text-ink">Sesizări</span>
          <ChevronRight size={18} strokeWidth={1.75} aria-hidden className="text-ink-faint" />
        </Link>

        <div className="flex items-center gap-3 rounded-card bg-surface px-4 py-3.5 shadow-sm">
          <Bell size={20} strokeWidth={1.75} aria-hidden className="text-ink-faint" />
          <span className="flex-1 text-[15px] text-ink">Notificări push</span>
          <Comutator activ={notificari} onChange={() => setNotificari((v) => !v)} eticheta="Notificări push" />
        </div>

        <div className="flex items-center gap-3 rounded-card bg-surface px-4 py-3.5 shadow-sm">
          <Moon size={20} strokeWidth={1.75} aria-hidden className="text-ink-faint" />
          <span className="flex-1 text-[15px] text-ink">Temă întunecată</span>
          <Comutator activ={temaIntunecata} onChange={comutaTema} eticheta="Temă întunecată" />
        </div>

        <SecuritateDrawer
          biometrieActivata={biometrieActivata}
          areSelfieVerificat={profil.verification_status === "verified"}
          dispozitive={dispozitive}
        />
      </div>

      {esteAdmin ? (
        <>
          <h2 className="mb-2 mt-6 text-[13px] font-medium text-ink-faint">Administrare</h2>
          <Link
            href="/admin"
            className="flex items-center gap-3 rounded-card border border-primary-100 bg-primary-50 px-4 py-3.5 transition-colors hover:bg-primary-100"
          >
            <UserCog size={20} strokeWidth={1.75} aria-hidden className="text-primary-600" />
            <span className="flex-1">
              <span className="block text-[15px] font-medium text-primary-700">
                Panoul de administrare
              </span>
              <span className="block text-[12.5px] text-primary-600">
                Verificări de identitate și conturi semnalate
              </span>
            </span>
            <ChevronRight size={18} strokeWidth={1.75} aria-hidden className="text-primary-600" />
          </Link>
        </>
      ) : null}

      <Button
        varianta="ghost"
        loading={seIese}
        onClick={() => startTransition(async () => { await deconecteaza(); })}
        iconaStanga={!seIese ? <LogOut size={18} strokeWidth={1.75} aria-hidden /> : undefined}
        className="mt-8 w-full"
      >
        Deconectează-te
      </Button>

      <InchideContul stare={stareStergere} />
    </div>
  );
}
