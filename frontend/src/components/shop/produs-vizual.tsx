import Image from "next/image";
import type { Produs } from "@/lib/data/produse";
import { cn } from "@/lib/utils";

/** Latimea reala a vizualului in layout, ca Next sa serveasca poza potrivita. */
const SIZES = {
  card: "(min-width: 640px) 210px, 45vw",
  detaliu: "(min-width: 640px) 384px, 90vw",
  mic: "56px",
} as const;

const MARIMI_ICOANA = { card: 34, detaliu: 56, mic: 22 } as const;

/**
 * Imaginea produsului. Gradientul si icoana raman dedesubt ca placeholder
 * cat se incarca poza (sau daca lipseste fisierul).
 */
export function ProdusVizual({
  produs,
  marime = "card",
  alt = "",
  className,
}: {
  produs: Produs;
  marime?: "card" | "detaliu" | "mic";
  /** Lasa gol pentru vizual decorativ (numele produsului e deja in text). */
  alt?: string;
  className?: string;
}) {
  const Icoana = produs.icoana;

  return (
    <div
      className={cn(
        "relative flex shrink-0 items-center justify-center overflow-hidden rounded-card shadow-sm",
        marime === "detaliu" && "aspect-square w-full",
        marime === "card" && "aspect-square w-full",
        marime === "mic" && "h-14 w-14 rounded-field",
        className,
      )}
      style={{ background: produs.gradient }}
      aria-hidden={alt === "" || undefined}
    >
      <Icoana size={MARIMI_ICOANA[marime]} strokeWidth={1.5} className="text-white" />

      <Image
        src={produs.imagine}
        alt={alt}
        fill
        sizes={SIZES[marime]}
        className="object-cover"
      />
    </div>
  );
}
