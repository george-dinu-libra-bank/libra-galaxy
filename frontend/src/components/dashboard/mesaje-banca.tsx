"use client";

import { useTransition } from "react";
import { AlertTriangle, Check, Info, LifeBuoy, Lock, MessageCircle, Unlock } from "lucide-react";
import { cn } from "@/lib/utils";
import { marcheazaCitita } from "@/lib/actions/notificari";
import type { Notificare } from "@/lib/data/notificari";
import Link from "next/link";
import { dataLunga } from "@/lib/momente";
import {
  idCerereDinNotificare,
  idInvestigatieDinNotificare,
  textFaraMarcaj,
} from "@/lib/notificari-credit";

/**
 * Ce intrebare se scrie in asistent cand omul apasa "Intreaba asistentul".
 *
 * Se pre-completeaza, nu se trimite: omul o poate schimba sau sterge inainte de
 * a apasa. Un mesaj trimis in locul lui ar fi o conversatie pe care n-a
 * inceput-o el.
 */
const INTREBARI: Record<string, string> = {
  blocare: "De ce mi-a fost blocat contul și ce trebuie să fac ca să-l deblochez?",
  deblocare: "Contul meu a fost deblocat — ce s-a întâmplat și ce urmează?",
  atentionare: "Am primit o atenționare de la bancă. Poți să-mi explici ce înseamnă?",
  info: "Am primit un mesaj de la bancă. Poți să-mi explici ce înseamnă?",
};

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

  const idCerere = idCerereDinNotificare(notificare.mesaj);
  const idInvestigatie = idInvestigatieDinNotificare(notificare.mesaj);
  // Cand mesajul are deja un loc al lui, acolo se duce omul. Un al doilea drum
  // (asistentul) i-ar imparti atentia intre doua raspunsuri — iar la o
  // investigatie l-ar trimite sa intrebe un model despre ceva ce banca tocmai
  // l-a intrebat pe el, direct.
  const areLocPropriu = idCerere !== null || idInvestigatie !== null;

  return (
    <article className={cn("rounded-card border p-4", stil.chenar, stil.fundal)}>
      <div className="flex items-start gap-3">
        <Icoana size={18} strokeWidth={1.75} className={cn("mt-0.5 shrink-0", stil.ton)} aria-hidden />

        <div className="min-w-0 flex-1">
          <h3 className="text-[14px] font-semibold text-ink">{notificare.titlu}</h3>
          <p className="mt-1 whitespace-pre-line text-[13px] leading-[19px] text-ink-soft">
            {/* Fara curatare, mesajele de credit i-ar arata clientului marcajul
                tehnic de la final in clar. */}
            {textFaraMarcaj(notificare.mesaj)}
          </p>
          {idCerere ? (
            <Link
              href={`/credite?discutie=${idCerere}`}
              className="mt-2 inline-block text-[12.5px] font-semibold text-primary-600 hover:underline"
            >
              Deschide discutia
            </Link>
          ) : null}
          {idInvestigatie ? (
            <Link
              href={`/investigatii/${idInvestigatie}`}
              className="mt-2 inline-block text-[12.5px] font-semibold text-primary-600 hover:underline"
            >
              Vezi mesajul băncii
            </Link>
          ) : null}
          <p className="mt-2 text-[12px] text-ink-faint">
            {dataLunga(notificare.creat_la)}
          </p>

          {areLocPropriu ? null : (
            <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2">
              <Link
                href={`/asistent?nou=1&intrebare=${encodeURIComponent(
                  INTREBARI[notificare.tip] ?? INTREBARI.info,
                )}`}
                className="inline-flex items-center gap-1.5 text-[13px] font-semibold text-primary-600 hover:underline"
              >
                <MessageCircle size={15} strokeWidth={1.75} aria-hidden />
                Întreabă asistentul
              </Link>

              {/* A doua cale, care nu depinde de nimeni: cine vrea sa scrie
                  direct nu trebuie sa treaca printr-o conversatie. */}
              <Link
                href={`/sesizari?subiect=${encodeURIComponent(notificare.titlu)}`}
                className="inline-flex items-center gap-1.5 text-[13px] font-semibold text-ink-soft hover:underline"
              >
                <LifeBuoy size={15} strokeWidth={1.75} aria-hidden />
                Scrie băncii
              </Link>
            </div>
          )}
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
