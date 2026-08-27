"use client";

import { useEffect, useRef, useState, useTransition } from "react";
import {
  Bold,
  Check,
  Italic,
  List,
  ListOrdered,
  Loader2,
  RotateCcw,
  Underline,
} from "lucide-react";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { Drawer, DrawerContent } from "@/components/ui/drawer";
import { regenereazaContract, salveazaContract } from "@/lib/actions/admin-credite";
import type { ContractCerere } from "@/lib/tipuri-admin";
import { cn } from "@/lib/utils";

/**
 * Editorul de contract din dosarul de credit.
 *
 * `contentEditable` si `document.execCommand`, nu o bibliotecă de editare:
 * contractul are nevoie de sase comenzi (bold, italic, subliniat, doua liste,
 * titlu), iar `execCommand` le da pe toate fara sa aduca 300 KB de JavaScript
 * intr-un ecran de administrare. E depreciat, dar nu exista browser care sa nu
 * il implementeze si nu exista inlocuitor standardizat.
 *
 * Ce iese de aici e continut neincrezut, chiar daca il scrie un analist:
 * backendul il taie la lista de etichete permise inainte sa il scrie in baza
 * (`credit/contract.py:sanitizeaza`). Aici nu se sanitizeaza nimic — doua liste
 * de etichete tinute in acord de mana ar diverge la prima modificare.
 *
 * Dupa trimiterea catre client editorul se blocheaza: contractul semnat trebuie
 * sa fie acelasi document pe care l-a citit omul.
 */

type Comanda = {
  id: string;
  eticheta: string;
  comanda: string;
  valoare?: string;
  icoana: typeof Bold;
};

const COMENZI: Comanda[] = [
  { id: "bold", eticheta: "Îngroșat", comanda: "bold", icoana: Bold },
  { id: "italic", eticheta: "Cursiv", comanda: "italic", icoana: Italic },
  { id: "underline", eticheta: "Subliniat", comanda: "underline", icoana: Underline },
  { id: "ul", eticheta: "Listă cu buline", comanda: "insertUnorderedList", icoana: List },
  { id: "ol", eticheta: "Listă numerotată", comanda: "insertOrderedList", icoana: ListOrdered },
];

const BLOCURI = [
  { eticheta: "Titlu", valoare: "h2" },
  { eticheta: "Subtitlu", valoare: "h3" },
  { eticheta: "Paragraf", valoare: "p" },
];

export function EditorContract({
  idCerere,
  contract,
}: {
  idCerere: string;
  contract: ContractCerere;
}) {
  const zona = useRef<HTMLDivElement>(null);
  const [html, setHtml] = useState(contract.html);
  const [salvat, setSalvat] = useState(true);
  const [eroare, setEroare] = useState<string | null>(null);
  const [confirmaRefacerea, setConfirmaRefacerea] = useState(false);
  const [seSalveaza, startSalvare] = useTransition();
  const [seReface, startRefacere] = useTransition();

  const trimis = contract.trimis_la !== null;

  // Continutul se pune o singura data, la montare. React nu are voie sa
  // rescrie nodul in timp ce se scrie in el: ar muta cursorul la inceput la
  // fiecare tasta.
  useEffect(() => {
    if (zona.current && zona.current.innerHTML !== contract.html) {
      zona.current.innerHTML = contract.html;
    }
    // Doar la schimbarea contractului venit de la server (salvare, regenerare).
  }, [contract.html]);

  function comanda(cmd: string, valoare?: string) {
    zona.current?.focus();
    document.execCommand(cmd, false, valoare);
    citeste();
  }

  function citeste() {
    const continut = zona.current?.innerHTML ?? "";
    setHtml(continut);
    setSalvat(continut === contract.html);
  }

  function salveaza() {
    setEroare(null);
    startSalvare(async () => {
      const rezultat = await salveazaContract(idCerere, html);
      if (rezultat.eroare) {
        setEroare(rezultat.eroare);
        return;
      }
      setSalvat(true);
    });
  }

  function reface() {
    setEroare(null);
    startRefacere(async () => {
      const rezultat = await regenereazaContract(idCerere);
      setConfirmaRefacerea(false);
      if (rezultat.eroare) {
        setEroare(rezultat.eroare);
        return;
      }
      if (rezultat.contract && zona.current) {
        zona.current.innerHTML = rezultat.contract.html;
        setHtml(rezultat.contract.html);
        setSalvat(true);
      }
    });
  }

  return (
    <section className="rounded-card border border-line bg-surface p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-[15px] font-semibold text-ink">Contractul de credit</h2>
          <p className="mt-1 text-[13px] leading-[19px] text-ink-soft">
            {trimis
              ? "Trimis clientului. Textul nu se mai poate schimba — el semnează exact ce citește aici."
              : "Completat automat din datele dosarului. Ajustează-l, apoi apasă „Aprobă” ca să plece la client."}
          </p>
        </div>

        {trimis ? (
          <span className="inline-flex shrink-0 items-center gap-1.5 rounded-full bg-success/10 px-3 py-1.5 text-[12.5px] font-medium text-success">
            <Check size={16} strokeWidth={1.75} aria-hidden />
            Trimis clientului
          </span>
        ) : null}
      </div>

      {eroare ? (
        <div className="mt-4">
          <Banda ton="eroare">{eroare}</Banda>
        </div>
      ) : null}

      {!trimis ? (
        <div className="mt-4 flex flex-wrap items-center gap-1 rounded-field border border-line bg-muted p-1.5">
          <select
            aria-label="Stilul paragrafului"
            defaultValue=""
            onChange={(eveniment) => {
              if (eveniment.target.value) comanda("formatBlock", eveniment.target.value);
              eveniment.target.value = "";
            }}
            className="h-9 rounded-[10px] border border-line bg-surface px-2 text-[13px] text-ink-soft focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
          >
            <option value="" disabled>
              Stil
            </option>
            {BLOCURI.map((bloc) => (
              <option key={bloc.valoare} value={bloc.valoare}>
                {bloc.eticheta}
              </option>
            ))}
          </select>

          {COMENZI.map(({ id, eticheta, comanda: cmd, icoana: Icoana }) => (
            <button
              key={id}
              type="button"
              // `onMouseDown` cu preventDefault, nu `onClick`: un click pe buton
              // ar lua focusul din zona editabila si ar pierde selectia, deci
              // comanda nu ar mai avea peste ce sa se aplice.
              onMouseDown={(eveniment) => {
                eveniment.preventDefault();
                comanda(cmd);
              }}
              aria-label={eticheta}
              title={eticheta}
              className="flex h-9 w-9 items-center justify-center rounded-[10px] text-ink-soft transition-colors hover:bg-primary-50 hover:text-primary-700 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
            >
              <Icoana size={16} strokeWidth={1.75} aria-hidden />
            </button>
          ))}

          <button
            type="button"
            onClick={() => setConfirmaRefacerea(true)}
            className="ml-auto flex h-9 items-center gap-1.5 rounded-[10px] px-2.5 text-[13px] text-ink-soft transition-colors hover:bg-primary-50 hover:text-primary-700 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
          >
            <RotateCcw size={16} strokeWidth={1.75} aria-hidden />
            Refă din șablon
          </button>
        </div>
      ) : null}

      <div
        ref={zona}
        contentEditable={!trimis}
        suppressContentEditableWarning
        onInput={citeste}
        onBlur={citeste}
        role="textbox"
        aria-multiline="true"
        aria-label="Textul contractului"
        className={cn(
          "contract-text mt-3 max-h-[520px] min-h-[260px] overflow-y-auto rounded-field border border-line p-5 text-[13.5px] leading-[21px] text-ink-soft",
          trimis
            ? "bg-muted"
            : "bg-surface focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25",
        )}
      />

      {!trimis ? (
        <div className="mt-4 flex items-center justify-between gap-3">
          <p className="text-[12.5px] text-ink-faint">
            {salvat ? "Toate modificările sunt salvate." : "Ai modificări nesalvate."}
          </p>
          <Button
            onClick={salveaza}
            loading={seSalveaza}
            disabled={salvat}
            iconaStanga={<Check size={18} strokeWidth={1.75} aria-hidden />}
          >
            Salvează contractul
          </Button>
        </div>
      ) : null}

      <Drawer open={confirmaRefacerea} onOpenChange={setConfirmaRefacerea}>
        <DrawerContent
          title="Refaci contractul din șablon?"
          description="Textul scris până acum se pierde și se generează unul nou din datele dosarului."
          footer={
            <Button onClick={reface} loading={seReface} className="w-full">
              Da, refă contractul
            </Button>
          }
        >
          <p className="text-[15px] leading-[22px] text-ink-soft">
            Util după ce cererea primește rata și DAE: șablonul generat la depunere avea liniuțe
            în locul lor. Modificările tale nu se pot recupera.
          </p>
          {seReface ? (
            <p className="mt-3 flex items-center gap-2 text-[13px] text-ink-faint">
              <Loader2 size={16} strokeWidth={1.75} aria-hidden className="animate-spin" />
              Se generează…
            </p>
          ) : null}
        </DrawerContent>
      </Drawer>
    </section>
  );
}
