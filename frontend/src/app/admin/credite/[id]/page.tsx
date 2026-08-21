import Link from "next/link";
import { notFound } from "next/navigation";
import { ChevronLeft } from "lucide-react";
import { Banda } from "@/components/ui/banda";
import { DeciziaCererii } from "@/components/admin/decizia-cererii";
import { DocumentAdeverinta } from "@/components/admin/document-adeverinta";
import { cereAdmin } from "@/lib/admin";
import { BackendError } from "@/lib/backend";
import { obtineDosarCredit } from "@/lib/data/admin-credite";
import {
  ETICHETE_STATUS,
  ETICHETE_SURSA,
  lei,
  tonStatus,
  type CerereCredit,
  type MotivSauFactor,
  type VerificareVenit,
} from "@/lib/tipuri-admin";
import { cn } from "@/lib/utils";

const STIL_TON = {
  bun: "bg-success/10 text-success",
  rau: "bg-danger/8 text-danger",
  atentie: "bg-warning/10 text-warning",
  neutru: "bg-muted text-ink-faint",
} as const;

export default async function DosarCreditPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const [{ id }, admin] = await Promise.all([params, cereAdmin()]);

  const dosar = await obtineDosarCredit(admin.token, id).catch((exc) => {
    if (exc instanceof BackendError && exc.status === 404) notFound();
    throw exc;
  });

  const { cerere, verificari, documente } = dosar;
  const deDecis = cerere.status === "analiza_manuala";

  return (
    <div className="flex flex-col gap-6">
      <Link
        href="/admin/credite"
        className="inline-flex w-fit items-center gap-1.5 text-[13px] font-semibold text-primary-600 hover:underline"
      >
        <ChevronLeft size={16} strokeWidth={2} aria-hidden />
        Înapoi la credite
      </Link>

      <Antet cerere={cerere} />

      <Cifre cerere={cerere} />

      {cerere.explicatie ? (
        <section className="rounded-card border border-line bg-surface p-5">
          <h2 className="text-[15px] font-semibold text-ink">Ce i s-a spus clientului</h2>
          <p className="mt-2 whitespace-pre-line text-[13px] leading-[20px] text-ink-soft">
            {cerere.explicatie}
          </p>
        </section>
      ) : null}

      <Punctaj motive={cerere.motive} scor={cerere.scor} />

      <Verificari verificari={verificari} />

      {documente.length > 0 ? (
        documente.map((document) => (
          <DocumentAdeverinta key={document.id} document={document} idCerere={cerere.id} />
        ))
      ) : (
        <section className="rounded-card border border-dashed border-line bg-surface p-5 text-center">
          <p className="text-[13px] leading-[19px] text-ink-faint">
            Clientul nu a încărcat niciun document. Aplicația i-o cere doar când banca nu-i
            vede venitul în încasări.
          </p>
        </section>
      )}

      {deDecis ? (
        <DeciziaCererii
          idCerere={cerere.id}
          nume={cerere.nume}
          suma={cerere.suma_ceruta}
          luni={cerere.luni}
        />
      ) : (
        <Banda ton="info">
          Dosarul e în starea „{ETICHETE_STATUS[cerere.status]}”. Doar cererile care așteaptă
          decizie pot fi aprobate sau respinse de aici.
        </Banda>
      )}
    </div>
  );
}

function Antet({ cerere }: { cerere: CerereCredit }) {
  const ton = tonStatus(cerere.status);

  return (
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div>
        <h1 className="text-[26px] font-bold leading-8 tracking-[-0.02em] text-ink">
          {cerere.nume}
        </h1>
        <p className="mt-1.5 text-[15px] leading-[22px] text-ink-soft">
          {lei(cerere.suma_ceruta)} RON pe {cerere.luni} luni · depusă{" "}
          {new Date(cerere.creat_la).toLocaleDateString("ro-RO", {
            day: "numeric",
            month: "long",
            year: "numeric",
          })}
        </p>
      </div>
      <span
        className={cn(
          "inline-flex items-center rounded-full px-3 py-1.5 text-[12.5px] font-medium",
          STIL_TON[ton],
        )}
      >
        {ETICHETE_STATUS[cerere.status]}
      </span>
    </div>
  );
}

function Cifre({ cerere }: { cerere: CerereCredit }) {
  const dti = cerere.dti === null ? null : Number(cerere.dti);

  return (
    <section className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <Cifra eticheta="Punctaj" valoare={cerere.scor === null ? "—" : `${cerere.scor}/100`} />
      <Cifra
        eticheta="Grad de îndatorare"
        valoare={dti === null ? "—" : `${(dti * 100).toFixed(1)}%`}
        // Plafonul BNR pentru credite de consum. Peste el nu se acorda, deci
        // apropierea de prag e informatia care conteaza, nu procentul singur.
        subtitlu={dti === null ? undefined : `plafon 40%`}
        ton={dti !== null && dti > 0.4 ? "rau" : "neutru"}
      />
      <Cifra eticheta="Venit folosit" valoare={`${lei(cerere.venit_folosit)} RON`} />
      <Cifra eticheta="Obligații" valoare={`${lei(cerere.obligatii_folosite)} RON`} />
    </section>
  );
}

function Cifra({
  eticheta,
  valoare,
  subtitlu,
  ton = "neutru",
}: {
  eticheta: string;
  valoare: string;
  subtitlu?: string;
  ton?: "neutru" | "rau";
}) {
  return (
    <div className="rounded-card border border-line bg-surface p-4">
      <p className="text-[12px] text-ink-faint">{eticheta}</p>
      <p
        className={cn(
          "mt-1 text-[18px] font-bold tabular",
          ton === "rau" ? "text-danger" : "text-ink",
        )}
      >
        {valoare}
      </p>
      {subtitlu ? <p className="text-[11.5px] text-ink-faint">{subtitlu}</p> : null}
    </div>
  );
}

/**
 * Din ce s-a compus punctajul.
 *
 * Coloana `motive` tine si factorii scorecard-ului, si motivele de respingere pe
 * criterii hard (vezi `_finalizeaza` din backend) — se disting dupa prezenta lui
 * `maxim`. Un factor fara punctajul lui e un numar pe care analistul n-are cum
 * sa il judece.
 */
function Punctaj({ motive, scor }: { motive: MotivSauFactor[]; scor: number | null }) {
  if (motive.length === 0) return null;

  const suntFactori = motive.some((element) => element.maxim !== undefined);

  return (
    <section className="rounded-card border border-line bg-surface p-5">
      <h2 className="text-[15px] font-semibold text-ink">
        {suntFactori ? "Din ce s-a compus punctajul" : "De ce a fost respinsă automat"}
      </h2>

      <ul className="mt-3 flex flex-col gap-2.5">
        {motive.map((element) => (
          <li key={element.cod} className="flex items-start justify-between gap-4">
            <span className="text-[13px] leading-[19px] text-ink-soft">
              {element.explicatie ?? element.text ?? element.cod}
            </span>
            {element.maxim !== undefined ? (
              <span
                className={cn(
                  "shrink-0 rounded-full px-2.5 py-1 text-[11.5px] font-medium tabular",
                  (element.puncte ?? 0) >= element.maxim * 0.6
                    ? "bg-success/10 text-success"
                    : "bg-warning/10 text-warning",
                )}
              >
                {element.puncte}/{element.maxim}
              </span>
            ) : null}
          </li>
        ))}
      </ul>

      {suntFactori && scor !== null ? (
        <p className="mt-4 border-t border-line pt-3 text-[13px] text-ink-faint">
          Total {scor} din 100. Peste 70 se aprobă automat, sub 45 se respinge; între ele
          decide un om.
        </p>
      ) : null}
    </section>
  );
}

/** Cele patru surse de venit, si ce a gasit fiecare. */
function Verificari({ verificari }: { verificari: VerificareVenit[] }) {
  if (verificari.length === 0) return null;

  // Doar ultima rulare per sursa: fiecare reevaluare scrie randuri noi, iar
  // istoricul complet e in baza, pentru audit — aici conteaza starea de acum.
  const ultimele = new Map<string, VerificareVenit>();
  for (const verificare of verificari) ultimele.set(verificare.sursa, verificare);

  return (
    <section className="rounded-card border border-line bg-surface p-5">
      <h2 className="text-[15px] font-semibold text-ink">Cum a ajuns banca la cifre</h2>
      <p className="mt-1 text-[13px] leading-[19px] text-ink-faint">
        Neavând acces la ANAF sau Biroul de Credit, se coroborează patru surse.
      </p>

      <ul className="mt-4 flex flex-col divide-y divide-line">
        {[...ultimele.values()].map((verificare) => (
          <li
            key={verificare.sursa}
            className="flex items-center justify-between gap-4 py-3 first:pt-0 last:pb-0"
          >
            <div className="min-w-0">
              <p className="text-[13px] font-medium text-ink">
                {ETICHETE_SURSA[verificare.sursa]}
              </p>
              <p className="text-[12px] text-ink-faint">
                {verificare.incredere === null
                  ? "fără încredere calculată"
                  : `încredere ${(Number(verificare.incredere) * 100).toFixed(0)}%`}
              </p>
            </div>
            <span className="shrink-0 text-[13px] font-semibold tabular text-ink">
              {verificare.venit_constatat
                ? `${lei(verificare.venit_constatat)} RON`
                : verificare.obligatii_constatate
                  ? `${lei(verificare.obligatii_constatate)} RON obligații`
                  : "nimic găsit"}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

export const dynamic = "force-dynamic";
