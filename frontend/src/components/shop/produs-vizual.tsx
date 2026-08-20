import type { Produs } from "@/lib/data/produse";
import { cn } from "@/lib/utils";

/** "Imaginea" produsului — placeholder in gradient pana vin poze reale. */
export function ProdusVizual({
  produs,
  marime = "card",
  className,
}: {
  produs: Produs;
  marime?: "card" | "detaliu" | "mic";
  className?: string;
}) {
  const Icoana = produs.icoana;

  const marimiIcoana = { card: 34, detaliu: 56, mic: 22 } as const;

  return (
    <div
      className={cn(
        "flex shrink-0 items-center justify-center rounded-card shadow-sm",
        marime === "detaliu" && "aspect-square w-full",
        marime === "card" && "aspect-square w-full",
        marime === "mic" && "h-14 w-14 rounded-field",
        className,
      )}
      style={{ background: produs.gradient }}
      aria-hidden
    >
      <Icoana size={marimiIcoana[marime]} strokeWidth={1.5} className="text-white" />
    </div>
  );
}
