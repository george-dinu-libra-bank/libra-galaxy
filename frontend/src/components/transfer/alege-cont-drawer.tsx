"use client";

import { Check, ChevronRight, Landmark } from "lucide-react";
import {
  Drawer,
  DrawerClose,
  DrawerContent,
  DrawerTrigger,
} from "@/components/ui/drawer";
import type { Cont } from "@/lib/mock-data";
import { cn, formateazaIban, formateazaSuma } from "@/lib/utils";

export function AlegeContDrawer({
  conturi,
  selectat,
  onSelect,
}: {
  conturi: Cont[];
  selectat: Cont;
  onSelect: (cont: Cont) => void;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-[13px] font-medium text-ink-soft">Din cont</span>

      <Drawer>
        <DrawerTrigger className="flex h-[52px] w-full items-center gap-3 rounded-field border border-line bg-surface px-4 text-left transition-colors duration-150 ease-soft hover:border-primary-300 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/12">
          <Landmark size={18} strokeWidth={1.75} aria-hidden className="shrink-0 text-ink-faint" />
          <span className="min-w-0 flex-1">
            <span className="block truncate text-[15px] text-ink">{selectat.nume}</span>
            <span className="tabular block truncate text-[12.5px] text-ink-faint">
              {formateazaIban(selectat.iban)}
            </span>
          </span>
          <span className="tabular shrink-0 text-[13px] text-ink-faint">
            {formateazaSuma(selectat.sold, selectat.valuta)}
          </span>
          <ChevronRight size={18} strokeWidth={1.75} aria-hidden className="shrink-0 text-ink-faint" />
        </DrawerTrigger>

        <DrawerContent title="Alege contul sursa" description="Din ce cont trimiti banii.">
          <div className="flex flex-col gap-2">
            {conturi.map((cont) => (
              <DrawerClose key={cont.id} asChild>
                <button
                  type="button"
                  onClick={() => onSelect(cont)}
                  className={cn(
                    "flex w-full items-center gap-3 rounded-field border px-4 py-3 text-left transition-colors duration-150 ease-soft",
                    cont.id === selectat.id
                      ? "border-primary-500 bg-primary-50"
                      : "border-line bg-surface hover:bg-muted",
                  )}
                >
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[15px] text-ink">{cont.nume}</span>
                    <span className="tabular block truncate text-[12.5px] text-ink-faint">
                      {formateazaIban(cont.iban)}
                    </span>
                  </span>
                  <span className="tabular shrink-0 text-[13px] font-medium text-ink">
                    {formateazaSuma(cont.sold, cont.valuta)}
                  </span>
                  {cont.id === selectat.id ? (
                    <Check size={18} strokeWidth={1.75} aria-hidden className="shrink-0 text-primary-600" />
                  ) : null}
                </button>
              </DrawerClose>
            ))}
          </div>
        </DrawerContent>
      </Drawer>
    </div>
  );
}
