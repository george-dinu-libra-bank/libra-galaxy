"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import {
  Briefcase,
  CheckCircle2,
  FileSearch,
  Landmark,
  Loader2,
  Receipt,
  Wallet,
  XCircle,
} from "lucide-react";
import { Banda } from "@/components/ui/banda";
import { IncarcaAdeverinta } from "@/components/credite/incarca-adeverinta";
import { Button } from "@/components/ui/button";
import { Camp } from "@/components/ui/camp";
import { Checkbox } from "@/components/ui/checkbox";
import {
  acceptaOferta,
  depuneCerere,
  evalueazaCerere,
  type Decizie,
} from "@/lib/actions/credite";
import type { ContBancar } from "@/lib/data/conturi";
import {
  sumaDinText,
  validAngajator,
  validObligatii,
  validVechime,
  validVenit,
} from "@/lib/validare";
import { formateazaSuma } from "@/lib/utils";

/**
 * Cererea de credit, în patru pași.
 *
 * Mașină de stări cu string union și early return, ca în `register-form.tsx` —
 * proiectul nu are componentă de stepper și nu are nevoie de una.
 *
 * Pasul „verificare" nu e decor: în spatele lui rulează patru surse de venit
 * care se coroborează (tranzacții, adeverință, declarație, registru de expuneri).
 * Le arătăm bifându-se pe rând pentru că e singurul moment în care clientul
 * vede că banca chiar verifică, nu doar acceptă ce a scris el.
 */

type Pas = "date" | "verificare" | "decizie" | "succes";

type Campuri = {
  venit: string;
  angajator: string;
  vechime: string;
  obligatii: string;
};

const VALIDATORI: Record<keyof Campuri, (valoare: string) => string | null> = {
  venit: validVenit,
  angajator: validAngajator,
  vechime: validVechime,
  obligatii: validObligatii,
};

const VERIFICARI = [
  { cod: "tranzactii", eticheta: "Încasările recurente din cont", icoana: Wallet },
  { cod: "declarat", eticheta: "Datele declarate", icoana: FileSearch },
  { cod: "birou_credit", eticheta: "Obligațiile existente", icoana: Receipt },
  { cod: "decizie", eticheta: "Analiza de risc", icoana: Landmark },
];

export function CerereWizard({
  suma,
  luni,
  conturi,
}: {
  suma: number;
  luni: number;
  conturi: ContBancar[];
}) {
  const router = useRouter();
  const [pas, setPas] = useState<Pas>("date");

  const [valori, setValori] = useState<Campuri>({
    venit: "",
    angajator: "",
    vechime: "",
    obligatii: "",
  });
  const [erori, setErori] = useState<Partial<Record<keyof Campuri, string | null>>>({});
  const [atinse, setAtinse] = useState<Partial<Record<keyof Campuri, boolean>>>({});
  const [acord, setAcord] = useState(false);
  const [acordAtins, setAcordAtins] = useState(false);

  const [decizie, setDecizie] = useState<Decizie | null>(null);
  const [idCerere, setIdCerere] = useState<string | null>(null);
  const [idCont, setIdCont] = useState(conturi[0]?.id ?? "");
  const [eroare, setEroare] = useState<string | null>(null);
  const [seTrimite, startTransition] = useTransition();

  function seteaza(camp: keyof Campuri, valoare: string) {
    setValori((precedente) => ({ ...precedente, [camp]: valoare }));
    // După prima eroare, câmpul se revalidează la fiecare tastă (DESIGN.md 9).
    if (erori[camp]) setErori((precedente) => ({ ...precedente, [camp]: VALIDATORI[camp](valoare) }));
  }

  function laBlur(camp: keyof Campuri) {
    setAtinse((precedente) => ({ ...precedente, [camp]: true }));
    setErori((precedente) => ({ ...precedente, [camp]: VALIDATORI[camp](valori[camp]) }));
  }

  function trimite() {
    const noiErori = Object.fromEntries(
      (Object.keys(VALIDATORI) as (keyof Campuri)[]).map((camp) => [
        camp,
        VALIDATORI[camp](valori[camp]),
      ]),
    ) as Record<keyof Campuri, string | null>;

    setErori(noiErori);
    setAtinse({ venit: true, angajator: true, vechime: true, obligatii: true });
    setAcordAtins(true);

    if (Object.values(noiErori).some(Boolean) || !acord) return;

    setEroare(null);
    setPas("verificare");

    startTransition(async () => {
      const creata = await depuneCerere({
        suma,
        luni,
        venitDeclarat: sumaDinText(valori.venit),
        angajator: valori.angajator.trim(),
        vechimeAngajatorLuni: Number(valori.vechime),
        obligatiiDeclarate: sumaDinText(valori.obligatii),
      });

      if (creata.eroare || !creata.id) {
        setEroare(creata.eroare ?? "Nu am putut depune cererea.");
        setPas("date");
        return;
      }

      const evaluata = await evalueazaCerere(creata.id);
      if (evaluata.eroare || !evaluata.decizie) {
        setEroare(evaluata.eroare ?? "Nu am putut evalua cererea.");
        setPas("date");
        return;
      }

      setIdCerere(creata.id);
      setDecizie(evaluata.decizie);
      setPas("decizie");
    });
  }

  function semneaza() {
    if (!idCerere || !idCont) return;
    setEroare(null);

    startTransition(async () => {
      const rezultat = await acceptaOferta(idCerere, idCont);
      if (rezultat.eroare) {
        setEroare(rezultat.eroare);
        return;
      }
      setPas("succes");
    });
  }

  // -- pasul 1: datele declarate --------------------------------------------

  if (pas === "date") {
    return (
      <div className="mt-6 space-y-5">
        <section className="rounded-card bg-surface p-5 shadow-sm">
          <p className="text-[13px] text-ink-faint">Ai cerut</p>
          <p className="tabular mt-1 text-[22px] font-bold text-ink">
            {formateazaSuma(suma)} <span className="text-[15px] font-medium text-ink-soft">pe {luni} luni</span>
          </p>
        </section>

        {eroare ? <Banda ton="eroare">{eroare}</Banda> : null}

        <div className="space-y-4">
          <Camp
            eticheta="Venit net lunar"
            icoana={Wallet}
            inputMode="decimal"
            placeholder="6200"
            value={valori.venit}
            onChange={(eveniment) => seteaza("venit", eveniment.target.value)}
            onBlur={() => laBlur("venit")}
            eroare={atinse.venit ? erori.venit : null}
            validat={Boolean(atinse.venit && !erori.venit && valori.venit)}
            ajutor="Îl verificăm în încasările din cont — scrie suma reală."
          />

          <Camp
            eticheta="Angajator"
            icoana={Briefcase}
            placeholder="ACME Software SRL"
            value={valori.angajator}
            onChange={(eveniment) => seteaza("angajator", eveniment.target.value)}
            onBlur={() => laBlur("angajator")}
            eroare={atinse.angajator ? erori.angajator : null}
            validat={Boolean(atinse.angajator && !erori.angajator && valori.angajator)}
          />

          <Camp
            eticheta="Vechime la angajatorul actual (luni)"
            inputMode="numeric"
            placeholder="18"
            value={valori.vechime}
            onChange={(eveniment) => seteaza("vechime", eveniment.target.value)}
            onBlur={() => laBlur("vechime")}
            eroare={atinse.vechime ? erori.vechime : null}
            validat={Boolean(atinse.vechime && !erori.vechime && valori.vechime)}
          />

          <Camp
            eticheta="Rate lunare la alte bănci"
            icoana={Receipt}
            inputMode="decimal"
            placeholder="0"
            value={valori.obligatii}
            onChange={(eveniment) => seteaza("obligatii", eveniment.target.value)}
            onBlur={() => laBlur("obligatii")}
            eroare={atinse.obligatii ? erori.obligatii : null}
            ajutor="Lasă gol dacă nu ai alte credite."
          />
        </div>

        <Checkbox
          checked={acord}
          onCheckedChange={(valoare) => {
            setAcord(valoare);
            setAcordAtins(true);
          }}
          eroare={acordAtins && !acord ? "Fără acordul tău nu putem face verificările." : null}
        >
          Declar pe proprie răspundere că datele sunt corecte și sunt de acord ca
          Galaxy Bank să verifice veniturile și obligațiile mele.
        </Checkbox>

        <Button className="w-full" loading={seTrimite} onClick={trimite}>
          Trimite cererea
        </Button>
      </div>
    );
  }

  // -- pasul 2: verificarile ------------------------------------------------

  if (pas === "verificare") {
    return (
      <div className="mt-10 space-y-6" role="status" aria-live="polite">
        <div className="flex flex-col items-center gap-3 text-center">
          <Loader2 size={32} strokeWidth={1.75} className="animate-spin text-primary-600" aria-hidden />
          <p className="text-[15px] font-medium text-ink">Verificăm cererea</p>
          <p className="text-[13px] text-ink-faint">Durează câteva secunde.</p>
        </div>

        <ul className="space-y-3 rounded-card bg-surface p-5 shadow-sm">
          {VERIFICARI.map(({ cod, eticheta, icoana: Icoana }, indice) => (
            <li
              key={cod}
              className="flex animate-fade-up items-center gap-3 text-[15px] text-ink-soft"
              style={{ "--i": indice } as React.CSSProperties}
            >
              <Icoana size={18} strokeWidth={1.75} aria-hidden className="shrink-0 text-primary-600" />
              {eticheta}
            </li>
          ))}
        </ul>
      </div>
    );
  }

  // -- pasul 3: decizia -----------------------------------------------------

  if (pas === "decizie" && decizie) {
    const aprobat = decizie.decizie === "aprobat";
    const manual = decizie.decizie === "analiza_manuala";

    return (
      <div className="mt-6 space-y-5">
        <section className="rounded-card bg-surface p-5 text-center shadow-sm">
          {aprobat ? (
            <CheckCircle2 size={40} strokeWidth={1.5} className="mx-auto animate-pop text-success" aria-hidden />
          ) : manual ? (
            <FileSearch size={40} strokeWidth={1.5} className="mx-auto text-warning" aria-hidden />
          ) : (
            <XCircle size={40} strokeWidth={1.5} className="mx-auto text-danger" aria-hidden />
          )}

          <p className="mt-4 whitespace-pre-line text-[15px] leading-[22px] text-ink-soft">
            {decizie.explicatie}
          </p>
        </section>

        {aprobat && decizie.rataLunara ? (
          <section className="rounded-card bg-surface p-5 shadow-sm">
            <h2 className="text-[15px] font-semibold text-ink">Oferta ta</h2>
            <dl className="mt-4 space-y-2">
              <Rand eticheta="Sumă" valoare={formateazaSuma(suma)} />
              <Rand eticheta="Perioadă" valoare={`${luni} luni`} />
              <Rand eticheta="Rată lunară" valoare={formateazaSuma(decizie.rataLunara)} />
              {decizie.dae ? (
                <Rand eticheta="DAE" valoare={`${(decizie.dae * 100).toFixed(2).replace(".", ",")}%`} />
              ) : null}
            </dl>

            <label className="mt-5 block text-[13px] text-ink-faint" htmlFor="cont-creditare">
              Banii intră în
            </label>
            <select
              id="cont-creditare"
              value={idCont}
              onChange={(eveniment) => setIdCont(eveniment.target.value)}
              className="mt-1.5 h-12 w-full rounded-field border border-line bg-bg px-3 text-[15px] text-ink focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
            >
              {conturi.map((cont) => (
                <option key={cont.id} value={cont.id}>
                  {cont.nume} · {cont.ibanMascat}
                </option>
              ))}
            </select>
          </section>
        ) : null}

        {decizie.factori.length > 0 ? (
          <details className="rounded-card bg-surface p-5 shadow-sm">
            <summary className="cursor-pointer text-[15px] font-medium text-ink">
              Cum am calculat {decizie.scor !== null ? `punctajul de ${decizie.scor}/100` : "decizia"}
            </summary>
            <ul className="mt-4 space-y-2.5">
              {decizie.factori.map((factor) => (
                <li key={factor.cod} className="text-[13px] leading-[19px]">
                  <div className="flex items-baseline justify-between gap-3">
                    <span className="text-ink-soft">{factor.explicatie}</span>
                    <span className="tabular shrink-0 font-medium text-ink">
                      {factor.puncte}/{factor.maxim}
                    </span>
                  </div>
                  <div className="mt-1 h-1 w-full rounded-full bg-muted">
                    <div
                      className="h-1 rounded-full bg-primary-600"
                      style={{ width: `${(factor.puncte / factor.maxim) * 100}%` }}
                    />
                  </div>
                </li>
              ))}
            </ul>
          </details>
        ) : null}

        {decizie.cereDocument && idCerere ? (
          <IncarcaAdeverinta idCerere={idCerere} />
        ) : null}

        {eroare ? <Banda ton="eroare">{eroare}</Banda> : null}

        {aprobat ? (
          <Button className="w-full" loading={seTrimite} onClick={semneaza}>
            Semnează și primește {formateazaSuma(suma)}
          </Button>
        ) : (
          <Button className="w-full" varianta="secondary" onClick={() => router.push("/credite")}>
            Înapoi la credite
          </Button>
        )}
      </div>
    );
  }

  // -- pasul 4: gata --------------------------------------------------------

  return (
    <div className="mt-16 flex flex-col items-center gap-4 text-center">
      <CheckCircle2 size={56} strokeWidth={1.5} className="animate-pop text-success" aria-hidden />
      <h2 className="text-xl font-bold text-ink">Banii sunt în cont</h2>
      <p className="max-w-[300px] text-[15px] leading-[22px] text-ink-soft">
        {formateazaSuma(suma)} au fost virați. Graficul de rambursare e gata, iar
        prima rată se încasează automat la scadență.
      </p>
      <Button className="mt-2 w-full" onClick={() => router.push("/credite")}>
        Vezi creditul
      </Button>
    </div>
  );
}

function Rand({ eticheta, valoare }: { eticheta: string; valoare: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4">
      <dt className="text-[13px] text-ink-soft">{eticheta}</dt>
      <dd className="tabular text-[15px] font-medium text-ink">{valoare}</dd>
    </div>
  );
}
