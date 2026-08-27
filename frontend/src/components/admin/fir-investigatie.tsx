import { Bot, Building2, User } from "lucide-react";
import {
  ETICHETA_VALOARE,
  type CampExtras,
  type MesajInvestigatie,
} from "@/lib/data/investigatii";
import { cn } from "@/lib/utils";

/**
 * Firul investigației, așa cum îl vede administratorul.
 *
 * Trei feluri de mesaje, deosebite vizual pentru că nu au aceeași greutate:
 * ce a scris banca, ce a răspuns clientul, și ce a adăugat sistemul (citirea
 * structurată și analiza). Ultimele două sunt marcate ca venind de la un model
 * — administratorul trebuie să știe ce citește, nu să ghicească.
 */

function esteCamp(x: unknown): x is CampExtras {
  if (typeof x !== "object" || x === null) return false;
  const c = x as Record<string, unknown>;
  return typeof c.intrebare === "string" && typeof c.valoare === "string";
}

function campuriDin(structura: Record<string, unknown>): CampExtras[] {
  if (structura.tip !== "extragere" || !Array.isArray(structura.campuri)) return [];
  return structura.campuri.filter(esteCamp);
}

function intrebariDin(structura: Record<string, unknown>): string[] {
  if (!Array.isArray(structura.intrebari)) return [];
  return structura.intrebari.filter((i): i is string => typeof i === "string");
}

const CULOARE_VALOARE: Record<CampExtras["valoare"], string> = {
  da: "bg-success/10 text-success",
  nu: "bg-danger/8 text-danger",
  nu_a_spus: "bg-line/60 text-ink-faint",
};

function Data({ valoare }: { valoare: string }) {
  return (
    <time dateTime={valoare} className="text-[11px] tabular text-ink-faint">
      {new Date(valoare).toLocaleString("ro-RO", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })}
    </time>
  );
}

function Extragere({ campuri }: { campuri: CampExtras[] }) {
  return (
    <ul className="mt-3 flex flex-col gap-2">
      {campuri.map((camp, i) => (
        <li key={`${camp.intrebare}-${i}`} className="flex flex-col gap-1">
          <div className="flex items-start gap-2">
            <span
              className={cn(
                "mt-px shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold",
                CULOARE_VALOARE[camp.valoare],
              )}
            >
              {ETICHETA_VALOARE[camp.valoare]}
            </span>
            <span className="text-[13px] leading-[19px] text-ink">{camp.intrebare}</span>
          </div>
          {camp.citat ? (
            <blockquote className="ml-2 border-l-2 border-line pl-3 text-[12px] italic leading-[18px] text-ink-soft">
              „{camp.citat}”
            </blockquote>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

function Mesaj({ mesaj }: { mesaj: MesajInvestigatie }) {
  const campuri = campuriDin(mesaj.structura);
  const intrebari = intrebariDin(mesaj.structura);

  const antet = {
    banca: { eticheta: "Banca", Icoana: Building2, stil: "text-primary-700" },
    client: { eticheta: "Clientul", Icoana: User, stil: "text-ink" },
    sistem: { eticheta: "Agent", Icoana: Bot, stil: "text-ink-faint" },
  }[mesaj.autor];

  return (
    <li
      className={cn(
        "rounded-card border p-4",
        mesaj.autor === "banca" && "border-primary-100 bg-primary-50/40",
        mesaj.autor === "client" && "border-line bg-surface",
        mesaj.autor === "sistem" &&
          (mesaj.structura.tip === "epuizat"
            ? "border-warning/40 bg-warning/5"
            : "border-dashed border-line bg-canvas/60"),
      )}
    >
      <div className="flex items-center justify-between gap-3">
        <span className={cn("flex items-center gap-1.5 text-[12px] font-semibold", antet.stil)}>
          <antet.Icoana size={14} strokeWidth={1.75} aria-hidden />
          {antet.eticheta}
        </span>
        <Data valoare={mesaj.creat_la} />
      </div>

      {/* Mesajele de la sistem nu repetă textul-titlu al extragerii: lista de
          câmpuri spune deja tot. */}
      {campuri.length === 0 ? (
        <p className="mt-2 whitespace-pre-wrap text-[14px] leading-[21px] text-ink">
          {mesaj.text}
        </p>
      ) : null}

      {campuri.length > 0 ? <Extragere campuri={campuri} /> : null}

      {intrebari.length > 0 ? (
        <p className="mt-3 text-[11px] leading-[16px] text-ink-faint">
          Întrebări puse: {intrebari.length}
        </p>
      ) : null}

      {mesaj.propus_de_agent ? (
        <p className="mt-3 border-t border-line pt-2 text-[11px] leading-[16px] text-ink-faint">
          {mesaj.autor === "banca"
            ? mesaj.structura.reluare === true
              ? "Reluare trimisă automat, fiindcă răspunsul lăsase întrebări deschise. Nu a fost citită de nimeni înainte să plece."
              : mesaj.editat_de_om
                ? "Text propus de un agent, modificat de administrator înainte de trimitere."
                : "Text propus de un agent, trimis de administrator fără modificări."
            : "Scris de un agent, pentru administrator. Clientul nu vede acest text."}
        </p>
      ) : null}
    </li>
  );
}

export function FirInvestigatie({ mesaje }: { mesaje: MesajInvestigatie[] }) {
  if (mesaje.length === 0) {
    return (
      <p className="rounded-card border border-dashed border-line p-5 text-[13px] leading-[19px] text-ink-soft">
        Încă nu s-a scris nimic. Compune mai jos primul mesaj către client.
      </p>
    );
  }

  return (
    <ol className="flex flex-col gap-3">
      {mesaje.map((mesaj) => (
        <Mesaj key={mesaj.id} mesaj={mesaj} />
      ))}
    </ol>
  );
}
