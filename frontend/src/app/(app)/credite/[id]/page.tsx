import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { DetaliuCreditVizual } from "@/components/credite/detaliu-credit";
import { obtineCalculRambursare, obtineDetaliuCredit } from "@/lib/data/credite";

export const metadata: Metadata = {
  title: "Credit · Libra",
};

export default async function CreditPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;

  // Citirea proceseaza intai ratele scadente, deci soldul afisat e la zi.
  const detaliu = await obtineDetaliuCredit(id);
  if (!detaliu) notFound();

  // Calculul de rambursare are sens doar pe un credit deschis; pe unul stins,
  // backendul refuza operatiunea, deci nici nu il cerem.
  const inchis =
    detaliu.credit.status === "inchis" || detaliu.credit.status === "rambursat_anticipat";
  const calcul = inchis ? null : await obtineCalculRambursare(id);

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
        Galaxy Flex Personal
      </h1>

      <DetaliuCreditVizual detaliu={detaliu} calcul={calcul} />
    </div>
  );
}
