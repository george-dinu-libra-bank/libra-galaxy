"use client";

import { cn } from "@/lib/utils";

/** Comutator pornit/oprit (DESIGN.md 7). Folosit in setari si in drawerul de securitate. */
export function Comutator({
  activ,
  onChange,
  eticheta,
  dezactivat = false,
}: {
  activ: boolean;
  onChange: () => void;
  eticheta: string;
  dezactivat?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={activ}
      aria-label={eticheta}
      onClick={onChange}
      disabled={dezactivat}
      className={cn(
        "relative h-7 w-12 shrink-0 rounded-full transition-colors duration-150 ease-soft",
        "focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25",
        "disabled:cursor-not-allowed disabled:opacity-50",
        activ ? "bg-primary-600" : "bg-line",
      )}
    >
      <span
        className={cn(
          "absolute left-1 top-1 h-5 w-5 rounded-full bg-white shadow-sm transition-transform duration-150 ease-soft",
          activ ? "translate-x-5" : "translate-x-0",
        )}
      />
    </button>
  );
}
