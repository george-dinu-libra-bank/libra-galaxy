import type { Metadata } from "next";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { Simulator } from "@/components/credite/simulator";
import { Banda } from "@/components/ui/banda";
import { obtineProdusCredit } from "@/lib/data/credite";

export const metadata: Metadata = {
  title: "Simulare credit · Libra",
};

export default async function SimularePage() {
  // Limitele vin din catalogul din baza de date, nu din constante in interfata:
  // cand se schimba produsul, se schimba un rand, nu doua fisiere.
  const produs = await obtineProdusCredit();

  return (
    <div className="mx-auto w-full max-w-[440px] px-6 pb-6 pt-8 sm:max-w-2xl">
      <Link
        href="/credite"
        className="inline-flex items-center gap-1.5 text-[13px] text-ink-faint focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
      >
        <ArrowLeft size={16} strokeWidth={1.75} aria-hidden />
        Credite
      </Link>

      <h1 className="mt-3 text-xl font-bold tracking-[-0.02em] text-ink">
        {produs?.nume ?? "Simulare credit"}
      </h1>
      <p className="mt-1 text-[13px] text-ink-faint">
        Alege suma și perioada — rata se calculează pe loc.
      </p>

      {produs ? (
        <Simulator produs={produs} />
      ) : (
        <div className="mt-6">
          <Banda ton="eroare">
            Nu am putut încărca datele produsului. Încearcă din nou mai târziu.
          </Banda>
        </div>
      )}
    </div>
  );
}
