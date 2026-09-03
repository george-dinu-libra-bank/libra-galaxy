"use client";

import { X } from "lucide-react";
import { createContext, useContext, type ComponentProps, type ReactNode } from "react";
import { Drawer as Vaul } from "vaul";
import { cn } from "@/lib/utils";

/**
 * Wrapper peste vaul, stilizat conform DESIGN.md (sectiunea 8).
 * In ecrane se importa DE AICI, niciodata direct din "vaul", ca toate
 * drawerele sa arate si sa se comporte identic.
 */

const ContextScopTema = createContext("");

/**
 * Clasa de tema pe care o primesc drawerele deschise sub acest scop.
 *
 * Exista fiindca vaul face portal in `document.body`: continutul drawerului
 * ajunge in AFARA containerului din care a fost deschis, deci nu mosteneste
 * variabilele CSS rescrise pe acesta. Un grup cu tema verde (0054_tema_grup.sql)
 * si-ar deschide toate drawerele albastre — ceea ce arata a bug, nu a decizie.
 *
 * Contextul React trece prin portaluri (e legat de arborele de componente, nu de
 * cel din DOM), deci un singur provider in jurul paginii rezolva toate drawerele
 * de sub ea, fara sa le dam fiecaruia o prop. Un drawer care are nevoie de alta
 * tema decat a scopului foloseste prop-ul `clasaTema` de mai jos.
 *
 * Nu se pune pe overlay: acela e `bg-ink/40` in toate temele.
 */
export function ScopTemaDrawer({ clasa, children }: { clasa: string; children: ReactNode }) {
  return <ContextScopTema.Provider value={clasa}>{children}</ContextScopTema.Provider>;
}

export const Drawer = Vaul.Root;
/** Drawer deschis peste alt drawer (vaul se ocupa de stivuire). */
export const DrawerNested = Vaul.NestedRoot;
export const DrawerTrigger = Vaul.Trigger;
export const DrawerClose = Vaul.Close;

type ContentProps = ComponentProps<typeof Vaul.Content> & {
  /** Obligatoriu — citit de cititoarele de ecran. */
  title: string;
  /** Obligatoriu — o propozitie despre ce face drawerul. */
  description: string;
  /** Ascunde titlul vizual, dar il pastreaza pentru accesibilitate. */
  ascundeTitlu?: boolean;
  /** Buton „X" in coltul din dreapta sus. */
  cuInchidere?: boolean;
  /** Zona lipita jos: buton primar full-width, eventual o actiune ghost. */
  footer?: ReactNode;
  /**
   * Suprascrie tema mostenita din `ScopTemaDrawer`. Folosit acolo unde drawerul
   * chiar schimba tema (selectorul de tema al grupului): trebuie sa se picteze
   * in ce alegi acum, nu in ce e salvat. Nu se dau amandoua prin `className` —
   * doua clase `.tema-grup-*` pe acelasi element au aceeasi specificitate, deci
   * ar castiga cea scrisa mai jos in globals.css, nu cea dorita.
   */
  clasaTema?: string;
  children: ReactNode;
};

export function DrawerContent({
  title,
  description,
  ascundeTitlu = false,
  cuInchidere = true,
  footer,
  clasaTema,
  className,
  children,
  ...props
}: ContentProps) {
  const clasaScop = useContext(ContextScopTema);

  return (
    <Vaul.Portal>
      <Vaul.Overlay className="fixed inset-0 z-40 bg-ink/40" />

      <Vaul.Content
        {...props}
        className={cn(
          "fixed inset-x-0 bottom-0 z-50 mx-auto flex max-h-[92vh] w-full flex-col",
          "rounded-t-card bg-surface shadow-lg outline-none sm:max-w-[480px]",
          clasaTema ?? clasaScop,
          className,
        )}
      >
        {/* maner de tragere */}
        <div
          aria-hidden
          className="mx-auto mt-3 h-1 w-10 shrink-0 rounded-full bg-line"
        />

        <div className="flex items-start justify-between gap-4 px-6 pt-4">
          <div className={cn("flex flex-col gap-1", ascundeTitlu && "sr-only")}>
            <Vaul.Title className="text-lg font-semibold leading-6 text-ink">
              {title}
            </Vaul.Title>
            <Vaul.Description className="text-[12.5px] leading-[18px] text-ink-faint">
              {description}
            </Vaul.Description>
          </div>

          {cuInchidere ? (
            <Vaul.Close
              aria-label="Inchide"
              className={cn(
                "-mr-2 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl",
                "text-ink-faint transition-colors hover:bg-primary-50 hover:text-primary-700",
                "focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25",
              )}
            >
              <X size={18} strokeWidth={1.75} aria-hidden />
            </Vaul.Close>
          ) : null}
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-5">{children}</div>

        {footer ? (
          <div className="border-t border-line px-6 pt-4 pb-[max(24px,env(safe-area-inset-bottom))]">
            {footer}
          </div>
        ) : (
          <div className="pb-[max(8px,env(safe-area-inset-bottom))]" />
        )}
      </Vaul.Content>
    </Vaul.Portal>
  );
}
