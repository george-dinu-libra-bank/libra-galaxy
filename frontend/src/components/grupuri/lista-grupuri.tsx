import Link from "next/link";
import { ChevronRight, Users } from "lucide-react";
import type { GrupSumar } from "@/lib/data/grupuri";
import { formateazaSuma } from "@/lib/utils";

/** Grupurile utilizatorului, cu soldul comun si numarul de membri. */
export function ListaGrupuri({ grupuri }: { grupuri: GrupSumar[] }) {
  if (grupuri.length === 0) {
    return (
      <div className="mt-8 rounded-card bg-surface p-8 text-center shadow-sm">
        <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-primary-50">
          <Users size={22} strokeWidth={1.75} aria-hidden className="text-primary-600" />
        </span>
        <p className="mt-4 text-[15px] leading-[22px] text-ink-soft">
          Nu ești în niciun grup încă.
        </p>
        <p className="mt-1 text-[12.5px] leading-[18px] text-ink-faint">
          Creează unul și trimite codul mai departe, sau intră într-unul cu codul primit.
        </p>
      </div>
    );
  }

  return (
    <div className="mt-6 flex flex-col gap-3">
      {grupuri.map((grup, i) => (
        <Link
          key={grup.id}
          href={`/grupuri/${grup.id}`}
          className="animate-fade-up flex items-center gap-3 rounded-card bg-surface p-4 shadow-sm transition-[transform,box-shadow] duration-[180ms] ease-soft hover:shadow-md active:scale-[0.99] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
          style={{ animationDelay: `${i * 40}ms` }}
        >
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary-50">
            <Users size={18} strokeWidth={1.75} aria-hidden className="text-primary-600" />
          </span>

          <div className="min-w-0 flex-1">
            <p className="truncate text-[15px] font-semibold text-ink">{grup.nume}</p>
            <p className="text-[12.5px] text-ink-faint">
              {grup.membri === 1 ? "1 membru" : `${grup.membri} membri`}
            </p>
          </div>

          <p className="tabular shrink-0 text-[15px] font-bold text-ink">
            {formateazaSuma(grup.sold)}
          </p>

          <ChevronRight size={18} strokeWidth={1.75} aria-hidden className="shrink-0 text-ink-faint" />
        </Link>
      ))}
    </div>
  );
}
