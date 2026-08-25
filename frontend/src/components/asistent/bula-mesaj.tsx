import { ArrowRight, FileDown, Landmark, Mic, Users } from "lucide-react";
import { cn, formateazaIban } from "@/lib/utils";
import type { ActiuneRapida, FisierGenerat, NivelIncredere } from "@/lib/data/asistent";
import { GRADIENTE_STIL_CARD } from "@/lib/stil-card";

function ora(data: string) {
  return new Date(data).toLocaleTimeString("ro-RO", { hour: "2-digit", minute: "2-digit" });
}

const STIL_INCREDERE: Record<NonNullable<NivelIncredere>, { eticheta: string; dot: string; text: string }> = {
  ridicat: { eticheta: "Încredere ridicată", dot: "bg-success", text: "text-success" },
  mediu: { eticheta: "Încredere medie", dot: "bg-warning", text: "text-warning" },
  scazut: { eticheta: "Încredere scăzută", dot: "bg-danger", text: "text-danger" },
};

/** Actiuni rapide fara vizual de cont (spre deosebire de "transfer") — doar un buton de navigare. */
const ACTIUNI_SIMPLE: Record<string, { eticheta: string; icona: typeof Landmark }> = {
  credit: { eticheta: "Cerere de credit", icona: Landmark },
  grup: { eticheta: "Creează grup", icona: Users },
};

export function BulaMesaj({
  rol,
  text,
  nivelIncredere,
  canal,
  creatLa,
  fisierGenerat,
  actiuneRapida,
}: {
  rol: "user" | "assistant";
  text: string;
  nivelIncredere: NivelIncredere;
  canal: "text" | "voce";
  creatLa: string;
  fisierGenerat?: FisierGenerat | null;
  actiuneRapida?: ActiuneRapida | null;
}) {
  const alMeu = rol === "user";
  const incredere = nivelIncredere ? STIL_INCREDERE[nivelIncredere] : null;

  return (
    <div className={cn("flex flex-col gap-1.5", alMeu ? "items-end" : "items-start")}>
      <div
        className={cn(
          "max-w-[85%] rounded-card px-4 py-2.5",
          alMeu ? "rounded-br-md bg-primary-600 text-white" : "rounded-bl-md bg-muted text-ink",
        )}
      >
        <p className="whitespace-pre-wrap break-words text-[15px] leading-[22px]">{text}</p>

        <div
          className={cn(
            "tabular mt-1 flex items-center gap-1 text-[11px] leading-4",
            alMeu ? "text-primary-100" : "text-ink-faint",
          )}
        >
          {canal === "voce" ? <Mic size={11} strokeWidth={1.75} aria-hidden /> : null}
          {ora(creatLa)}
        </div>
      </div>

      {!alMeu && fisierGenerat ? (
        <a
          href={fisierGenerat.url}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1.5 rounded-full bg-primary-50 px-2.5 py-1 text-[11px] font-medium text-primary-700 shadow-sm hover:bg-primary-100"
        >
          <FileDown size={12} strokeWidth={1.75} aria-hidden />
          Descarcă PDF
        </a>
      ) : null}

      {!alMeu && actiuneRapida?.tip === "transfer" ? (
        <a
          href={actiuneRapida.url}
          className="flex w-full max-w-[280px] flex-col gap-3 rounded-card p-4 text-white shadow-lg transition-transform duration-150 ease-soft active:scale-[0.98]"
          style={{ background: GRADIENTE_STIL_CARD.standard }}
        >
          {actiuneRapida.numeCont ? <span className="text-[13px] text-white/80">{actiuneRapida.numeCont}</span> : null}
          {actiuneRapida.iban ? (
            <span className="tabular text-[15px] tracking-[0.06em]">
              {formateazaIban(actiuneRapida.iban)}
              {actiuneRapida.valuta ? <span className="ml-2 text-[12px] text-white/80">{actiuneRapida.valuta}</span> : null}
            </span>
          ) : null}
          <span className="flex items-center justify-between rounded-field bg-white/15 px-3 py-2 text-[13px] font-medium">
            Transferuri
            <ArrowRight size={14} strokeWidth={1.75} aria-hidden />
          </span>
        </a>
      ) : null}

      {!alMeu && actiuneRapida && ACTIUNI_SIMPLE[actiuneRapida.tip] ? (
        (() => {
          const { eticheta, icona: Icona } = ACTIUNI_SIMPLE[actiuneRapida.tip];
          return (
            <a
              href={actiuneRapida.url}
              className="flex items-center gap-2 rounded-field bg-primary-600 px-4 py-2.5 text-[13px] font-medium text-white shadow-lg transition-transform duration-150 ease-soft active:scale-[0.98] hover:bg-primary-700"
            >
              <Icona size={16} strokeWidth={1.75} aria-hidden />
              {eticheta}
              <ArrowRight size={14} strokeWidth={1.75} aria-hidden />
            </a>
          );
        })()
      ) : null}

      {!alMeu && incredere ? (
        <span
          className={cn(
            "inline-flex items-center gap-1.5 rounded-full bg-surface px-2.5 py-1 text-[11px] font-medium shadow-sm",
            incredere.text,
          )}
        >
          <span className={cn("h-1.5 w-1.5 rounded-full", incredere.dot)} aria-hidden />
          {incredere.eticheta}
        </span>
      ) : null}
    </div>
  );
}
