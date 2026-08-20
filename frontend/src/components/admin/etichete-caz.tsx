import { Check, HelpCircle, X } from "lucide-react";
import type { CazVerificare } from "@/lib/data/admin-verificari";
import { cn } from "@/lib/utils";

type Ton = "bun" | "rau" | "necunoscut";

const STILURI: Record<Ton, string> = {
  bun: "bg-success/10 text-success",
  rau: "bg-danger/8 text-danger",
  necunoscut: "bg-muted text-ink-faint",
};

const ICOANE = { bun: Check, rau: X, necunoscut: HelpCircle } as const;

function Eticheta({ ton, children }: { ton: Ton; children: React.ReactNode }) {
  const Icoana = ICOANE[ton];

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11.5px] font-medium",
        STILURI[ton],
      )}
    >
      <Icoana size={12} strokeWidth={2.25} aria-hidden className="shrink-0" />
      {children}
    </span>
  );
}

/**
 * Cele doua dovezi, rezumate: potrivirea fetelor si CNP-ul.
 *
 * Numarul fetelor e o DISTANTA, nu un scor de similaritate — mai mic inseamna
 * mai asemanator. De aceea nu se afiseaza niciodata singur, ci mereu langa
 * prag si langa verdictul in cuvinte: "0.37" fara context ar parea un scor
 * mic, adica slab, si ar duce la respingerea unui cont bun.
 */
export function EticheteCaz({
  caz,
  className,
}: {
  caz: CazVerificare;
  className?: string;
}) {
  return (
    <span className={cn("flex flex-wrap items-center gap-1.5", className)}>
      {caz.distanta_fete === null || caz.prag === null ? (
        <Eticheta ton="necunoscut">Fața nu a fost detectată</Eticheta>
      ) : (
        <Eticheta ton={caz.sub_prag ? "bun" : "rau"}>
          Fețe: {caz.distanta_fete.toFixed(2)} / prag {caz.prag.toFixed(2)} —{" "}
          {caz.sub_prag ? "se potrivesc" : "nu se potrivesc"}
        </Eticheta>
      )}

      {caz.cnp_se_potriveste === null ? (
        <Eticheta ton="necunoscut">CNP necitit</Eticheta>
      ) : (
        <Eticheta ton={caz.cnp_se_potriveste ? "bun" : "rau"}>
          {caz.cnp_se_potriveste ? "CNP identic" : "CNP diferit"}
        </Eticheta>
      )}
    </span>
  );
}
