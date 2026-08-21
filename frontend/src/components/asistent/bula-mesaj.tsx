import { FileDown, Mic } from "lucide-react";
import { cn } from "@/lib/utils";
import type { FisierGenerat, NivelIncredere } from "@/lib/data/asistent";

function ora(data: string) {
  return new Date(data).toLocaleTimeString("ro-RO", { hour: "2-digit", minute: "2-digit" });
}

const STIL_INCREDERE: Record<NonNullable<NivelIncredere>, { eticheta: string; dot: string; text: string }> = {
  ridicat: { eticheta: "Încredere ridicată", dot: "bg-success", text: "text-success" },
  mediu: { eticheta: "Încredere medie", dot: "bg-warning", text: "text-warning" },
  scazut: { eticheta: "Încredere scăzută", dot: "bg-danger", text: "text-danger" },
};

export function BulaMesaj({
  rol,
  text,
  nivelIncredere,
  canal,
  creatLa,
  fisierGenerat,
}: {
  rol: "user" | "assistant";
  text: string;
  nivelIncredere: NivelIncredere;
  canal: "text" | "voce";
  creatLa: string;
  fisierGenerat?: FisierGenerat | null;
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
