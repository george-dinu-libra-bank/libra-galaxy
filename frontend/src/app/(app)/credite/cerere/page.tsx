import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { CerereWizard } from "@/components/credite/cerere-wizard";
import { Banda } from "@/components/ui/banda";
import { obtineConturiUtilizator } from "@/lib/data/conturi";
import { obtineProdusCredit } from "@/lib/data/credite";

export const metadata: Metadata = {
  title: "Cerere de credit · Libra",
};

export default async function CererePage({
  searchParams,
}: {
  searchParams: Promise<{ suma?: string; luni?: string }>;
}) {
  const [{ suma: sumaBruta, luni: luniBrute }, produs, conturi] = await Promise.all([
    searchParams,
    obtineProdusCredit(),
    obtineConturiUtilizator(),
  ]);

  if (!produs) {
    return (
      <div className="mx-auto w-full max-w-[440px] px-6 pb-6 pt-8 sm:max-w-2xl">
        <Banda ton="eroare">
          Nu am putut încărca datele produsului. Încearcă din nou mai târziu.
        </Banda>
      </div>
    );
  }

  // Parametrii vin din URL, deci nu se au incredere: orice valoare in afara
  // limitelor produsului trimite omul inapoi la simulator, unde nu poate alege
  // gresit. Serverul reverifica oricum la depunere.
  const suma = Number(sumaBruta);
  const luni = Number(luniBrute);
  const valid =
    Number.isFinite(suma) &&
    Number.isFinite(luni) &&
    suma >= produs.sumaMin &&
    suma <= produs.sumaMax &&
    luni >= produs.luniMin &&
    luni <= produs.luniMax;

  if (!valid) redirect("/credite/simulare");

  // Creditul se vireaza numai in RON — RPC-ul credit_acorda (0010) respinge
  // orice alta valuta, deci nu are rost sa fie oferite in selector.
  const conturiRon = conturi.filter((cont) => cont.valuta === "RON");

  return (
    <div className="mx-auto w-full max-w-[440px] px-6 pb-6 pt-8 sm:max-w-2xl">
      <Link
        href={`/credite/simulare`}
        className="inline-flex items-center gap-1.5 text-[13px] text-ink-faint focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
      >
        <ArrowLeft size={16} strokeWidth={1.75} aria-hidden />
        Simulare
      </Link>

      <h1 className="mt-3 text-xl font-bold tracking-[-0.02em] text-ink">Cerere de credit</h1>
      <p className="mt-1 text-[13px] text-ink-faint">
        Verificăm veniturile în încasările din cont, nu doar ce declari.
      </p>

      {conturiRon.length === 0 ? (
        <div className="mt-6">
          <Banda ton="eroare">
            Ai nevoie de un cont în RON ca să primești creditul. Deschide unul din
            ecranul principal.
          </Banda>
        </div>
      ) : (
        <CerereWizard suma={suma} luni={luni} conturi={conturiRon} />
      )}
    </div>
  );
}
