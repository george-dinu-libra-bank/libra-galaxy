"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { History, Loader2, Plus, Trash2 } from "lucide-react";
import { useState, useTransition } from "react";
import { Drawer, DrawerContent, DrawerTrigger } from "@/components/ui/drawer";
import { stergeConversatie } from "@/lib/actions/asistent";
import type { ConversatieAsistent } from "@/lib/data/asistent";
import { cn } from "@/lib/utils";

function dataScurta(data: string) {
  return new Date(data).toLocaleDateString("ro-RO", { day: "numeric", month: "short" });
}

/** Istoricul conversatiilor — un istoric nu are nevoie de URL propriu, doar drawer (DESIGN.md 8.1). */
export function ListaConversatiiDrawer({
  conversatii,
  conversatieActivaId,
}: {
  conversatii: ConversatieAsistent[];
  conversatieActivaId: string | null;
}) {
  const router = useRouter();
  const [dePersConfirmat, setDePersConfirmat] = useState<string | null>(null);
  const [seSterge, startTransition] = useTransition();

  function sterge(id: string) {
    startTransition(async () => {
      const { eroare } = await stergeConversatie(id);
      setDePersConfirmat(null);
      if (eroare) return;

      // Conversatia stearsa nu mai exista — daca era cea activa, ecranul trebuie
      // sa arate gol, nu sa incerce sa reincarce mesaje care nu mai exista.
      if (id === conversatieActivaId) router.push("/asistent?nou=1");
      else router.refresh();
    });
  }

  return (
    <Drawer>
      <DrawerTrigger
        aria-label="Istoricul conversațiilor"
        className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-surface text-ink-soft shadow-sm transition-colors hover:bg-primary-50 hover:text-primary-700 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
      >
        <History size={18} strokeWidth={1.75} aria-hidden />
      </DrawerTrigger>

      <DrawerContent title="Conversații" description="Alege o conversație anterioară sau pornește una nouă.">
        <Link
          href="/asistent?nou=1"
          className="mb-3 flex h-12 items-center justify-center gap-2 rounded-field border border-primary-100 bg-primary-50 text-[14px] font-semibold text-primary-700 transition-colors hover:bg-primary-100"
        >
          <Plus size={16} strokeWidth={1.75} aria-hidden />
          Conversație nouă
        </Link>

        {conversatii.length === 0 ? (
          <p className="my-6 text-center text-[14px] text-ink-faint">Nicio conversație încă.</p>
        ) : (
          <div className="flex flex-col gap-1">
            {conversatii.map((conversatie) => {
              const cerutaStergere = dePersConfirmat === conversatie.id;

              if (cerutaStergere) {
                return (
                  <div
                    key={conversatie.id}
                    className="flex items-center justify-between gap-2 rounded-field bg-danger/8 px-3 py-2.5"
                  >
                    <span className="truncate text-[13px] text-danger">Ștergi „{conversatie.titlu}”?</span>
                    <div className="flex shrink-0 items-center gap-1">
                      <button
                        type="button"
                        onClick={() => sterge(conversatie.id)}
                        disabled={seSterge}
                        className="flex h-8 items-center rounded-lg bg-danger px-3 text-[12.5px] font-semibold text-white disabled:opacity-60"
                      >
                        {seSterge ? <Loader2 size={13} strokeWidth={2} className="animate-spin" aria-hidden /> : "Șterge"}
                      </button>
                      <button
                        type="button"
                        onClick={() => setDePersConfirmat(null)}
                        disabled={seSterge}
                        className="flex h-8 items-center rounded-lg px-3 text-[12.5px] font-medium text-ink-soft hover:bg-danger/10"
                      >
                        Renunță
                      </button>
                    </div>
                  </div>
                );
              }

              return (
                <div
                  key={conversatie.id}
                  className={cn(
                    "group flex items-center gap-1 rounded-field transition-colors hover:bg-primary-50",
                    conversatie.id === conversatieActivaId && "bg-primary-50",
                  )}
                >
                  <Link href={`/asistent?c=${conversatie.id}`} className="flex min-w-0 flex-1 flex-col gap-0.5 px-3 py-2.5">
                    <span className="truncate text-[14px] font-medium text-ink">{conversatie.titlu}</span>
                    <span className="text-[12px] text-ink-faint">{dataScurta(conversatie.actualizatLa)}</span>
                  </Link>
                  <button
                    type="button"
                    onClick={() => setDePersConfirmat(conversatie.id)}
                    aria-label={`Șterge conversația „${conversatie.titlu}”`}
                    className="mr-2 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-ink-faint transition-colors hover:bg-danger/10 hover:text-danger"
                  >
                    <Trash2 size={15} strokeWidth={1.75} aria-hidden />
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </DrawerContent>
    </Drawer>
  );
}
