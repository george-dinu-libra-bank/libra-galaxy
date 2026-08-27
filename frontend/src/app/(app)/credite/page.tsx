import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, Banknote, Calculator, Plus } from "lucide-react";
import type { ReactNode } from "react";
import { CardInVerificare, CardOferta, CardRespinsa } from "@/components/credite/cereri-in-curs";
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

const STARI_VERIFICARE = ["analiza_manuala", "in_analiza", "asteapta_documente"];
const STARI_RESPINSE = ["respinsa", "expirata", "anulata"];

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

  // Pagina se citeste de sus in jos in ordinea in care conteaza: intai ce cere
  // o semnatura, apoi banii pe care ii ai deja, apoi dosarele care asteapta un
  // raspuns, si la final ce s-a inchis. Fiecare grup e o sectiune cu titlu, in
  // loc de un singur teanc de carduri fara nume.
  const oferte = cereri.filter((cerere) => cerere.status === "oferta");
  const inVerificare = cereri.filter((cerere) => STARI_VERIFICARE.includes(cerere.status));
  const respinse = cereri.filter((cerere) => STARI_RESPINSE.includes(cerere.status));

  const active = credite.filter(
    (credit) => credit.status === "activ" || credit.status === "restant",
  );
  const inchise = credite.filter(
    (credit) => credit.status !== "activ" && credit.status !== "restant",
  );

  // Firele se cer si pentru dosarele inchise recent: acolo sta motivul scris de
  // analist, iar fara el o respingere n-are unde fi citita. Raman putine — o
  // persoana are cateva cereri, nu sute.
  const inLucru = [...oferte, ...inVerificare, ...respinse];
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
      oferte.map(async (cerere) => [cerere.id, await obtineContractCerere(cerere.id)] as const),
    ),
  ) as Record<string, ContractCerere | null>;

  // Ecranul de intrare („n-ai niciun credit") apare doar cand chiar nu e nimic
  // in lucru. O cerere respinsa nu-l ascunde: acolo invitatia de a depune din
  // nou e exact ce trebuie sa vada omul.
  const gol = credite.length === 0 && oferte.length === 0 && inVerificare.length === 0;

  return (
    <div className="mx-auto w-full max-w-[440px] px-6 pb-6 pt-8 sm:max-w-2xl">
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-xl font-bold tracking-[-0.02em] text-ink">Credite</h1>
        <Link
          href="/credite/simulare"
          className="inline-flex h-10 shrink-0 items-center gap-1.5 rounded-full bg-primary-600 px-4 text-[14px] font-semibold text-white shadow-btn transition-colors duration-150 ease-soft hover:bg-primary-700 active:scale-[0.98] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
        >
          <Plus size={17} strokeWidth={2} aria-hidden />
          Credit nou
        </Link>
      </div>

      {eroare ? (
        <div className="mt-4">
          <Banda ton="eroare">{eroare}</Banda>
        </div>
      ) : null}

      {gol && !eroare ? (
        <section className="mt-6 rounded-card bg-surface p-7 text-center shadow-sm">
          <span className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-primary-50 text-primary-600">
            <Banknote size={26} strokeWidth={1.5} aria-hidden />
          </span>
          <h2 className="mt-5 text-[17px] font-semibold text-ink">
            {produs?.nume ?? "Credit de nevoi personale"}
          </h2>
          <p className="mt-2.5 text-[15px] leading-[22px] text-ink-soft">
            {produs
              ? `Între ${formateazaSuma(produs.sumaMin)} și ${formateazaSuma(produs.sumaMax)}, cu dobândă fixă de ${(produs.dobandaAnuala * 100).toFixed(2).replace(".", ",")}% pe an.`
              : "Vezi cât ai de plată lunar înainte să depui o cerere."}
          </p>
          <Link
            href="/credite/simulare"
            className="mt-6 flex h-12 w-full items-center justify-center gap-2 rounded-field bg-primary-600 text-[15px] font-semibold text-white shadow-btn transition-[transform,box-shadow] duration-[180ms] ease-soft hover:shadow-md active:scale-[0.99] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
          >
            <Calculator size={18} strokeWidth={1.75} aria-hidden />
            Simulează un credit
          </Link>
        </section>
      ) : null}

      {/* Ofertele stau deasupra creditelor active: sunt singurul lucru din
          pagina care expira daca omul nu face nimic. */}
      {oferte.length > 0 ? (
        <Sectiune titlu="De semnat" numar={oferte.length}>
          {oferte.map((cerere) => (
            <CardOferta
              key={cerere.id}
              cerere={cerere}
              conturi={conturi}
              mesaje={fire[cerere.id] ?? []}
              contract={contracte[cerere.id] ?? null}
              discutieDeschisa={discutie === cerere.id}
            />
          ))}
        </Sectiune>
      ) : null}

      {active.length > 0 ? (
        <Sectiune titlu="Credite active" numar={active.length}>
          {active.map((credit) => (
            <CardCredit key={credit.id} credit={credit} />
          ))}
        </Sectiune>
      ) : null}

      {inVerificare.length > 0 ? (
        <Sectiune titlu="În verificare" numar={inVerificare.length}>
          {inVerificare.map((cerere) => (
            <CardInVerificare
              key={cerere.id}
              cerere={cerere}
              mesaje={fire[cerere.id] ?? []}
              discutieDeschisa={discutie === cerere.id}
            />
          ))}
        </Sectiune>
      ) : null}

      {inchise.length > 0 ? (
        <Sectiune titlu="Credite încheiate" numar={inchise.length}>
          {inchise.map((credit) => (
            <CardCredit key={credit.id} credit={credit} />
          ))}
        </Sectiune>
      ) : null}

      {respinse.length > 0 ? (
        <Sectiune titlu="Cereri respinse" numar={respinse.length}>
          {respinse.map((cerere) => (
            <CardRespinsa
              key={cerere.id}
              cerere={cerere}
              mesaje={fire[cerere.id] ?? []}
              discutieDeschisa={discutie === cerere.id}
            />
          ))}
        </Sectiune>
      ) : null}
    </div>
  );
}

/**
 * Un grup de carduri, cu titlu si numar.
 *
 * Acelasi antet pentru toate grupurile: asa se vede din prima ca sunt liste
 * diferite, nu un teanc continuu de carduri.
 */
function Sectiune({
  titlu,
  numar,
  children,
}: {
  titlu: string;
  numar: number;
  children: ReactNode;
}) {
  return (
    <section className="mt-8">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="text-[12.5px] font-semibold uppercase tracking-[0.07em] text-ink-faint">
          {titlu}
        </h2>
        <span className="tabular text-[12.5px] text-ink-faint">{numar}</span>
      </div>
      <div className="mt-3 space-y-4">{children}</div>
    </section>
  );
}

function CardCredit({
  credit,
}: {
  credit: Awaited<ReturnType<typeof obtineCredite>>["credite"][number];
}) {
  const eticheta = ETICHETE[credit.status] ?? ETICHETE.activ;
  const incheiat = credit.status !== "activ" && credit.status !== "restant";

  return (
    <Link
      href={`/credite/${credit.id}`}
      className="block rounded-card bg-surface p-5 shadow-sm transition-[transform,box-shadow] duration-[180ms] ease-soft hover:shadow-md active:scale-[0.99] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
    >
      <div className="flex items-center justify-between gap-3">
        <span className={cn("rounded-full px-2.5 py-1 text-[11px] font-medium", eticheta.clasa)}>
          {eticheta.text}
        </span>
        <ArrowRight size={20} strokeWidth={1.75} aria-hidden className="shrink-0 text-ink-faint" />
      </div>

      {/* O singura cifra mare, cu eticheta ei dedesubt. Restul detaliilor stau
          jos, despartite de o linie, in loc sa fie inghesuite intr-un rand
          lipit cu puncte. */}
      <p className="tabular mt-4 text-[26px] font-bold leading-[32px] text-ink">
        {formateazaSuma(incheiat ? credit.principal : credit.soldRamas)}
      </p>
      <p className="mt-1 text-[13px] text-ink-faint">
        {incheiat ? "credit achitat" : "rămas de plată"}
      </p>

      <dl className="mt-5 flex gap-8 border-t border-line pt-4">
        {!incheiat ? (
          <>
            <Detaliu eticheta="Rată lunară" valoare={formateazaSuma(credit.rataLunara)} />
            <Detaliu eticheta="Acordat" valoare={formateazaSuma(credit.principal)} />
          </>
        ) : null}
        <Detaliu eticheta="Durată" valoare={`${credit.luni} luni`} />
      </dl>
    </Link>
  );
}

function Detaliu({ eticheta, valoare }: { eticheta: string; valoare: string }) {
  return (
    <div className="min-w-0">
      <dt className="text-[12px] text-ink-faint">{eticheta}</dt>
      <dd className="tabular mt-1 text-[14px] font-semibold text-ink">{valoare}</dd>
    </div>
  );
}
