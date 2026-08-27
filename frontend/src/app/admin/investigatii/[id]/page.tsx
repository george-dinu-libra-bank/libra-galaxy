import Link from "next/link";
import { notFound } from "next/navigation";
import { ChevronLeft } from "lucide-react";
import { cereAdmin } from "@/lib/admin";
import { BackendError } from "@/lib/backend";
import {
  ETICHETA_REZULTAT,
  ETICHETA_STARE,
  obtineDosar,
  type Dosar,
} from "@/lib/data/investigatii";
import { Banda } from "@/components/ui/banda";
import { CompuneMesajInvestigatie } from "@/components/admin/compune-mesaj-investigatie";
import { FirInvestigatie } from "@/components/admin/fir-investigatie";
import { IncheieInvestigatie } from "@/components/admin/incheie-investigatie";
import { formateazaSuma } from "@/lib/utils";

export const dynamic = "force-dynamic";

const STARI_INCHISE = ["rezolvat", "escalat", "inchis"] as const;

/** Intrebarile ramase deschise, din ultima analiza a agentului. */
function intrebariFaraRaspuns(dosar: Dosar): string[] {
  for (let i = dosar.mesaje.length - 1; i >= 0; i -= 1) {
    const s = dosar.mesaje[i].structura;
    if (s?.tip !== "analiza") continue;
    return Array.isArray(s.fara_raspuns)
      ? s.fara_raspuns.filter((x): x is string => typeof x === "string")
      : [];
  }
  return [];
}

function Antet({ dosar }: { dosar: Dosar }) {
  const { caz } = dosar;
  const inchisa = (STARI_INCHISE as readonly string[]).includes(caz.stare);

  return (
    <div className="flex flex-col gap-3 rounded-card border border-line bg-surface p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-[20px] font-bold leading-7 tracking-[-0.01em] text-ink">
            Investigație
          </h1>
          <p className="mt-1 max-w-2xl text-[14px] leading-[21px] text-ink-soft">
            {caz.motiv_deschidere}
          </p>
        </div>

        <span className="shrink-0 rounded-full bg-primary-50 px-3 py-1.5 text-[12px] font-semibold text-primary-700">
          {ETICHETA_STARE[caz.stare]}
        </span>
      </div>

      <dl className="flex flex-wrap gap-x-8 gap-y-2 border-t border-line pt-3 text-[13px]">
        {caz.gravitate !== null ? (
          <div>
            <dt className="text-ink-faint">Gravitate</dt>
            <dd className="font-semibold text-ink tabular">{caz.gravitate} / 100</dd>
          </div>
        ) : null}
        {caz.numar_semnalari !== null ? (
          <div>
            <dt className="text-ink-faint">Plăți semnalate</dt>
            <dd className="font-semibold text-ink tabular">{caz.numar_semnalari}</dd>
          </div>
        ) : null}
        <div>
          <dt className="text-ink-faint">Deschisă</dt>
          <dd className="font-semibold text-ink tabular">
            {new Date(caz.deschis_la).toLocaleDateString("ro-RO")}
          </dd>
        </div>
        {inchisa && caz.rezultat ? (
          <div>
            <dt className="text-ink-faint">Urmare</dt>
            <dd className="font-semibold text-ink">{ETICHETA_REZULTAT[caz.rezultat]}</dd>
          </div>
        ) : null}
      </dl>

      <Link
        href={`/admin/tranzactii/${caz.id_utilizator}`}
        className="w-fit text-[13px] font-semibold text-primary-600 underline-offset-2 hover:underline"
      >
        Vezi raportul contului
      </Link>
    </div>
  );
}

function Tranzactii({ dosar }: { dosar: Dosar }) {
  if (dosar.tranzactii.length === 0) return null;

  return (
    <section className="rounded-card border border-line bg-surface p-5">
      <h2 className="text-[15px] font-semibold text-ink">Plățile din investigație</h2>
      <ul className="mt-3 flex flex-col gap-2">
        {dosar.tranzactii.map((t) => (
          <li
            key={t.id}
            className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 border-b border-line pb-2 last:border-0 last:pb-0"
          >
            <span className="text-[14px] text-ink">{t.descriere ?? "Plată"}</span>
            <span className="text-[14px] font-semibold text-ink tabular">
              {formateazaSuma(t.suma, t.valuta)}
            </span>
            <span className="w-full text-[12px] text-ink-faint tabular">
              {new Date(t.creat_la).toLocaleDateString("ro-RO")}
              {t.motiv ? ` · ${t.motiv}` : ""}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

export default async function PaginaInvestigatie({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const [{ id }, admin] = await Promise.all([params, cereAdmin()]);

  const dosar = await obtineDosar(admin.token, id).catch((exc) => {
    if (exc instanceof BackendError && exc.status === 404) notFound();
    throw exc;
  });

  const inchisa = (STARI_INCHISE as readonly string[]).includes(dosar.caz.stare);
  const asteptamClientul = dosar.caz.stare === "asteptam_clientul";

  return (
    <div className="flex flex-col gap-6">
      <Link
        href="/admin/investigatii"
        className="inline-flex w-fit items-center gap-1.5 text-[13px] font-semibold text-primary-600 hover:underline"
      >
        <ChevronLeft size={16} strokeWidth={2} aria-hidden />
        Toate investigațiile
      </Link>

      <Antet dosar={dosar} />
      <Tranzactii dosar={dosar} />

      <section className="flex flex-col gap-3">
        <h2 className="text-[15px] font-semibold text-ink">Firul discuției</h2>
        <FirInvestigatie mesaje={dosar.mesaje} />
      </section>

      {/* Cât timp mingea e la client, nu se compune un al doilea mesaj: două
          întrebări trimise una peste alta îl încurcă pe om și lasă răspunsul
          fără o listă limpede la care să se raporteze. */}
      {asteptamClientul ? (
        <Banda ton="info">
          Mesajul a plecat. Așteptăm răspunsul clientului — până atunci nu se mai trimite nimic.
        </Banda>
      ) : null}

      {!inchisa && !asteptamClientul ? (
        <CompuneMesajInvestigatie idCaz={id} faraRaspuns={intrebariFaraRaspuns(dosar)} />
      ) : null}

      {!inchisa ? <IncheieInvestigatie idCaz={id} /> : null}
    </div>
  );
}
