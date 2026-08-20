import Link from "next/link";
import type { Produs } from "@/lib/data/produse";
import { formateazaSuma } from "@/lib/utils";
import { ProdusVizual } from "./produs-vizual";

export function ProdusCard({ produs }: { produs: Produs }) {
  return (
    <Link
      href={`/shop/${produs.slug}`}
      className="group flex flex-col gap-3 rounded-card border border-line bg-surface p-3 transition-colors duration-150 ease-soft hover:bg-muted focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
    >
      <ProdusVizual produs={produs} marime="card" />

      <div className="flex flex-col gap-1">
        <span className="text-[14.5px] font-semibold leading-5 text-ink">{produs.nume}</span>
        <span className="text-[12.5px] leading-[17px] text-ink-faint">
          {produs.descriereScurta}
        </span>
        <span className="tabular mt-1 text-[15px] font-semibold text-primary-600">
          {formateazaSuma(produs.pret)}
        </span>
      </div>
    </Link>
  );
}
