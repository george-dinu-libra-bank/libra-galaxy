"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { Plus, Send, Sparkles, X } from "lucide-react";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { pregatesteMesaj, trimiteMesaj } from "@/lib/actions/investigatii";

/**
 * Compune mesajul către client: întrebările, propunerea agentului, trimiterea.
 *
 * Pasul din mijloc e rostul întregii componente. Agentul scrie, administratorul
 * citește, și abia apoi apasă trimite. Nu există niciun drum prin care textul
 * să ajungă la client fără să treacă prin ochii lui — de aceea „Propune textul"
 * și „Trimite clientului" sunt două butoane separate, nu unul.
 */

const INTREBARI_SUGERATE = [
  "Ai făcut tu aceste plăți?",
  "Ai pierdut cardul sau l-a folosit altcineva?",
  "Ai fost în străinătate în perioada respectivă?",
  "Ai primit vreun mesaj sau apel prin care ți s-au cerut datele cardului?",
];

export function CompuneMesajInvestigatie({
  idCaz,
  faraRaspuns = [],
}: {
  idCaz: string;
  /** Intrebarile la care raspunsul clientului nu a spus nimic. */
  faraRaspuns?: string[];
}) {
  const router = useRouter();
  // Cand clientul a raspuns pe langa subiect, caseta porneste cu exact
  // intrebarile ramase deschise — administratorul nu le cauta prin fir.
  const [intrebari, setIntrebari] = useState<string[]>(
    faraRaspuns.length > 0 ? faraRaspuns.slice(0, 8) : [INTREBARI_SUGERATE[0]],
  );
  const [intrebareNoua, setIntrebareNoua] = useState("");
  const [nota, setNota] = useState("");

  const [text, setText] = useState("");
  // Se ține minte ce a scris agentul, ca să știm dacă administratorul a atins
  // textul. Cele două steaguri ajung în `caz_mesaj` și rămân acolo: peste șase
  // luni, la o contestație, întrebarea „cine a scris asta" are răspuns în date.
  const [textAgent, setTextAgent] = useState<string | null>(null);

  const [sePregateste, pornestePregatirea] = useTransition();
  const [seTrimite, pornesteTrimiterea] = useTransition();
  const [eroare, setEroare] = useState<string | null>(null);
  const [nota_agent, setNotaAgent] = useState<string | null>(null);

  function adauga(intrebare: string) {
    const curata = intrebare.trim();
    if (!curata || intrebari.includes(curata) || intrebari.length >= 8) return;
    setIntrebari([...intrebari, curata]);
    setIntrebareNoua("");
  }

  function pregateste() {
    setEroare(null);
    setNotaAgent(null);
    pornestePregatirea(async () => {
      const { date, eroare: err } = await pregatesteMesaj(idCaz, intrebari, nota);
      if (err) {
        setEroare(err);
        return;
      }
      if (!date?.text) {
        setNotaAgent(
          "Agentul nu a putut propune un text acum. Scrie tu mesajul în caseta de mai jos.",
        );
        return;
      }
      setText(date.text);
      setTextAgent(date.text);
    });
  }

  function trimite() {
    setEroare(null);
    pornesteTrimiterea(async () => {
      const { eroare: err } = await trimiteMesaj(
        idCaz,
        text,
        intrebari,
        textAgent !== null,
        textAgent !== null && text.trim() !== textAgent.trim(),
      );
      if (err) {
        setEroare(err);
        return;
      }
      router.refresh();
    });
  }

  const nesugerate = INTREBARI_SUGERATE.filter((i) => !intrebari.includes(i));

  return (
    <section className="flex flex-col gap-5 rounded-card border border-line bg-surface p-5">
      <div>
        <h2 className="text-[15px] font-semibold text-ink">Întreabă clientul</h2>
        <p className="mt-1 text-[13px] leading-[19px] text-ink-soft">
          {faraRaspuns.length > 0
            ? "Răspunsul clientului a lăsat întrebările de mai jos deschise. Cere agentului o reluare, citește-o și trimite-o."
            : "Alege întrebările, cere agentului o propunere, apoi citește-o și trimite-o."}
        </p>
      </div>

      {/* 1. Întrebările */}
      <div className="flex flex-col gap-2.5">
        <p className="text-[13px] font-medium text-ink-soft">Întrebări ({intrebari.length}/8)</p>

        <ul className="flex flex-col gap-1.5">
          {intrebari.map((intrebare) => (
            <li
              key={intrebare}
              className="flex items-start gap-2 rounded-field bg-primary-50 px-3 py-2 text-[13px] leading-[19px] text-primary-700"
            >
              <span className="flex-1">{intrebare}</span>
              <button
                type="button"
                onClick={() => setIntrebari(intrebari.filter((i) => i !== intrebare))}
                aria-label={`Scoate întrebarea „${intrebare}"`}
                className="mt-px shrink-0 text-primary-700/60 transition-colors hover:text-danger"
              >
                <X size={15} strokeWidth={2} aria-hidden />
              </button>
            </li>
          ))}
        </ul>

        {nesugerate.length > 0 ? (
          <div className="flex flex-wrap gap-1.5">
            {nesugerate.map((intrebare) => (
              <button
                key={intrebare}
                type="button"
                onClick={() => adauga(intrebare)}
                className="rounded-full border border-line px-3 py-1.5 text-left text-[12px] leading-[16px] text-ink-soft transition-colors hover:border-primary-300 hover:text-primary-700"
              >
                + {intrebare}
              </button>
            ))}
          </div>
        ) : null}

        <div className="flex gap-2">
          <input
            value={intrebareNoua}
            onChange={(e) => setIntrebareNoua(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                adauga(intrebareNoua);
              }
            }}
            placeholder="Scrie o altă întrebare"
            maxLength={300}
            className="h-11 flex-1 rounded-field border border-line bg-surface px-3 text-[14px] text-ink outline-none transition-colors focus:border-primary-500"
          />
          <Button
            varianta="ghost"
            marime="sm"
            onClick={() => adauga(intrebareNoua)}
            disabled={!intrebareNoua.trim() || intrebari.length >= 8}
            iconaStanga={<Plus size={16} strokeWidth={2} aria-hidden />}
          >
            Adaugă
          </Button>
        </div>
      </div>

      {/* 2. Propunerea agentului */}
      <div className="flex flex-col gap-2.5 border-t border-line pt-5">
        <label htmlFor="nota-agent" className="text-[13px] font-medium text-ink-soft">
          Observație pentru agent (opțional)
        </label>
        <input
          id="nota-agent"
          value={nota}
          onChange={(e) => setNota(e.target.value)}
          placeholder="Ex.: clientul e în vârstă, scrie cât mai simplu"
          maxLength={2000}
          className="h-11 rounded-field border border-line bg-surface px-3 text-[14px] text-ink outline-none transition-colors focus:border-primary-500"
        />

        <Button
          varianta="secondary"
          marime="sm"
          className="w-fit"
          loading={sePregateste}
          disabled={intrebari.length === 0}
          onClick={pregateste}
          iconaStanga={<Sparkles size={16} strokeWidth={1.75} aria-hidden />}
        >
          Propune textul
        </Button>

        {nota_agent ? <Banda ton="info">{nota_agent}</Banda> : null}
      </div>

      {/* 3. Textul, editabil, apoi trimiterea */}
      <div className="flex flex-col gap-2.5 border-t border-line pt-5">
        <label htmlFor="text-mesaj" className="text-[13px] font-medium text-ink-soft">
          Mesajul care ajunge la client
        </label>
        <textarea
          id="text-mesaj"
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={9}
          maxLength={4000}
          placeholder="Scrie mesajul, sau cere-i agentului o propunere mai sus."
          className="rounded-field border border-line bg-surface p-3 text-[14px] leading-[21px] text-ink outline-none transition-colors focus:border-primary-500"
        />

        {textAgent !== null ? (
          <p className="text-[12px] leading-[17px] text-ink-faint">
            {text.trim() === textAgent.trim()
              ? "Textul e cel propus de agent, neschimbat. Citește-l înainte să-l trimiți."
              : "Ai modificat textul propus de agent. Se consemnează ca atare."}
          </p>
        ) : null}

        {eroare ? <Banda ton="eroare">{eroare}</Banda> : null}

        <Button
          marime="sm"
          className="w-fit"
          loading={seTrimite}
          disabled={!text.trim() || intrebari.length === 0}
          onClick={trimite}
          iconaStanga={<Send size={16} strokeWidth={1.75} aria-hidden />}
        >
          Trimite clientului
        </Button>
      </div>
    </section>
  );
}
