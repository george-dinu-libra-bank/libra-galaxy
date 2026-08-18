import { AlertCircle, CheckCircle2, Info } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

type Ton = "eroare" | "succes" | "info";

const STILURI: Record<Ton, string> = {
  eroare: "bg-danger/8 text-danger",
  succes: "bg-success/10 text-success",
  info: "bg-primary-50 text-primary-700",
};

const ICOANE = {
  eroare: AlertCircle,
  succes: CheckCircle2,
  info: Info,
} as const;

/** Banda de mesaj la nivel de formular (DESIGN.md 7 si 9). */
export function Banda({ ton, children }: { ton: Ton; children: ReactNode }) {
  const Icoana = ICOANE[ton];

  return (
    <div
      role={ton === "eroare" ? "alert" : "status"}
      className={cn(
        "flex animate-band items-start gap-2.5 overflow-hidden rounded-field px-4 py-3",
        "text-[13px] leading-[18px]",
        STILURI[ton],
      )}
    >
      <Icoana size={16} strokeWidth={1.75} aria-hidden className="mt-px shrink-0" />
      <span>{children}</span>
    </div>
  );
}
