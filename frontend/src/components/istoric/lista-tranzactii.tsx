"use client";

import { useMemo, useState } from "react";
import { ArrowDownLeft, ArrowUpRight } from "lucide-react";
import { Drawer, DrawerContent } from "@/components/ui/drawer";
import type { TranzactieAfisata } from "@/lib/data/tranzactii";
import { cn, formateazaSuma } from "@/lib/utils";
import { FiltreDrawer, type Filtre } from "@/components/istoric/filtre-drawer";

const ZI_MS = 24 * 60 * 60 * 1000;

function etichetaZi(data: Date) {
  const astazi = new Date();
  astazi.setHours(0, 0, 0, 0);
  const ziua = new Date(data);
  ziua.setHours(0, 0, 0, 0);
  const diferenta = Math.round((astazi.getTime() - ziua.getTime()) / ZI_MS);

  if (diferenta === 0) return "Astăzi";
  if (diferenta === 1) return "Ieri";
  return ziua.toLocaleDateString("ro-RO", { day: "numeric", month: "long" });
}

function trecePerioada(data: Date, perioada: Filtre["perioada"]) {
  if (perioada === "tot") return true;
  const zile = perioada === "7z" ? 7 : perioada === "30z" ? 30 : 90;
  return Date.now() - data.getTime() <= zile * ZI_MS;
}

export function ListaTranzactii({ tranzactii }: { tranzactii: TranzactieAfisata[] }) {
  const [filtre, setFiltre] = useState<Filtre>({ perioada: "30z", tip: "toate" });
  const [selectata, setSelectata] = useState<TranzactieAfisata | null>(null);

  const filtrate = useMemo(() => {
    return tranzactii.filter((t) => {
      if (filtre.tip !== "toate" && t.tip !== filtre.tip) return false;
      return trecePerioada(new Date(t.creatLa), filtre.perioada);
    });
  }, [tranzactii, filtre]);

  const grupuri = useMemo(() => {
    const map = new Map<string, TranzactieAfisata[]>();
    for (const t of filtrate) {
      const cheie = etichetaZi(new Date(t.creatLa));
      if (!map.has(cheie)) map.set(cheie, []);
      map.get(cheie)!.push(t);
    }
    return Array.from(map.entries());
  }, [filtrate]);

  return (
    <div className="mx-auto w-full max-w-[440px] px-6 pb-6 pt-8 sm:max-w-2xl">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold tracking-[-0.02em] text-ink">Istoric</h1>
        <FiltreDrawer
          filtre={filtre}
          onFiltreChange={setFiltre}
          numarRezultate={filtrate.length}
        />
      </div>

      {grupuri.length === 0 ? (
        <p className="mt-16 text-center text-[15px] text-ink-faint">
          {tranzactii.length === 0
            ? "Nu ai nicio tranzactie inca."
            : "Nicio tranzactie in perioada selectata."}
        </p>
      ) : (
        <div className="mt-6 flex flex-col gap-6">
          {grupuri.map(([zi, itemi]) => (
            <div key={zi}>
              <p className="mb-2 text-[13px] font-medium text-ink-faint">{zi}</p>
              <div className="overflow-hidden rounded-card bg-surface shadow-sm">
                {itemi.map((t, i) => (
                  <RandTranzactie
                    key={t.id}
                    tranzactie={t}
                    ultimul={i === itemi.length - 1}
                    onClick={() => setSelectata(t)}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      <Drawer
        open={selectata !== null}
        onOpenChange={(deschis) => {
          if (!deschis) setSelectata(null);
        }}
      >
        <DrawerContent
          title={selectata ? (selectata.tip === "primita" ? "Tranzactie primita" : "Tranzactie trimisa") : ""}
          description={selectata?.descriere ?? ""}
        >
          {selectata ? <DetaliuTranzactie tranzactie={selectata} /> : null}
        </DrawerContent>
      </Drawer>
    </div>
  );
}

function RandTranzactie({
  tranzactie,
  ultimul,
  onClick,
}: {
  tranzactie: TranzactieAfisata;
  ultimul: boolean;
  onClick: () => void;
}) {
  const primita = tranzactie.tip === "primita";
  const Icoana = primita ? ArrowDownLeft : ArrowUpRight;

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-muted",
        !ultimul && "border-b border-line",
      )}
    >
      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary-50">
        <Icoana size={18} strokeWidth={1.75} aria-hidden className="text-primary-600" />
      </span>

      <span className="min-w-0 flex-1">
        <span className="block truncate text-[15px] text-ink">
          {tranzactie.descriere || (primita ? "Transfer primit" : "Transfer trimis")}
        </span>
        <span className="block text-[12.5px] text-ink-faint">
          {new Date(tranzactie.creatLa).toLocaleTimeString("ro-RO", {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </span>
      </span>

      <span
        className={cn(
          "tabular shrink-0 text-[15px] font-semibold",
          primita ? "text-success" : "text-ink",
        )}
      >
        {primita ? "+" : "−"} {formateazaSuma(tranzactie.suma, tranzactie.valuta)}
      </span>
    </button>
  );
}

function DetaliuTranzactie({ tranzactie }: { tranzactie: TranzactieAfisata }) {
  const primita = tranzactie.tip === "primita";

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col items-center gap-1 py-2 text-center">
        <span
          className={cn(
            "tabular text-[32px] font-bold leading-[38px]",
            primita ? "text-success" : "text-ink",
          )}
        >
          {primita ? "+" : "−"} {formateazaSuma(tranzactie.suma, tranzactie.valuta)}
        </span>
        <span className="text-[13px] text-ink-faint">{primita ? "Primita" : "Trimisa"}</span>
      </div>

      <div>
        <Rand eticheta="Descriere" valoare={tranzactie.descriere || "—"} />
        <Rand
          eticheta="Data"
          valoare={new Date(tranzactie.creatLa).toLocaleString("ro-RO", {
            day: "numeric",
            month: "long",
            year: "numeric",
            hour: "2-digit",
            minute: "2-digit",
          })}
        />
        <Rand eticheta="ID tranzactie" valoare={tranzactie.id} mono />
      </div>
    </div>
  );
}

function Rand({ eticheta, valoare, mono }: { eticheta: string; valoare: string; mono?: boolean }) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-line py-3 last:border-0">
      <span className="text-[13px] text-ink-faint">{eticheta}</span>
      <span className={cn("text-right text-[15px] text-ink", mono && "tabular")}>{valoare}</span>
    </div>
  );
}
