"use client";

import { Check } from "lucide-react";
import { useId, type ReactNode } from "react";
import { cn } from "@/lib/utils";

type Props = {
  checked: boolean;
  onCheckedChange: (valoare: boolean) => void;
  children: ReactNode;
  eroare?: string | null;
  disabled?: boolean;
};

export function Checkbox({
  checked,
  onCheckedChange,
  children,
  eroare,
  disabled,
}: Props) {
  const id = useId();

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-start gap-3">
        <button
          type="button"
          role="checkbox"
          id={id}
          aria-checked={checked}
          aria-invalid={eroare ? true : undefined}
          disabled={disabled}
          onClick={() => onCheckedChange(!checked)}
          className={cn(
            "mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-md border",
            "transition-colors duration-150 ease-soft",
            "focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25",
            checked
              ? "border-primary-600 bg-primary-600"
              : eroare
                ? "border-danger bg-surface"
                : "border-line bg-surface hover:border-primary-400",
            disabled && "cursor-not-allowed opacity-60",
          )}
        >
          {checked ? (
            <Check
              size={14}
              strokeWidth={3}
              aria-hidden
              className="animate-pop text-white"
            />
          ) : null}
        </button>

        <label
          htmlFor={id}
          className="cursor-pointer text-[13px] leading-[18px] text-ink-soft"
        >
          {children}
        </label>
      </div>

      {eroare ? (
        <p role="alert" className="animate-fade-up pl-8 text-[12.5px] text-danger">
          {eroare}
        </p>
      ) : null}
    </div>
  );
}
