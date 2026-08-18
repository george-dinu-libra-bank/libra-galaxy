"use client";

import { Loader2 } from "lucide-react";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/utils";

type Varianta = "primary" | "secondary" | "ghost" | "danger";
type Marime = "md" | "sm";

const VARIANTE: Record<Varianta, string> = {
  primary:
    "bg-primary-600 text-white shadow-btn hover:bg-primary-700 active:bg-primary-800 " +
    "disabled:bg-primary-100 disabled:text-primary-300 disabled:shadow-none",
  secondary:
    "bg-primary-50 text-primary-700 border border-primary-100 hover:bg-primary-100 " +
    "disabled:text-primary-300",
  ghost:
    "bg-transparent text-ink-soft hover:bg-primary-50 hover:text-primary-700 " +
    "disabled:text-ink-faint",
  danger:
    "bg-danger text-white hover:brightness-95 active:brightness-90 " +
    "disabled:bg-danger/30",
};

const MARIMI: Record<Marime, string> = {
  md: "h-[52px] px-6 text-[15px]",
  sm: "h-11 px-4 text-sm",
};

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  varianta?: Varianta;
  marime?: Marime;
  loading?: boolean;
  iconaStanga?: ReactNode;
};

export function Button({
  varianta = "primary",
  marime = "md",
  loading = false,
  iconaStanga,
  className,
  children,
  disabled,
  ...props
}: Props) {
  return (
    <button
      {...props}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-field font-semibold",
        "transition-[background-color,transform,box-shadow] duration-[180ms] ease-soft",
        "active:scale-[0.98] disabled:cursor-not-allowed disabled:active:scale-100",
        "focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25",
        VARIANTE[varianta],
        MARIMI[marime],
        className,
      )}
    >
      {loading ? (
        <Loader2 size={18} strokeWidth={1.75} className="animate-spin" aria-hidden />
      ) : (
        iconaStanga
      )}
      {children}
    </button>
  );
}
