import Image from "next/image";
import { cn } from "@/lib/utils";

/**
 * Sigla Galaxy Bank. PNG cu fundal transparent (500x500) — se afiseaza direct,
 * fara cutie colorata in jur, la orice dimensiune.
 */
export function Logo({ size = 40, className }: { size?: number; className?: string }) {
  return (
    <Image
      src="/logo.png"
      alt="Galaxy Bank"
      width={size}
      height={size}
      className={cn("shrink-0", className)}
    />
  );
}
