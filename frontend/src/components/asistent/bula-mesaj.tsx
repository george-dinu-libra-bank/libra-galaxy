import Link from "next/link";
import { Fragment } from "react";
import { ArrowRight, FileDown, Landmark, Mic, Users } from "lucide-react";
import { cn, formateazaIban } from "@/lib/utils";
import type { ActiuneRapida, FisierGenerat, NivelIncredere } from "@/lib/data/asistent";
import { GRADIENTE_STIL_CARD } from "@/lib/stil-card";

/**
 * Caile interne din raspuns devin linkuri pe care se poate apasa.
 *
 * Bula randa `{text}` ca text simplu, deci cand asistentul pregateste o cerere
 * de credit si raspunde cu "/credite/cerere?suma=30000&..." omul vedea niste
 * caractere, nu ceva de apasat — linkul „nu exista", desi pagina era acolo.
 *
 * Doar cai care incep cu `/`, niciodata adrese externe si niciodata
 * `dangerouslySetInnerHTML`: continutul vine de la un model, deci se randeaza
 * ca text si se inlocuiesc doar bucatile care se potrivesc exact cu un traseu
 * din aplicatie. Nimic din ce spune modelul nu poate deveni HTML.
 */
// Numai sectiunile care exista chiar in aplicatie, nu orice bucata care incepe
// cu `/`. Altfel „Rata 1/36" din raspuns devenea un link catre /36.
const CALE_INTERNA =
  /(\/(?:credite|dashboard|istoric|transfer|carduri|grupuri|setari|asistent|beneficiari|admin)(?:\/[a-z0-9\-]+)*(?:\?[a-zA-Z0-9%+=&._-]*)?)/g;

function cuLinkuri(text: string) {
  return text.split(CALE_INTERNA).map((bucata, indice) => {
    if (indice % 2 === 1) {
      return (
        <Link
          key={indice}
          href={bucata}
          className="font-semibold underline underline-offset-2 hover:opacity-80"
        >
          {bucata}
        </Link>
      );
    }
    return <Fragment key={indice}>{bucata}</Fragment>;
  });
}

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
        <p className="whitespace-pre-wrap break-words text-[15px] leading-[22px]">
          {cuLinkuri(text)}
        </p>

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

      {!alMeu && actiuneRapida?.tip === "transfer" && actiuneRapida.conturi.length > 0 ? (
        <div className="flex w-full flex-col items-center gap-2.5">
          {actiuneRapida.conturi.map((cont) => (
            <a
              key={cont.id}
              href={`/transfer?cont=${cont.id}`}
              className="flex w-full max-w-[320px] flex-col gap-2.5 rounded-card p-4 text-white shadow-lg transition-transform duration-150 ease-soft active:scale-[0.98]"
              style={{ background: GRADIENTE_STIL_CARD.standard }}
            >
              <span className="text-[13px] text-white/80">
                {cont.nume ? `${cont.nume} LIBRA` : "Cont LIBRA"}
              </span>
              <span className="tabular whitespace-nowrap text-[13px] tracking-[0.02em]">
                {formateazaIban(cont.iban)}
                {cont.valuta ? <span className="ml-2 text-[11px] text-white/80">{cont.valuta}</span> : null}
              </span>
              <span className="flex items-center justify-center rounded-field bg-white/15 px-3 py-2 text-[13px] font-medium">
                Transfer nou
              </span>
            </a>
          ))}
        </div>
      ) : null}

      {!alMeu && actiuneRapida && ACTIUNI_SIMPLE[actiuneRapida.tip] ? (
        (() => {
          const { eticheta, icona: Icona } = ACTIUNI_SIMPLE[actiuneRapida.tip];
          return (
            <div className="flex w-full justify-center">
              <a
                href={actiuneRapida.url}
                className="flex items-center gap-2 rounded-field bg-primary-600 px-4 py-2.5 text-[13px] font-medium text-white shadow-lg transition-transform duration-150 ease-soft active:scale-[0.98] hover:bg-primary-700"
              >
                <Icona size={16} strokeWidth={1.75} aria-hidden />
                {eticheta}
                <ArrowRight size={14} strokeWidth={1.75} aria-hidden />
              </a>
            </div>
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
