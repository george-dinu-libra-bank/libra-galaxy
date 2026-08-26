import type { Metadata } from "next";
import Link from "next/link";
import { obtineCheltuieliPeCategorie } from "@/lib/data/analiza";
import { CATEGORIE_INFO, etichetaCategorie } from "@/lib/categorii";
import { cn, formateazaSuma } from "@/lib/utils";

export const metadata: Metadata = {
  title: "Cheltuieli pe categorii · Galaxy Bank",
};

/** "2026-08" -> "August 2026" */
function numeLunaAnul(luna: string) {
  if (!luna) return "";
  const data = new Date(`${luna}-01T00:00:00`);
  const text = data.toLocaleDateString("ro-RO", { month: "long", year: "numeric" });
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export default async function CategoriiPage() {
  const cheltuieli = await obtineCheltuieliPeCategorie();

  return (
    <div className="mx-auto w-full max-w-[440px] px-6 pb-6 pt-8 sm:max-w-2xl">
      <h1 className="text-xl font-bold tracking-[-0.02em] text-ink">Cheltuieli pe categorii</h1>
      <p className="mt-1 text-[13px] text-ink-faint">{numeLunaAnul(cheltuieli.luna)}</p>

      {cheltuieli.categorii.length === 0 ? (
        <p className="mt-16 text-center text-[15px] text-ink-faint">
          Nu ai nicio cheltuială luna asta.
        </p>
      ) : (
        <div className="mt-6 grid grid-cols-2 gap-3">
          {cheltuieli.categorii.map((c) => {
            const info = CATEGORIE_INFO[c.categorie];
            const Icona = info?.icona ?? CATEGORIE_INFO.altele.icona;
            return (
              <Link
                key={c.categorie}
                href={`/categorii/${c.categorie}`}
                className={cn(
                  "flex flex-col gap-2 rounded-card bg-surface p-4 shadow-sm",
                  "transition-[transform,box-shadow] duration-150 ease-soft",
                  "hover:shadow-md active:scale-[0.98] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25",
                )}
              >
                <span className="flex h-10 w-10 items-center justify-center rounded-full bg-primary-50 text-primary-600">
                  <Icona size={18} strokeWidth={1.75} aria-hidden />
                </span>
                <span className="truncate text-[13px] font-medium text-ink">
                  {etichetaCategorie(c.categorie)}
                </span>
                <span className="tabular truncate text-[15px] font-semibold text-ink">
                  {formateazaSuma(c.total, cheltuieli.valuta)}
                </span>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
