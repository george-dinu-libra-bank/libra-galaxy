import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, Banknote, Calculator } from "lucide-react";
import { CereriInCurs } from "@/components/credite/cereri-in-curs";
import { Banda } from "@/components/ui/banda";
import { obtineConturiUtilizator } from "@/lib/data/conturi";
import {
  obtineCereri,
  obtineContractCerere,
  obtineCredite,
  obtineMesajeCerere,
  obtineProdusCredit,
} from "@/lib/data/credite";
import type { ContractCerere, MesajCerere } from "@/lib/data/credite";
import { cn, formateazaSuma } from "@/lib/utils";

export const metadata: Metadata = {
  title: "Credite · Galaxy Bank",
};

const ETICHETE: Record<string, { text: string; clasa: string }> = {
  activ: { text: "Activ", clasa: "bg-primary-50 text-primary-700" },
  restant: { text: "Restant", clasa: "bg-danger/10 text-danger" },
  inchis: { text: "Închis", clasa: "bg-muted text-ink-soft" },
  rambursat_anticipat: { text: "Rambursat", clasa: "bg-success/10 text-success" },
};

export default async function CreditePage({
  searchParams,
}: {
  searchParams: Promise<{ discutie?: string }>;
}) {
  // `?discutie=<id>` vine din notificare: firul se deschide direct, ca
  // notificarea sa fie utilizabila, nu doar informativa.
  const { discutie } = await searchParams;
  // Citirea creditelor incaseaza intai ratele scadente (backendul le proceseaza
  // lenes), deci soldurile de mai jos sunt la zi in momentul afisarii.
  //
  // Cererile se citesc si ele: o oferta emisa dupa ce clientul a inchis
  // wizard-ul — cazul obisnuit cand dosarul trece prin analiza manuala — n-avea
  // pana acum unde sa apara, deci nu putea fi semnata niciodata.
  const [citireCredite, produs, citireCereri, conturi] = await Promise.all([
    obtineCredite(),
    obtineProdusCredit(),
    obtineCereri(),
    obtineConturiUtilizator(),
  ]);

  // Backendul cazut nu mai arata ca „n-ai niciun credit": ecranul de intrare si
  // banda de eroare spun lucruri diferite, iar al doilea e adevarat.
  const { credite } = citireCredite;
  const { cereri } = citireCereri;
  const eroare = citireCredite.eroare ?? citireCereri.eroare ?? null;

  // Ecranul de intrare („n-ai niciun credit, simuleaza unul") n-are ce cauta
  // sub o oferta pe care omul tocmai e invitat sa o semneze.
  const inCurs = cereri.some((cerere) =>
    ["oferta", "analiza_manuala", "asteapta_documente", "in_analiza"].includes(cerere.status),
  );

  // Firele se cer si pentru dosarele inchise recent: acolo sta motivul scris de
  // analist, iar fara el o respingere n-are unde fi citita. Raman putine — o
  // persoana are cateva cereri, nu sute.
  const inLucru = cereri.filter((cerere) =>
    [
      "oferta", "analiza_manuala", "asteapta_documente", "in_analiza",
      "respinsa", "expirata", "anulata",
    ].includes(cerere.status),
  );
  const fire = Object.fromEntries(
    await Promise.all(
      inLucru.map(
        async (cerere) => [cerere.id, await obtineMesajeCerere(cerere.id)] as const,
      ),
    ),
  ) as Record<string, MesajCerere[]>;

  // Contractul se cere doar pentru ofertele care asteapta semnatura: pentru
  // orice alta stare backendul raspunde 404, iar clientul n-are ce citi.
  const contracte = Object.fromEntries(
    await Promise.all(
      cereri
        .filter((cerere) => cerere.status === "oferta")
        .map(async (cerere) => [cerere.id, await obtineContractCerere(cerere.id)] as const),
    ),
  ) as Record<string, ContractCerere | null>;

  const active = credite.filter((credit) => credit.status === "activ" || credit.status === "restant");
  const inchise = credite.filter((credit) => credit.status !== "activ" && credit.status !== "restant");

  return (
    <div className="mx-auto w-full max-w-[440px] px-6 pb-6 pt-8 sm:max-w-2xl">
      <h1 className="text-xl font-bold tracking-[-0.02em] text-ink">Credite</h1>

      {eroare ? (
        <div className="mt-4">
          <Banda ton="eroare">{eroare}</Banda>
        </div>
      ) : null}

      <CereriInCurs
        cereri={cereri}
        conturi={conturi}
        mesaje={fire}
        contracte={contracte}
        discutieDeschisa={discutie ?? null}
      />

      {credite.length === 0 && !inCurs && !eroare ? (
        <section className="mt-6 rounded-card bg-surface p-6 text-center shadow-sm">
          <span className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-primary-50 text-primary-600">
            <Banknote size={26} strokeWidth={1.5} aria-hidden />
          </span>
          <h2 className="mt-4 text-[17px] font-semibold text-ink">
            {produs?.nume ?? "Credit de nevoi personale"}
          </h2>
          <p className="mt-2 text-[15px] leading-[22px] text-ink-soft">
            {produs
              ? `Între ${formateazaSuma(produs.sumaMin)} și ${formateazaSuma(produs.sumaMax)}, cu dobândă fixă de ${(produs.dobandaAnuala * 100).toFixed(2).replace(".", ",")}% pe an.`
              : "Vezi cât ai de plată lunar înainte să depui o cerere."}
          </p>
          <Link
            href="/credite/simulare"
            className="mt-5 flex h-12 w-full items-center justify-center gap-2 rounded-field bg-primary-600 text-[15px] font-semibold text-white shadow-btn transition-[transform,box-shadow] duration-[180ms] ease-soft hover:shadow-md active:scale-[0.99] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
          >
            <Calculator size={18} strokeWidth={1.75} aria-hidden />
            Simulează un credit
          </Link>
        </section>
      ) : null}

      {credite.length > 0 ? (
        <>
          {active.length > 0 ? (
            <ul className="mt-6 space-y-3">
              {active.map((credit) => (
                <li key={credit.id}>
                  <CardCredit credit={credit} />
                </li>
              ))}
            </ul>
          ) : null}

          {inchise.length > 0 ? (
            <>
              <h2 className="mt-8 text-lg font-semibold text-ink">Credite încheiate</h2>
              <ul className="mt-4 space-y-3">
                {inchise.map((credit) => (
                  <li key={credit.id}>
                    <CardCredit credit={credit} />
                  </li>
                ))}
              </ul>
            </>
          ) : null}

          <Link
            href="/credite/simulare"
            className="mt-6 flex h-12 w-full items-center justify-center gap-2 rounded-field border border-line bg-surface text-[15px] font-semibold text-ink shadow-sm transition-[transform,box-shadow] duration-[180ms] ease-soft hover:shadow-md active:scale-[0.99] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
          >
            <Calculator size={18} strokeWidth={1.75} aria-hidden />
            Simulează un credit nou
          </Link>
        </>
      ) : null}

      {credite.length === 0 && inCurs ? (
        <Link
          href="/credite/simulare"
          className="mt-6 flex h-12 w-full items-center justify-center gap-2 rounded-field border border-line bg-surface text-[15px] font-semibold text-ink shadow-sm transition-[transform,box-shadow] duration-[180ms] ease-soft hover:shadow-md active:scale-[0.99] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
        >
          <Calculator size={18} strokeWidth={1.75} aria-hidden />
          Simulează un credit
        </Link>
      ) : null}
    </div>
  );
}

function CardCredit({
  credit,
}: {
  credit: Awaited<ReturnType<typeof obtineCredite>>["credite"][number];
}) {
  const eticheta = ETICHETE[credit.status] ?? ETICHETE.activ;

  return (
    <Link
      href={`/credite/${credit.id}`}
      className="flex items-center gap-3 rounded-card bg-surface p-5 shadow-sm transition-[transform,box-shadow] duration-[180ms] ease-soft hover:shadow-md active:scale-[0.99] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
    >
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className={cn("rounded-full px-2 py-0.5 text-[11px] font-medium", eticheta.clasa)}>
            {eticheta.text}
          </span>
          <span className="text-[13px] text-ink-faint">{credit.luni} luni</span>
        </div>

        <p className="tabular mt-2 text-[22px] font-bold leading-[28px] text-ink">
          {formateazaSuma(credit.soldRamas)}
        </p>
        <p className="text-[13px] text-ink-faint">
          rămas din {formateazaSuma(credit.principal)} · rată{" "}
          {formateazaSuma(credit.rataLunara)}
        </p>
      </div>

      <ArrowRight size={20} strokeWidth={1.75} aria-hidden className="shrink-0 text-ink-faint" />
    </Link>
  );
}
