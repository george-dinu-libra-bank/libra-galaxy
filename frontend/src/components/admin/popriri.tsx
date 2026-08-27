"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { Scale, Undo2 } from "lucide-react";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { Camp } from "@/components/ui/camp";
import {
  incaseazaPoprirea,
  ridicaPoprirea,
  storneazaIncasarea,
} from "@/lib/actions/admin-popriri";
import {
  restDePlata,
  sePoateIncasaAcum,
  sePoateStorna,
  type Poprire,
} from "@/lib/tipuri-admin";
import { formateazaSuma } from "@/lib/utils";

/**
 * Popririle instituite, cu ce se poate face cu ele.
 *
 * Doua operatiuni, si diferenta dintre ele conteaza:
 *
 *   STORNEAZA — reverse: banii virati se intorc in contul clientului. Merge si
 *               pe o poprire stinsa sau ridicata — acolo e chiar cazul obisnuit,
 *               contestatia admisa DUPA ce banca virase. Nu ridica poprirea: daca
 *               ea ramane activa, banii intorsi redevin indisponibili pe loc,
 *               fiindca datoria a redevenit neplatita.
 *   INCASEAZA — vireaza banii catre creditor. Ii ia din conturi in ordinea
 *               vechimii si scrie in istoric, ca orice plata. Fara suma, ia cat
 *               se poate acum: banii pica in transe, si asta e forma folosita.
 *   RIDICA    — anuleaza poprirea. Banii DEJA virati nu se intorc — au plecat la
 *               creditor si nu mai sunt ai bancii. Scrie asta si in notificare.
 *
 * Cifra „se poate încasa acum" e calculata in interfata doar ca sa nu ofere un
 * buton respins oricum; decizia ramane a bazei, care recalculeaza cu soldul din
 * momentul apasarii, nu cu cel de la incarcarea paginii.
 */
export function Popriri({ popriri }: { popriri: Poprire[] }) {
  const active = popriri.filter((p) => p.status === "activa");
  const incheiate = popriri.filter((p) => p.status !== "activa");

  if (popriri.length === 0) return null;

  return (
    <section className="mt-10">
      <h2 className="text-lg font-semibold text-ink">Popriri</h2>
      <p className="mt-1 text-[13px] leading-[19px] text-ink-faint">
        Indisponibilizează o sumă pe toate conturile clientului, nu contul întreg. Încasările
        intră normal, iar banii peste suma poprită rămân la dispoziția lui.
      </p>

      <div className="mt-4 flex flex-col gap-3">
        {active.map((poprire) => (
          <Rand key={poprire.id} poprire={poprire} />
        ))}
        {incheiate.map((poprire) => (
          <Rand key={poprire.id} poprire={poprire} />
        ))}
      </div>
    </section>
  );
}

const ETICHETE: Record<Poprire["status"], { text: string; clasa: string }> = {
  activa: { text: "Activă", clasa: "bg-warning/10 text-warning" },
  stinsa: { text: "Stinsă", clasa: "bg-success/10 text-success" },
  ridicata: { text: "Ridicată", clasa: "bg-muted text-ink-faint" },
};

function Rand({ poprire }: { poprire: Poprire }) {
  const router = useRouter();
  const [suma, setSuma] = useState("");
  const [motiv, setMotiv] = useState("");
  const [sumaStorno, setSumaStorno] = useState("");
  const [eroare, setEroare] = useState<string | null>(null);
  const [seTrimite, startTransition] = useTransition();

  const activa = poprire.status === "activa";
  const ramas = restDePlata(poprire);
  const acum = sePoateIncasaAcum(poprire);
  const storna = sePoateStorna(poprire);
  const eticheta = ETICHETE[poprire.status];

  function incaseaza() {
    setEroare(null);
    const cerut = Number(suma.replace(",", "."));
    startTransition(async () => {
      const rezultat = await incaseazaPoprirea(
        poprire.id,
        Number.isFinite(cerut) && cerut > 0 ? cerut : undefined,
      );
      if (rezultat.eroare) {
        setEroare(rezultat.eroare);
        return;
      }
      setSuma("");
      router.refresh();
    });
  }

  function storneaza() {
    setEroare(null);
    const cerut = Number(sumaStorno.replace(",", "."));
    startTransition(async () => {
      const rezultat = await storneazaIncasarea(poprire.id, {
        suma: Number.isFinite(cerut) && cerut > 0 ? cerut : undefined,
      });
      if (rezultat.eroare) {
        setEroare(rezultat.eroare);
        return;
      }
      setSumaStorno("");
      router.refresh();
    });
  }

  function ridica() {
    setEroare(null);
    startTransition(async () => {
      const rezultat = await ridicaPoprirea(poprire.id, motiv);
      if (rezultat.eroare) {
        setEroare(rezultat.eroare);
        return;
      }
      setMotiv("");
      router.refresh();
    });
  }

  return (
    <article className="rounded-card border border-line bg-surface p-4">
      <div className="flex flex-wrap items-start gap-3">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-muted">
          <Scale size={17} strokeWidth={1.75} aria-hidden className="text-ink-faint" />
        </span>

        <div className="min-w-0 flex-1">
          <p className="truncate text-[15px] font-semibold text-ink">
            {poprire.nume ?? "Client necunoscut"}
          </p>
          <p className="mt-0.5 text-[13px] text-ink-soft">
            {poprire.creditor}
            {poprire.dosar ? ` · dosar ${poprire.dosar}` : ""}
          </p>
        </div>

        <span
          className={`shrink-0 rounded-full px-2.5 py-1 text-[12px] font-medium ${eticheta.clasa}`}
        >
          {eticheta.text}
        </span>
      </div>

      <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-[13px] sm:grid-cols-4">
        <Cifra eticheta="Suma poprită" valoare={formateazaSuma(Number(poprire.suma_totala), "RON")} />
        <Cifra eticheta="Virat deja" valoare={formateazaSuma(Number(poprire.suma_incasata), "RON")} />
        <Cifra eticheta="Rest de plată" valoare={formateazaSuma(ramas, "RON")} />
        <Cifra
          eticheta="Are în conturi"
          valoare={
            poprire.disponibil === null
              ? "—"
              : formateazaSuma(Number(poprire.disponibil), "RON")
          }
        />
      </dl>

      {eroare ? (
        <div className="mt-3">
          <Banda ton="eroare">{eroare}</Banda>
        </div>
      ) : null}

      {activa ? (
        <div className="mt-4 flex flex-col gap-3 border-t border-line pt-4">
          {acum <= 0 ? (
            <Banda ton="info">
              Clientul nu are bani în conturi. Poprirea rămâne activă și se poate încasa când
              intră bani.
            </Banda>
          ) : (
            <p className="text-[13px] text-ink-soft">
              Se pot încasa acum <strong className="font-semibold text-ink">
                {formateazaSuma(acum, "RON")}
              </strong>.
            </p>
          )}

          <div className="flex flex-wrap items-end gap-3">
            <div className="min-w-[160px] flex-1">
              <Camp
                eticheta="Sumă de virat (RON)"
                type="text"
                inputMode="decimal"
                value={suma}
                onChange={(e) => setSuma(e.target.value)}
                placeholder={acum > 0 ? `Gol = tot ce se poate (${acum.toFixed(2)})` : "—"}
                ajutor="Lasă gol ca să iei cât se poate acum."
                autoComplete="off"
              />
            </div>

            <Button
              varianta="primary"
              marime="sm"
              loading={seTrimite}
              disabled={acum <= 0}
              onClick={incaseaza}
            >
              Încasează
            </Button>
          </div>

          <div className="flex flex-wrap items-end gap-3">
            <div className="min-w-[160px] flex-1">
              <Camp
                eticheta="Motivul ridicării"
                value={motiv}
                onChange={(e) => setMotiv(e.target.value)}
                placeholder="Ex. contestație admisă, creditorul a retras cererea"
                maxLength={500}
                ajutor="Ajunge la client, în notificare."
                autoComplete="off"
              />
            </div>

            <Button varianta="secondary" marime="sm" loading={seTrimite} onClick={ridica}>
              Ridică poprirea
            </Button>
          </div>
        </div>
      ) : null}

      {storna > 0 ? (
        <div className="mt-4 flex flex-col gap-3 border-t border-line pt-4">
          <p className="text-[13px] text-ink-soft">
            Către creditor s-au virat{" "}
            <strong className="font-semibold text-ink">{formateazaSuma(storna, "RON")}</strong>.
            Storno aduce banii înapoi în contul clientului
            {activa ? ", dar poprirea rămâne în vigoare, deci suma redevine indisponibilă" : ""}.
          </p>

          <div className="flex flex-wrap items-end gap-3">
            <div className="min-w-[160px] flex-1">
              <Camp
                eticheta="Sumă de returnat (RON)"
                type="text"
                inputMode="decimal"
                value={sumaStorno}
                onChange={(e) => setSumaStorno(e.target.value)}
                placeholder={`Gol = tot (${storna.toFixed(2)})`}
                ajutor="Lasă gol ca să returnezi tot ce s-a virat."
                autoComplete="off"
              />
            </div>

            <Button
              varianta="secondary"
              marime="sm"
              loading={seTrimite}
              onClick={storneaza}
              iconaStanga={<Undo2 size={16} strokeWidth={1.75} aria-hidden />}
            >
              Stornează
            </Button>
          </div>
        </div>
      ) : null}
    </article>
  );
}

function Cifra({ eticheta, valoare }: { eticheta: string; valoare: string }) {
  return (
    <div>
      <dt className="text-[12px] text-ink-faint">{eticheta}</dt>
      <dd className="tabular mt-0.5 font-semibold text-ink">{valoare}</dd>
    </div>
  );
}
