"use client";

import { Check, ChevronRight, Lock, Users, Wallet } from "lucide-react";
import {
  Drawer,
  DrawerClose,
  DrawerContent,
  DrawerTrigger,
} from "@/components/ui/drawer";
import type { ContSursa } from "@/lib/data/transfer";
import { cn, formateazaSuma } from "@/lib/utils";

/** Un rand din lista de surse — cont propriu sau sold de grup. */
function Rand({
  sursa,
  selectat,
  onSelect,
}: {
  sursa: ContSursa;
  selectat: ContSursa;
  onSelect: (sursa: ContSursa) => void;
}) {
  const ales = sursa.id === selectat.id && sursa.tip === selectat.tip;

  return (
    <DrawerClose asChild>
      <button
        type="button"
        disabled={sursa.blocat}
        onClick={() => onSelect(sursa)}
        className={cn(
          "flex w-full items-center gap-3 rounded-field border px-4 py-3 text-left transition-colors duration-150 ease-soft",
          "disabled:cursor-not-allowed disabled:opacity-60",
          ales
            ? "border-primary-500 bg-primary-50"
            : "border-line bg-surface hover:bg-muted disabled:hover:bg-surface",
        )}
      >
        <span className="min-w-0 flex-1">
          <span className="flex items-center gap-1.5">
            <span className="truncate text-[15px] text-ink">{sursa.nume}</span>
            {sursa.blocat ? (
              <span className="flex shrink-0 items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-[11px] font-medium text-ink-faint">
                <Lock size={11} strokeWidth={1.75} aria-hidden />
                Blocat
              </span>
            ) : null}
          </span>
          <span className="tabular block truncate text-[12.5px] text-ink-faint">
            {sursa.numarMascat}
          </span>
        </span>
        <span className="tabular shrink-0 text-[13px] font-medium text-ink">
          {formateazaSuma(sursa.sold, sursa.valuta)}
        </span>
        {ales ? (
          <Check size={18} strokeWidth={1.75} aria-hidden className="shrink-0 text-primary-600" />
        ) : null}
      </button>
    </DrawerClose>
  );
}

/**
 * Sursa transferului: unul dintre conturile proprii sau soldul comun al unui
 * grup din care faci parte (0009_core_banking_groups.sql).
 */
export function AlegeContDrawer({
  conturi,
  selectat,
  onSelect,
}: {
  conturi: ContSursa[];
  selectat: ContSursa;
  onSelect: (cont: ContSursa) => void;
}) {
  const conturiProprii = conturi.filter((sursa) => sursa.tip === "cont");
  const grupuri = conturi.filter((sursa) => sursa.tip === "grup");
  const dinGrup = selectat.tip === "grup";
  const Icoana = dinGrup ? Users : Wallet;

  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-[13px] font-medium text-ink-soft">
        {dinGrup ? "Din grup" : "Din cont"}
      </span>

      <Drawer>
        <DrawerTrigger className="flex h-[52px] w-full items-center gap-3 rounded-field border border-line bg-surface px-4 text-left transition-colors duration-150 ease-soft hover:border-primary-300 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/12">
          <Icoana size={18} strokeWidth={1.75} aria-hidden className="shrink-0 text-ink-faint" />
          <span className="min-w-0 flex-1">
            <span className="block truncate text-[15px] text-ink">{selectat.nume}</span>
            <span className="tabular block truncate text-[12.5px] text-ink-faint">
              {selectat.numarMascat}
            </span>
          </span>
          <span className="tabular shrink-0 text-[13px] text-ink-faint">
            {formateazaSuma(selectat.sold, selectat.valuta)}
          </span>
          <ChevronRight size={18} strokeWidth={1.75} aria-hidden className="shrink-0 text-ink-faint" />
        </DrawerTrigger>

        <DrawerContent
          title="Alege sursa"
          description="Din ce cont sau din ce grup pleacă banii."
        >
          <div className="flex flex-col gap-5">
            <div className="flex flex-col gap-2">
              <p className="text-[13px] font-medium text-ink-faint">Conturile mele</p>
              {conturiProprii.map((sursa) => (
                <Rand key={sursa.id} sursa={sursa} selectat={selectat} onSelect={onSelect} />
              ))}
            </div>

            {grupuri.length ? (
              <div className="flex flex-col gap-2">
                <p className="text-[13px] font-medium text-ink-faint">Grupuri</p>
                {grupuri.map((sursa) => (
                  <Rand
                    key={`grup-${sursa.id}`}
                    sursa={sursa}
                    selectat={selectat}
                    onSelect={onSelect}
                  />
                ))}
              </div>
            ) : null}
          </div>
        </DrawerContent>
      </Drawer>
    </div>
  );
}
