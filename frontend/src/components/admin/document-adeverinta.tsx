"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { Check, FileText, ScanLine, TriangleAlert } from "lucide-react";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { Camp } from "@/components/ui/camp";
import { confirmaVenitDinAdeverinta } from "@/lib/actions/admin-credite";
import { lei, type DocumentCerere } from "@/lib/tipuri-admin";

/**
 * Adeverinta, langa cifra citita din ea.
 *
 * Cele doua stau impreuna dinadins: analistul trebuie sa poata compara ce spune
 * documentul cu ce a inteles masina, fara sa deschida alt ecran. Campul e
 * editabil de la bun inceput, nu blocat cu un buton „corecteaza" — corectia nu
 * e o exceptie, e felul normal de a lucra cu un OCR.
 *
 * Ce se trimite mai departe e mereu ce scrie in camp, nu ce a citit masina.
 */
export function DocumentAdeverinta({
  document,
  idCerere,
}: {
  document: DocumentCerere;
  idCerere: string;
}) {
  const router = useRouter();
  const [seTrimite, startTransition] = useTransition();
  const [eroare, setEroare] = useState<string | null>(null);

  const citit = document.extras.venit_net ?? null;
  const [venit, setVenit] = useState(document.venit_confirmat ?? citit ?? "");

  const confirmat = document.status === "confirmat";
  const stersDinStorage = document.sters_la !== null;

  function confirma() {
    const curatat = venit.trim().replace(",", ".");
    if (!curatat || Number.isNaN(Number(curatat)) || Number(curatat) <= 0) {
      setEroare("Scrie venitul net lunar, în lei.");
      return;
    }

    setEroare(null);
    startTransition(async () => {
      const rezultat = await confirmaVenitDinAdeverinta(document.id, idCerere, curatat);
      if (rezultat.eroare) {
        setEroare(rezultat.eroare);
        return;
      }
      router.refresh();
    });
  }

  return (
    <section className="rounded-card border border-line bg-surface p-5">
      <div className="flex items-start gap-3">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary-50">
          <FileText size={19} strokeWidth={1.75} aria-hidden className="text-primary-600" />
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="text-[15px] font-semibold text-ink">Adeverință de venit</h2>
          <p className="mt-1 text-[13px] leading-[19px] text-ink-faint">
            Încărcată{" "}
            {new Date(document.creat_la).toLocaleDateString("ro-RO", {
              day: "numeric",
              month: "long",
              year: "numeric",
            })}
          </p>
        </div>
        {confirmat ? (
          <span className="inline-flex shrink-0 items-center gap-1.5 rounded-full bg-success/10 px-2.5 py-1 text-[11.5px] font-medium text-success">
            <Check size={12} strokeWidth={2.25} aria-hidden />
            Confirmată
          </span>
        ) : null}
      </div>

      <Previzualizare document={document} />

      <div className="mt-5 rounded-field border border-line bg-muted p-4">
        <p className="flex items-center gap-2 text-[13px] font-semibold text-ink">
          <ScanLine size={15} strokeWidth={1.75} aria-hidden className="text-ink-faint" />
          Ce a citit sistemul
        </p>

        {citit ? (
          <dl className="mt-3 grid grid-cols-1 gap-2 text-[13px] sm:grid-cols-3">
            <Pereche eticheta="Venit net" valoare={`${lei(citit)} RON`} />
            <Pereche eticheta="Angajator" valoare={document.extras.angajator ?? "—"} />
            <Pereche
              eticheta="Vechime"
              valoare={
                document.extras.vechime_luni ? `${document.extras.vechime_luni} luni` : "—"
              }
            />
          </dl>
        ) : (
          <p className="mt-2 text-[13px] leading-[19px] text-ink-soft">
            Nu s-a putut citi nicio sumă din document — fie e prea neclar, fie nu are
            eticheta „net” lângă cifră. Uită-te la document și scrie tu venitul.
          </p>
        )}
      </div>

      {confirmat && citit && document.venit_confirmat !== citit ? (
        <p className="mt-3 flex items-start gap-2 text-[12.5px] leading-[18px] text-warning">
          <TriangleAlert size={14} strokeWidth={2} aria-hidden className="mt-0.5 shrink-0" />
          Sistemul citise {lei(citit)} RON. Valoarea folosită este cea corectată de tine,{" "}
          {lei(document.venit_confirmat)} RON.
        </p>
      ) : null}

      {eroare ? (
        <div className="mt-4">
          <Banda ton="eroare">{eroare}</Banda>
        </div>
      ) : null}

      <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-end">
        <div className="flex-1">
          <Camp
            eticheta="Venit net lunar (RON)"
            value={venit}
            onChange={(eveniment) => setVenit(eveniment.target.value)}
            inputMode="decimal"
            autoComplete="off"
            ajutor={
              confirmat
                ? "Poți reveni oricând; ultima confirmare e cea care contează."
                : "Verifică cifra pe document înainte să confirmi. Ea intră în calculul scorului."
            }
          />
        </div>
        <Button
          className="sm:w-auto"
          loading={seTrimite}
          onClick={confirma}
          iconaStanga={<Check size={18} strokeWidth={1.75} aria-hidden />}
        >
          {confirmat ? "Actualizează" : "Confirmă venitul"}
        </Button>
      </div>

      {stersDinStorage ? (
        <p className="mt-3 text-[12.5px] leading-[18px] text-ink-faint">
          Fișierul a fost șters după perioada de păstrare. Ce s-a citit din el rămâne
          înregistrat mai sus.
        </p>
      ) : null}
    </section>
  );
}

function Pereche({ eticheta, valoare }: { eticheta: string; valoare: string }) {
  return (
    <div>
      <dt className="text-[12px] text-ink-faint">{eticheta}</dt>
      <dd className="mt-0.5 truncate font-semibold text-ink">{valoare}</dd>
    </div>
  );
}

/**
 * Documentul propriu-zis, din URL semnat cu durata scurta.
 *
 * PDF-ul intra in `<iframe>`, poza in `<img>` — nu exista un element care sa le
 * afiseze pe amandoua. Cand fisierul a fost sters dupa retentie, nu se arata un
 * chenar gol, ci se spune de ce lipseste.
 */
function Previzualizare({ document }: { document: DocumentCerere }) {
  if (!document.url) {
    return (
      <div className="mt-4 flex flex-col items-center gap-2 rounded-field border border-dashed border-line p-8 text-center">
        <FileText size={22} strokeWidth={1.75} aria-hidden className="text-ink-faint" />
        <p className="text-[13px] text-ink-soft">Documentul nu mai este disponibil.</p>
      </div>
    );
  }

  const estePdf = (document.content_type ?? "").includes("pdf");

  return (
    <div className="mt-4 overflow-hidden rounded-field border border-line bg-muted">
      {estePdf ? (
        <iframe
          src={document.url}
          title="Adeverință de venit"
          className="h-[420px] w-full border-0 bg-white"
        />
      ) : (
        // eslint-disable-next-line @next/next/no-img-element -- URL semnat, temporar
        <img
          src={document.url}
          alt="Adeverință de venit"
          className="max-h-[420px] w-full object-contain"
        />
      )}
    </div>
  );
}
