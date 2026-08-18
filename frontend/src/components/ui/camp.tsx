"use client";

import { AlertCircle, Check, Eye, EyeOff, type LucideIcon } from "lucide-react";
import { useId, useState, type InputHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

type Props = Omit<InputHTMLAttributes<HTMLInputElement>, "id"> & {
  eticheta: string;
  icoana?: LucideIcon;
  eroare?: string | null;
  ajutor?: string;
  validat?: boolean;
  /** Adauga butonul de afisare/ascundere a parolei. */
  parola?: boolean;
};

export function Camp({
  eticheta,
  icoana: Icoana,
  eroare,
  ajutor,
  validat = false,
  parola = false,
  className,
  type = "text",
  ...props
}: Props) {
  const id = useId();
  const [vizibil, setVizibil] = useState(false);

  const idEroare = `${id}-eroare`;
  const idAjutor = `${id}-ajutor`;
  const tipEfectiv = parola ? (vizibil ? "text" : "password") : type;

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-[13px] font-medium text-ink-soft">
        {eticheta}
      </label>

      <div
        className={cn(
          "group relative flex h-[52px] items-center rounded-field border bg-surface",
          "transition-[border-color,box-shadow] duration-150 ease-soft",
          "focus-within:ring-4",
          eroare
            ? "border-danger focus-within:border-danger focus-within:ring-danger/12"
            : "border-line focus-within:border-primary-500 focus-within:ring-primary-500/12",
        )}
      >
        {Icoana ? (
          <Icoana
            size={18}
            strokeWidth={1.75}
            aria-hidden
            className={cn(
              "ml-4 shrink-0 transition-colors duration-150",
              eroare
                ? "text-danger"
                : "text-ink-faint group-focus-within:text-primary-600",
            )}
          />
        ) : null}

        <input
          {...props}
          id={id}
          type={tipEfectiv}
          aria-invalid={eroare ? true : undefined}
          aria-describedby={eroare ? idEroare : ajutor ? idAjutor : undefined}
          className={cn(
            "h-full w-full bg-transparent px-3 text-[15px] text-ink outline-none",
            "placeholder:text-ink-faint",
            Icoana ? "pl-3" : "pl-4",
            "disabled:cursor-not-allowed disabled:text-ink-faint",
            className,
          )}
        />

        {parola ? (
          <button
            type="button"
            onClick={() => setVizibil((v) => !v)}
            aria-label={vizibil ? "Ascunde parola" : "Arata parola"}
            className={cn(
              "mr-2 flex h-11 w-11 shrink-0 items-center justify-center rounded-xl",
              "text-ink-faint transition-colors hover:bg-primary-50 hover:text-primary-600",
              "focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25",
            )}
          >
            {vizibil ? (
              <EyeOff size={18} strokeWidth={1.75} aria-hidden />
            ) : (
              <Eye size={18} strokeWidth={1.75} aria-hidden />
            )}
          </button>
        ) : null}

        {validat && !eroare && !parola ? (
          <Check
            size={18}
            strokeWidth={1.75}
            aria-hidden
            className="mr-4 shrink-0 animate-pop text-success"
          />
        ) : null}
      </div>

      {eroare ? (
        <p
          id={idEroare}
          role="alert"
          className="flex animate-fade-up items-center gap-1.5 text-[12.5px] text-danger"
        >
          <AlertCircle size={14} strokeWidth={1.75} aria-hidden className="shrink-0" />
          {eroare}
        </p>
      ) : ajutor ? (
        <p id={idAjutor} className="text-[12.5px] text-ink-faint">
          {ajutor}
        </p>
      ) : null}
    </div>
  );
}
