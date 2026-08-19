import Link from "next/link";
import { ArrowDownLeft, ArrowUpRight } from "lucide-react";
import { AvatarProfil } from "@/components/ui/avatar-profil";
import type { TranzactieAfisata } from "@/lib/data/tranzactii";
import { cn, formateazaSuma } from "@/lib/utils";

/**
 * Rezumatul de pe dashboard: ultimele cateva miscari, cu poza celuilalt
 * participant. Istoricul complet, cu filtre si detalii, ramane pe /istoric.
 */
export function UltimeleTranzactii({ tranzactii }: { tranzactii: TranzactieAfisata[] }) {
  return (
    <section className="mt-8">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-ink">Ultimele tranzacții</h2>

        {tranzactii.length > 0 ? (
          <Link
            href="/istoric"
            className="rounded-field px-2 py-1 text-[13px] font-semibold text-primary-600 transition-colors hover:bg-primary-50 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
          >
            Vezi tot
          </Link>
        ) : null}
      </div>

      {tranzactii.length === 0 ? (
        <p className="mt-4 rounded-card bg-surface p-6 text-center text-[15px] text-ink-faint shadow-sm">
          Nu ai nicio tranzacție încă.
        </p>
      ) : (
        <div className="mt-4 overflow-hidden rounded-card bg-surface shadow-sm">
          {tranzactii.map((tranzactie, i) => (
            <Rand
              key={tranzactie.id}
              tranzactie={tranzactie}
              ultimul={i === tranzactii.length - 1}
            />
          ))}
        </div>
      )}
    </section>
  );
}

function Rand({
  tranzactie,
  ultimul,
}: {
  tranzactie: TranzactieAfisata;
  ultimul: boolean;
}) {
  const primita = tranzactie.tip === "primita";
  const Sageata = primita ? ArrowDownLeft : ArrowUpRight;

  // Contrapartea lipseste doar daca profilul celuilalt a fost sters intre timp.
  const nume = tranzactie.contraparte?.nume ?? "Cont Libra";

  return (
    <div
      className={cn(
        "flex items-center gap-3 px-4 py-3",
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
          <Sageata size={10} strokeWidth={2.5} aria-hidden className="text-white" />
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
          {tranzactie.grup?.directie === "din"
            ? `din grupul ${tranzactie.grup.nume} · `
            : ""}
          {tranzactie.descriere ? `${tranzactie.descriere} · ` : ""}
          {new Date(tranzactie.creatLa).toLocaleDateString("ro-RO", {
            day: "numeric",
            month: "short",
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
    </div>
  );
}
