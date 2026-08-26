"use client";

import { ArrowLeft, ArrowLeftRight, Check, ChevronRight, Copy, Info, Lock } from "lucide-react";
import { useState, useTransition } from "react";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { Drawer, DrawerContent, DrawerTrigger } from "@/components/ui/drawer";
import type { ContBancar } from "@/lib/data/conturi";
import { schimbaValuta } from "@/lib/actions/schimb-valutar";
import { formateazaIban, formateazaSuma } from "@/lib/utils";
import { DESPRE_VALUTA, VALUTE, type Valuta } from "@/lib/valute";

/**
 * Meniul unui cont bancar — trei puncte pe cardul lui.
 *
 * Meniul apartine obiectului pe care il atinge. Prima varianta il pusese in
 * antetul dashboardului, langa clopotel si avatar: acolo erau deja doua
 * controale despre „mine", iar al treilea nu spunea despre CE cont vorbeste
 * cand omul are mai multe. Pe card, referentul e limpede fara sa scrie nimeni
 * nimic.
 *
 * Cele trei intrari sunt capabilitati care exista deja in aplicatie, nu functii
 * inventate pentru meniu. `schimbaValuta` in special: actiunea si RPC-ul
 * (schimba_valuta_cont) erau scrise de la 0013, dar nicio componenta n-o putea
 * declansa — cod mort in interfata.
 *
 * Datele personale si inchiderea relatiei cu banca NU sunt aici: acelea sunt
 * despre om, nu despre cont, si stau in Setari.
 */

type Ecran = "meniu" | "detalii" | "valuta";

export function MeniuCont({ cont }: { cont: ContBancar }) {
  const [deschis, setDeschis] = useState(false);
  const [ecran, setEcran] = useState<Ecran>("meniu");
  const [copiat, setCopiat] = useState(false);

  function comutaDeschis(valoare: boolean) {
    setDeschis(valoare);
    // Meniul se intoarce la prima pagina cand se inchide, altfel se redeschide
    // fix unde l-a lasat omul acum trei zile.
    if (!valoare) setEcran("meniu");
  }

  async function copiazaIban() {
    await navigator.clipboard.writeText(cont.iban);
    setCopiat(true);
    setTimeout(() => setCopiat(false), 2000);
  }

  const titlu =
    ecran === "detalii" ? "Detaliile contului" : ecran === "valuta" ? "Schimbă valuta" : cont.nume;

  return (
    <Drawer open={deschis} onOpenChange={comutaDeschis}>
      <DrawerTrigger
        aria-label={`Acțiuni pentru ${cont.nume}`}
        className="-mr-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-ink-faint transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
      >
        {/* Trei puncte desenate, nu o icoana din set: la marimea asta punctele
            din lucide-react se estompeaza pe ecrane cu densitate mica. */}
        <span className="flex flex-col gap-[3px]" aria-hidden>
          <span className="h-[3px] w-[3px] rounded-full bg-current" />
          <span className="h-[3px] w-[3px] rounded-full bg-current" />
          <span className="h-[3px] w-[3px] rounded-full bg-current" />
        </span>
      </DrawerTrigger>

      <DrawerContent title={titlu} description={formateazaIban(cont.iban)}>
        {/* Inapoi, nu doar „X". Prima varianta avea navigare intr-un singur
            sens: din submeniu se putea doar inchide tot. */}
        {ecran !== "meniu" ? (
          <button
            type="button"
            onClick={() => setEcran("meniu")}
            className="-mt-1 mb-3 inline-flex items-center gap-1.5 rounded-field py-1 pr-2 text-[13px] font-medium text-primary-600 transition-colors hover:text-primary-700 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
          >
            <ArrowLeft size={15} strokeWidth={2} aria-hidden />
            Înapoi
          </button>
        ) : null}

        {ecran === "meniu" ? (
          <Meniu
            cont={cont}
            copiat={copiat}
            onCopiaza={copiazaIban}
            onDetalii={() => setEcran("detalii")}
            onValuta={() => setEcran("valuta")}
          />
        ) : ecran === "detalii" ? (
          <Detalii cont={cont} />
        ) : (
          <SchimbaValuta cont={cont} onGata={() => comutaDeschis(false)} />
        )}
      </DrawerContent>
    </Drawer>
  );
}

function RandMeniu({
  icoana,
  eticheta,
  descriere,
  dezactivat,
  onClick,
}: {
  icoana: React.ReactNode;
  eticheta: string;
  descriere?: string;
  dezactivat?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={dezactivat}
      className="flex w-full items-center gap-3 rounded-field px-3 py-3 text-left transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-transparent"
    >
      <span className="shrink-0 text-ink-faint">{icoana}</span>
      <span className="min-w-0 flex-1">
        <span className="block text-[15px] font-medium text-ink">{eticheta}</span>
        {descriere ? (
          <span className="block text-[12.5px] leading-[17px] text-ink-faint">{descriere}</span>
        ) : null}
      </span>
      {!dezactivat ? (
        <ChevronRight size={16} strokeWidth={1.75} aria-hidden className="shrink-0 text-ink-faint" />
      ) : null}
    </button>
  );
}

function Meniu({
  cont,
  copiat,
  onCopiaza,
  onDetalii,
  onValuta,
}: {
  cont: ContBancar;
  copiat: boolean;
  onCopiaza: () => void;
  onDetalii: () => void;
  onValuta: () => void;
}) {
  return (
    <div className="flex flex-col">
      {cont.blocatDeBanca ? (
        <div className="mb-2">
          <Banda ton="eroare">
            Contul e blocat de bancă. Din el nu pot pleca bani până la deblocare.
          </Banda>
        </div>
      ) : null}

      <RandMeniu
        icoana={
          copiat ? (
            <Check size={19} strokeWidth={1.75} aria-hidden className="animate-pop text-success" />
          ) : (
            <Copy size={19} strokeWidth={1.75} aria-hidden />
          )
        }
        eticheta={copiat ? "IBAN copiat" : "Copiază IBAN-ul"}
        onClick={onCopiaza}
      />
      <RandMeniu
        icoana={<Info size={19} strokeWidth={1.75} aria-hidden />}
        eticheta="Detaliile contului"
        descriere="IBAN, valută, data deschiderii"
        onClick={onDetalii}
      />
      <RandMeniu
        icoana={
          cont.blocatDeBanca ? (
            <Lock size={19} strokeWidth={1.75} aria-hidden />
          ) : (
            <ArrowLeftRight size={19} strokeWidth={1.75} aria-hidden />
          )
        }
        eticheta="Schimbă valuta contului"
        // Dezactivat cu motivul scris, nu ascuns: un rand care dispare il lasa
        // pe om sa creada ca functia nu exista.
        descriere={
          cont.blocatDeBanca
            ? "Indisponibil cât contul e blocat"
            : `Acum în ${cont.valuta}, la cursul BNR`
        }
        dezactivat={cont.blocatDeBanca}
        onClick={onValuta}
      />
    </div>
  );
}

function Rand({ eticheta, valoare, mono }: { eticheta: string; valoare: string; mono?: boolean }) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-line py-3 last:border-0">
      <span className="text-[13px] text-ink-faint">{eticheta}</span>
      <span className={`text-right text-[15px] text-ink ${mono ? "tabular" : ""}`}>{valoare}</span>
    </div>
  );
}

function Detalii({ cont }: { cont: ContBancar }) {
  return (
    <div>
      <Rand eticheta="Nume" valoare={cont.nume} />
      <Rand eticheta="IBAN" valoare={formateazaIban(cont.iban)} mono />
      <Rand eticheta="Valută" valoare={`${cont.valuta} · ${DESPRE_VALUTA[cont.valuta].nume}`} />
      <Rand eticheta="Sold" valoare={formateazaSuma(cont.sold, cont.valuta)} mono />
      <Rand
        eticheta="Deschis la"
        valoare={new Date(cont.creatLa).toLocaleDateString("ro-RO", {
          day: "numeric",
          month: "long",
          timeZone: "Europe/Bucharest",
          year: "numeric",
        })}
      />
      <Rand eticheta="Stare" valoare={cont.blocatDeBanca ? "Blocat de bancă" : "Activ"} />
    </div>
  );
}

function SchimbaValuta({ cont, onGata }: { cont: ContBancar; onGata: () => void }) {
  const [aleasa, setAleasa] = useState<Valuta | null>(null);
  const [eroare, setEroare] = useState<string | null>(null);
  const [seTrimite, startTransition] = useTransition();

  const altele = VALUTE.filter((valuta) => valuta !== cont.valuta);

  return (
    <div className="flex flex-col gap-4">
      <p className="text-[13.5px] leading-[19px] text-ink-soft">
        Tot soldul contului se convertește la cursul BNR din ziua de azi. Restul datelor
        contului — IBAN, nume — rămân neschimbate.
      </p>

      <div className="flex flex-col gap-2">
        {altele.map((valuta) => (
          <button
            key={valuta}
            type="button"
            onClick={() => setAleasa(valuta)}
            className={`flex items-center gap-3 rounded-field border px-4 py-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25 ${
              aleasa === valuta
                ? "border-primary-600 bg-primary-50"
                : "border-line bg-surface hover:bg-muted"
            }`}
          >
            <span className="tabular text-[15px] font-semibold text-ink">{valuta}</span>
            <span className="flex-1 text-[13px] text-ink-faint">
              {DESPRE_VALUTA[valuta].nume}
            </span>
            {aleasa === valuta ? (
              <Check size={17} strokeWidth={2} aria-hidden className="text-primary-600" />
            ) : null}
          </button>
        ))}
      </div>

      {eroare ? <Banda ton="eroare">{eroare}</Banda> : null}

      <Button
        loading={seTrimite}
        disabled={aleasa === null}
        onClick={() =>
          startTransition(async () => {
            if (!aleasa) return;
            setEroare(null);
            const rezultat = await schimbaValuta(cont.id, aleasa);
            if (rezultat.eroare) setEroare(rezultat.eroare);
            else onGata();
          })
        }
      >
        {aleasa ? `Schimbă în ${aleasa}` : "Alege o valută"}
      </Button>
    </div>
  );
}
