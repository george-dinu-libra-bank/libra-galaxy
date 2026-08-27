"use client";

import {
  ArrowLeft,
  ArrowLeftRight,
  Check,
  ChevronRight,
  Copy,
  Hourglass,
  Info,
  Lock,
  Pencil,
  Star,
  XCircle,
} from "lucide-react";
import { useState, useTransition } from "react";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { Camp } from "@/components/ui/camp";
import { Drawer, DrawerContent, DrawerTrigger } from "@/components/ui/drawer";
import type { ContBancar } from "@/lib/data/conturi";
import { schimbaValuta } from "@/lib/actions/schimb-valutar";
import {
  cereInchidereaContului,
  retrageInchidereaContului,
} from "@/lib/actions/inchidere-cont";
import { faContulPrincipal, redenumesteCont } from "@/lib/actions/conturi";
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

type Ecran = "meniu" | "detalii" | "valuta" | "inchide" | "redenumeste" | "principal";

/**
 * `celelalte` = conturile in care pot merge banii ramasi. Vin de la parinte, nu
 * se citesc aici: componenta e client-side, iar lista o are deja dashboardul.
 */
export function MeniuCont({
  cont,
  celelalte = [],
}: {
  cont: ContBancar;
  celelalte?: ContBancar[];
}) {
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
    ecran === "detalii"
      ? "Detaliile contului"
      : ecran === "valuta"
        ? "Schimbă valuta"
        : ecran === "inchide"
          ? "Închide contul"
          : ecran === "redenumeste"
            ? "Redenumește contul"
            : ecran === "principal"
              ? "Cont principal"
              : cont.nume;

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
            onInchide={() => setEcran("inchide")}
            onRedenumeste={() => setEcran("redenumeste")}
            onPrincipal={() => setEcran("principal")}
          />
        ) : ecran === "detalii" ? (
          <Detalii cont={cont} />
        ) : ecran === "redenumeste" ? (
          <Redenumeste cont={cont} onGata={() => comutaDeschis(false)} />
        ) : ecran === "principal" ? (
          <FaPrincipal cont={cont} onGata={() => comutaDeschis(false)} />
        ) : ecran === "inchide" ? (
          <InchideContul
            cont={cont}
            celelalte={celelalte}
            onGata={() => comutaDeschis(false)}
          />
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
  onInchide,
  onRedenumeste,
  onPrincipal,
}: {
  cont: ContBancar;
  copiat: boolean;
  onCopiaza: () => void;
  onDetalii: () => void;
  onValuta: () => void;
  onInchide: () => void;
  onRedenumeste: () => void;
  onPrincipal: () => void;
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
        icoana={<Pencil size={19} strokeWidth={1.75} aria-hidden />}
        eticheta="Redenumește contul"
        descriere="Doar eticheta; IBAN-ul și banii rămân"
        onClick={onRedenumeste}
      />
      <RandMeniu
        icoana={
          cont.estePrincipal || cont.blocatDeBanca ? (
            <Lock size={19} strokeWidth={1.75} aria-hidden />
          ) : (
            <Star size={19} strokeWidth={1.75} aria-hidden />
          )
        }
        eticheta="Fă-l contul principal"
        descriere={
          cont.estePrincipal
            ? "Acesta e deja contul principal"
            : cont.blocatDeBanca
              ? "Un cont blocat nu poate fi principal"
              : "IBAN-ul pe care îl dai mai departe"
        }
        dezactivat={cont.estePrincipal || cont.blocatDeBanca}
        onClick={onPrincipal}
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
      <RandMeniu
        icoana={
          cont.estePrincipal || cont.blocatDeBanca ? (
            <Lock size={19} strokeWidth={1.75} aria-hidden />
          ) : cont.cerereInchidere ? (
            <Hourglass size={19} strokeWidth={1.75} aria-hidden />
          ) : (
            <XCircle size={19} strokeWidth={1.75} aria-hidden />
          )
        }
        eticheta={cont.cerereInchidere ? "Cerere de închidere trimisă" : "Închide contul"}
        // Acelasi tratament ca la schimbul de valuta: dezactivat CU motivul
        // scris, nu ascuns. „Contul principal nu se poate inchide" e un raspuns;
        // un rand care lipseste e o ghicitoare.
        descriere={
          cont.estePrincipal
            ? "Contul principal nu se poate închide"
            : cont.blocatDeBanca
              ? "Indisponibil cât contul e blocat"
              : cont.cerereInchidere
                ? "În analiză la bancă · atinge pentru detalii"
                : "Banii rămași se mută în alt cont al tău"
        }
        dezactivat={cont.estePrincipal || cont.blocatDeBanca}
        onClick={onInchide}
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

/**
 * Inchiderea contului: ce se intampla, unde se duc banii, si butonul.
 *
 * Ecranul spune tot INAINTE de apasare — soldul care se muta, contul in care
 * ajunge, cardurile care se inchid odata cu el. O confirmare care nu enumera
 * consecintele nu e o confirmare, e un obstacol.
 *
 * Nicio garda de aici nu e singura aparare: contul principal, contul blocat,
 * soldul negativ si destinatia invalida sunt refuzate si de
 * `public.inchide_cont_bancar` (0040), in aceeasi tranzactie cu mutarea banilor.
 */
function InchideContul({
  cont,
  celelalte,
  onGata,
}: {
  cont: ContBancar;
  celelalte: ContBancar[];
  onGata: () => void;
}) {
  // Implicit contul principal, daca exista: e destinatia pe care o alege si
  // banca automat, deci propunerea porneste de la acelasi loc.
  const implicit = celelalte.find((c) => c.estePrincipal) ?? celelalte[0] ?? null;

  const [destinatia, setDestinatia] = useState<string | null>(implicit?.id ?? null);
  const [motiv, setMotiv] = useState("");
  const [eroare, setEroare] = useState<string | null>(null);
  const [seLucreaza, startTransition] = useTransition();

  const areBani = cont.sold > 0;
  const aleasa = celelalte.find((c) => c.id === destinatia) ?? null;

  function trimite() {
    startTransition(async () => {
      setEroare(null);
      const rezultat = await cereInchidereaContului(cont.id, destinatia, motiv);
      if (rezultat.eroare) setEroare(rezultat.eroare);
      else onGata();
    });
  }

  function retrage() {
    startTransition(async () => {
      setEroare(null);
      const rezultat = await retrageInchidereaContului(cont.cerereInchidere!.id);
      if (rezultat.eroare) setEroare(rezultat.eroare);
      else onGata();
    });
  }

  // Cererea deja depusa: se arata starea si drumul inapoi, nu inca un formular.
  if (cont.cerereInchidere) {
    return (
      <div className="flex flex-col gap-4">
        <Banda ton="info">
          Cererea de închidere e în analiză la bancă. Contul funcționează normal până
          la decizie — poți trimite și primi bani ca de obicei.
        </Banda>
        <p className="text-[12.5px] leading-[18px] text-ink-faint">
          Trimisă pe{" "}
          {new Date(cont.cerereInchidere.creatLa).toLocaleDateString("ro-RO", {
            day: "numeric",
            month: "long",
            year: "numeric",
          })}
          . Îți trimitem o notificare când primim un răspuns.
        </p>
        {eroare ? <Banda ton="eroare">{eroare}</Banda> : null}
        <Button varianta="secondary" loading={seLucreaza} onClick={retrage}>
          M-am răzgândit, retrage cererea
        </Button>
      </div>
    );
  }

  // Fara alt cont deschis, banii n-au unde sa se duca. Se spune pe loc, nu dupa
  // ce omul completeaza motivul si apasa.
  if (areBani && celelalte.length === 0) {
    return (
      <Banda ton="eroare">
        Contul are {formateazaSuma(cont.sold, cont.valuta)}, dar nu ai alt cont deschis
        în care banii să fie mutați. Deschide unul întâi.
      </Banda>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-[13px] leading-[19px] text-ink-soft">
        Contul nu mai poate trimite sau primi bani după închidere.{" "}
        <span className="font-medium text-ink">Istoricul tranzacțiilor rămâne</span> — o
        plată veche va arăta în continuare că a plecat din „{cont.nume}”.
      </p>

      {areBani ? (
        <div>
          <p className="text-[13px] font-medium text-ink">
            Unde se duc {formateazaSuma(cont.sold, cont.valuta)}
          </p>
          <p className="mt-0.5 text-[12.5px] leading-[17px] text-ink-faint">
            Banca mută banii la aprobare. Poți schimba alegerea până atunci.
          </p>

          <div className="mt-2 flex flex-col gap-1.5">
            {celelalte.map((alt) => (
              <button
                key={alt.id}
                type="button"
                onClick={() => setDestinatia(alt.id)}
                className={`flex items-center gap-3 rounded-field border px-3 py-2.5 text-left transition-colors focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25 ${
                  destinatia === alt.id
                    ? "border-primary-500 bg-primary-50"
                    : "border-line hover:bg-muted"
                }`}
              >
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[14px] font-medium text-ink">
                    {alt.nume}
                    {alt.estePrincipal ? (
                      <span className="font-normal text-ink-faint"> · Cont principal</span>
                    ) : null}
                  </span>
                  <span className="tabular block truncate text-[12px] text-ink-faint">
                    {alt.ibanMascat}
                  </span>
                </span>
                {destinatia === alt.id ? (
                  <Check size={16} strokeWidth={2} aria-hidden className="shrink-0 text-primary-600" />
                ) : null}
              </button>
            ))}
          </div>

          {aleasa && aleasa.valuta !== cont.valuta ? (
            <p className="mt-2 text-[12.5px] leading-[18px] text-ink-faint">
              Conturile sunt în valute diferite; suma se convertește în {aleasa.valuta} la
              cursul BNR din ziua aprobării.
            </p>
          ) : null}
        </div>
      ) : (
        <p className="text-[13px] text-ink-faint">
          Contul e pe zero, deci nu se mută niciun ban.
        </p>
      )}

      <Camp
        eticheta="Motiv (opțional)"
        value={motiv}
        onChange={(e) => setMotiv(e.target.value)}
        maxLength={500}
        placeholder="Îl vede analistul care decide"
      />

      {eroare ? <Banda ton="eroare">{eroare}</Banda> : null}

      <Button varianta="danger" loading={seLucreaza} onClick={trimite}>
        Trimite cererea de închidere
      </Button>

      <p className="text-center text-[12px] leading-[17px] text-ink-faint">
        Cererea o analizează un om. Poți retrage cererea oricând înainte de decizie.
      </p>
    </div>
  );
}

/**
 * Redenumirea contului. Fara cerere la banca: numele e o eticheta pentru ochii
 * clientului, nu un element de identificare. IBAN-ul, soldul si istoricul raman.
 */
function Redenumeste({ cont, onGata }: { cont: ContBancar; onGata: () => void }) {
  const [nume, setNume] = useState(cont.nume);
  const [eroare, setEroare] = useState<string | null>(null);
  const [seLucreaza, startTransition] = useTransition();

  const curatat = nume.trim();
  const valid = curatat.length >= 2 && curatat.length <= 60;
  const schimbat = curatat !== cont.nume;

  function salveaza() {
    startTransition(async () => {
      setEroare(null);
      const rezultat = await redenumesteCont(cont.id, curatat);
      if (rezultat.eroare) setEroare(rezultat.eroare);
      else onGata();
    });
  }

  return (
    <div className="flex flex-col gap-4">
      <Camp
        eticheta="Numele contului"
        value={nume}
        onChange={(e) => setNume(e.target.value)}
        maxLength={60}
        autoFocus
        ajutor="Între 2 și 60 de caractere. Îl vezi doar tu."
      />

      {eroare ? <Banda ton="eroare">{eroare}</Banda> : null}

      <Button loading={seLucreaza} disabled={!valid || !schimbat} onClick={salveaza}>
        Salvează numele
      </Button>
    </div>
  );
}

/**
 * Mutarea titlului de „cont principal".
 *
 * Fara cerere la banca — nu misca niciun ban si nu inchide nimic. Dar are doua
 * urmari reale, si de aceea sunt scrise INAINTE de apasare: IBAN-ul principal e
 * cel pe care omul il da mai departe, si e contul in care se strang banii la
 * inchiderea relatiei. Tot el devine contul care nu se mai poate inchide.
 */
function FaPrincipal({ cont, onGata }: { cont: ContBancar; onGata: () => void }) {
  const [eroare, setEroare] = useState<string | null>(null);
  const [seLucreaza, startTransition] = useTransition();

  function muta() {
    startTransition(async () => {
      setEroare(null);
      const rezultat = await faContulPrincipal(cont.id);
      if (rezultat.eroare) setEroare(rezultat.eroare);
      else onGata();
    });
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-[13px] leading-[19px] text-ink-soft">
        „{cont.nume}” devine contul tău principal. Se schimbă trei lucruri:
      </p>

      <ul className="flex flex-col gap-2 text-[13px] leading-[19px] text-ink-soft">
        <li className="flex gap-2">
          <span aria-hidden className="text-ink-faint">
            •
          </span>
          <span>
            <span className="tabular font-medium text-ink">{cont.ibanMascat}</span> devine
            IBAN-ul pe care îl dai mai departe.
          </span>
        </li>
        <li className="flex gap-2">
          <span aria-hidden className="text-ink-faint">
            •
          </span>
          <span>
            Dacă vei închide relația cu banca, aici se strâng banii din celelalte conturi.
          </span>
        </li>
        <li className="flex gap-2">
          <span aria-hidden className="text-ink-faint">
            •
          </span>
          <span>
            Contul acesta nu va mai putea fi închis, iar cel principal de acum se
            eliberează.
          </span>
        </li>
      </ul>

      <p className="text-[12.5px] leading-[18px] text-ink-faint">
        Banii nu se mișcă. Poți schimba oricând înapoi.
      </p>

      {eroare ? <Banda ton="eroare">{eroare}</Banda> : null}

      <Button loading={seLucreaza} onClick={muta}>
        Fă-l contul principal
      </Button>
    </div>
  );
}
