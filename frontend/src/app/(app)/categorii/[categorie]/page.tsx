import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowDownLeft, ArrowUpRight, ChevronLeft } from "lucide-react";
import { obtineTranzactiiCategorizate } from "@/lib/data/analiza";
import { CATEGORIE_INFO, etichetaCategorie } from "@/lib/categorii";
import { cn, formateazaSuma } from "@/lib/utils";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ categorie: string }>;
}): Promise<Metadata> {
  const { categorie } = await params;
  return { title: `${etichetaCategorie(categorie)} · Galaxy Bank` };
}

/**
 * Tranzactiile unei singure categorii, luna curenta — categoria vine
 * determinista din backend (tools/categorii_tranzactii.py), aici doar se
 * filtreaza lista deja categorizata (CLAUDE.md #7: nu se reimplementeaza
 * categorizeaza() in TypeScript).
 */
export default async function CategoriePage({
  params,
}: {
  params: Promise<{ categorie: string }>;
}) {
  const { categorie } = await params;

  if (!CATEGORIE_INFO[categorie]) notFound();

  const toate = await obtineTranzactiiCategorizate();
  const tranzactii = toate.filter((t) => t.categorie === categorie);
  const Icona = CATEGORIE_INFO[categorie].icona;

  return (
    <div className="mx-auto w-full max-w-[440px] px-6 pb-6 pt-8 sm:max-w-2xl">
      <Link
        href="/categorii"
        className="-ml-2 inline-flex h-10 items-center gap-1 rounded-xl px-2 text-[13px] font-medium text-ink-soft transition-colors hover:text-primary-700 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
      >
        <ChevronLeft size={18} strokeWidth={1.75} aria-hidden />
        Categorii
      </Link>

      <div className="mt-2 flex items-center gap-3">
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-primary-50 text-primary-600">
          <Icona size={20} strokeWidth={1.75} aria-hidden />
        </span>
        <h1 className="text-xl font-bold tracking-[-0.02em] text-ink">
          {etichetaCategorie(categorie)}
        </h1>
      </div>

      {tranzactii.length === 0 ? (
        <p className="mt-16 text-center text-[15px] text-ink-faint">
          Nu ai nicio tranzacție în această categorie luna asta.
        </p>
      ) : (
        <div className="mt-6 overflow-hidden rounded-card bg-surface shadow-sm">
          {tranzactii.map((t, i) => {
            const iesire = t.directie === "iesire";
            const Sageata = iesire ? ArrowUpRight : ArrowDownLeft;
            return (
              <div
                key={`${t.data}-${t.suma}-${i}`}
                className={cn(
                  "flex items-center gap-3 px-4 py-3",
                  i !== tranzactii.length - 1 && "border-b border-line",
                )}
              >
                <span
                  className={cn(
                    "flex h-10 w-10 shrink-0 items-center justify-center rounded-full",
                    iesire ? "bg-primary-50 text-primary-600" : "bg-success/12 text-success",
                  )}
                >
                  <Sageata size={16} strokeWidth={2} aria-hidden />
                </span>

                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[15px] text-ink">
                    {t.descriere || etichetaCategorie(t.categorie)}
                  </span>
                  <span className="block text-[12.5px] text-ink-faint">
                    {new Date(t.data).toLocaleDateString("ro-RO", { day: "numeric", month: "short" })}
                  </span>
                </span>

                <span
                  className={cn(
                    "tabular shrink-0 text-[15px] font-semibold",
                    iesire ? "text-ink" : "text-success",
                  )}
                >
                  {iesire ? "−" : "+"} {formateazaSuma(t.suma, t.valuta)}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
