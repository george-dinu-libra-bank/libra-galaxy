"use client";

import { useTransition } from "react";
import { AlertTriangle, Check, Info, Lock, Unlock } from "lucide-react";
import { cn } from "@/lib/utils";
import { marcheazaCitita } from "@/lib/actions/notificari";
import type { Notificare } from "@/lib/data/notificari";
import { dataLunga } from "@/lib/momente";

const STIL = {
  blocare: { icoana: Lock, chenar: "border-danger/30", fundal: "bg-danger/5", ton: "text-danger" },
  deblocare: { icoana: Unlock, chenar: "border-success/30", fundal: "bg-success/5", ton: "text-success" },
  atentionare: { icoana: AlertTriangle, chenar: "border-warning/30", fundal: "bg-warning/5", ton: "text-warning" },
  info: { icoana: Info, chenar: "border-line", fundal: "bg-surface", ton: "text-primary-600" },
} as const;

/**
 * Mesajele bancii catre client, pe dashboard.
 *
 * Se afiseaza doar cele necitite: un om caruia i s-a blocat contul trebuie sa
 * vada de ce fara sa caute, dar mesajele vechi nu au ce sa mai ocupe ecranul
 * principal. Marcarea ca citita e o alegere a lui, nu se intampla singura la
 * afisare — altfel un mesaj important ar disparea dintr-o incarcare de pagina.
 */
export function MesajeBanca({ notificari }: { notificari: Notificare[] }) {
  const necitite = notificari.filter((n) => n.citita_la === null);
  if (necitite.length === 0) return null;

  return (
    <section className="flex flex-col gap-3">
      {necitite.map((n) => (
        <Mesaj key={n.id} notificare={n} />
      ))}
    </section>
  );
}

function Mesaj({ notificare }: { notificare: Notificare }) {
  const [seTrimite, startTransition] = useTransition();
  const stil = STIL[notificare.tip] ?? STIL.info;
  const Icoana = stil.icoana;

  return (
    <article className={cn("rounded-card border p-4", stil.chenar, stil.fundal)}>
      <div className="flex items-start gap-3">
        <Icoana size={18} strokeWidth={1.75} className={cn("mt-0.5 shrink-0", stil.ton)} aria-hidden />

        <div className="min-w-0 flex-1">
          <h3 className="text-[14px] font-semibold text-ink">{notificare.titlu}</h3>
          <p className="mt-1 whitespace-pre-line text-[13px] leading-[19px] text-ink-soft">
            {notificare.mesaj}
          </p>
          <p className="mt-2 text-[12px] text-ink-faint">
            {dataLunga(notificare.creat_la)}
          </p>
        </div>

        <button
          type="button"
          disabled={seTrimite}
          onClick={() => startTransition(() => marcheazaCitita(notificare.id).then(() => {}))}
          className="shrink-0 rounded-full p-1.5 text-ink-faint transition-colors hover:bg-ink/5 hover:text-ink disabled:opacity-50"
          aria-label="Am citit"
        >
          <Check size={16} strokeWidth={2} aria-hidden />
        </button>
      </div>
    </article>
  );
}
