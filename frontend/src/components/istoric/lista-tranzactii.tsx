"use client";

import { useMemo, useState } from "react";
import { ArrowDownLeft, ArrowUpRight } from "lucide-react";
import { AvatarProfil } from "@/components/ui/avatar-profil";
import { Drawer, DrawerContent } from "@/components/ui/drawer";
import type { TranzactieAfisata } from "@/lib/data/tranzactii";
import { cn, etichetaZi, formateazaOra, formateazaSuma } from "@/lib/utils";
import { FiltreDrawer, type Filtre } from "@/components/istoric/filtre-drawer";

const ZI_MS = 24 * 60 * 60 * 1000;

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
          title={selectata ? (selectata.tip === "primita" ? "Bani primiți" : "Bani trimiși") : ""}
          description={selectata?.descriere || "Transfer între conturi Galaxy Bank."}
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
  const nume = tranzactie.contraparte?.nume ?? "Cont Galaxy Bank";

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "rand-hover flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-muted",
        "focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25",
        !ultimul && "border-b border-line",
      )}
    >
      <span className="relative h-10 w-10 shrink-0">
        <AvatarProfil
          url={tranzactie.contraparte?.avatarUrl ?? null}
          nume={nume}
          marimeIcoana={18}
        />

        {/* Directia ramane vizibila si cand avem poza. */}
        <span
          className={cn(
            "absolute -bottom-0.5 -right-0.5 flex h-[18px] w-[18px] items-center justify-center rounded-full border-2 border-surface",
            primita ? "bg-success" : "bg-primary-600",
          )}
        >
          <Icoana size={10} strokeWidth={2.5} aria-hidden className="text-white" />
        </span>
      </span>

      <span className="min-w-0 flex-1">
        <span className="block truncate text-[15px] text-ink">
          {tranzactie.intreConturiProprii ? (
            "Între conturile tale"
          ) : (
            <>
              {primita ? "Primit de la" : "Trimis către"}{" "}
              <span className="font-semibold">{nume}</span>
            </>
          )}
        </span>
        <span className="block truncate text-[12.5px] text-ink-faint">
          {/* Banii au plecat din punga comuna, nu din contul tau — se spune. */}
          {tranzactie.grup?.directie === "din"
            ? `din grupul ${tranzactie.grup.nume} · `
            : ""}
          {tranzactie.descriere ? `${tranzactie.descriere} · ` : ""}
          {formateazaOra(tranzactie.creatLa)}
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
  const nume = tranzactie.contraparte?.nume ?? "Cont Galaxy Bank";

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col items-center gap-2 py-2 text-center">
        <div className="h-16 w-16 overflow-hidden rounded-full border border-line">
          <AvatarProfil
            url={tranzactie.contraparte?.avatarUrl ?? null}
            nume={nume}
            marimeIcoana={28}
          />
        </div>

        <span
          className={cn(
            "tabular text-[32px] font-bold leading-[38px]",
            primita ? "text-success" : "text-ink",
          )}
        >
          {primita ? "+" : "−"} {formateazaSuma(tranzactie.suma, tranzactie.valuta)}
        </span>
        <span className="text-[13px] text-ink-faint">
          {tranzactie.intreConturiProprii
            ? "Mutare între conturile tale"
            : primita
              ? `Primit de la ${nume}`
              : `Trimis către ${nume}`}
        </span>
      </div>

      <div>
        <Rand eticheta={primita ? "Expeditor" : "Beneficiar"} valoare={nume} />
        {tranzactie.grup?.directie === "din" ? (
          <Rand eticheta="Sursă" valoare={`Grupul ${tranzactie.grup.nume}`} />
        ) : null}
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
