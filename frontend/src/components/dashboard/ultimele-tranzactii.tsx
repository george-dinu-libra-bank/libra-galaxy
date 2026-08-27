"use client";

import Link from "next/link";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { ArrowDownLeft, ArrowUpRight } from "lucide-react";
import { AvatarProfil } from "@/components/ui/avatar-profil";
import type { TranzactieAfisata } from "@/lib/data/tranzactii";
import { ETICHETE_STARE } from "@/lib/stare-tranzactie";
import { cn, formateazaSuma } from "@/lib/utils";

/**
 * Rezumatul de pe dashboard: ultimele cateva miscari, cu poza celuilalt
 * participant. Istoricul complet, cu filtre si detalii, ramane pe /istoric.
 *
 * E componenta client doar ca sa poata anima: cand realtime aduce bani,
 * router.refresh() reincarca Server Component-ul parinte si lista soseste aici
 * ca props noi. Randurile fiind cheiate pe id, AnimatePresence vede exact ce a
 * intrat si ce a iesit din primele cinci, si le deschide/inchide in loc sa
 * clipeasca. Datele raman calculate pe server — aici nu se tine nimic in state.
 */
export function UltimeleTranzactii({ tranzactii }: { tranzactii: TranzactieAfisata[] }) {
  const fataMiscare = useReducedMotion();

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
          {/* `initial={false}`: la prima randare a paginii randurile sunt deja
              acolo, nu "sosesc". Animam doar ce se schimba dupa aceea. */}
          <AnimatePresence initial={false}>
            {tranzactii.map((tranzactie, i) => (
              <motion.div
                key={tranzactie.id}
                layout={fataMiscare ? false : "position"}
                initial={fataMiscare ? false : { height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={fataMiscare ? undefined : { height: 0, opacity: 0 }}
                transition={{
                  height: { duration: 0.32, ease: [0.22, 1, 0.36, 1] },
                  opacity: { duration: 0.22 },
                  layout: { duration: 0.32, ease: [0.22, 1, 0.36, 1] },
                }}
                // Inaltimea se animeaza, deci continutul trebuie taiat cat timp
                // randul e mai scund decat textul din el.
                className="overflow-hidden"
              >
                <Rand
                  tranzactie={tranzactie}
                  ultimul={i === tranzactii.length - 1}
                  fataMiscare={fataMiscare ?? false}
                />
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      )}
    </section>
  );
}

function Rand({
  tranzactie,
  ultimul,
  fataMiscare,
}: {
  tranzactie: TranzactieAfisata;
  ultimul: boolean;
  fataMiscare: boolean;
}) {
  const primita = tranzactie.tip === "primita";
  const Sageata = primita ? ArrowDownLeft : ArrowUpRight;

  // Contrapartea lipseste doar daca profilul celuilalt a fost sters intre timp.
  const nume = tranzactie.numeContraparte;

  // Un transfer oprit sau anulat arata altfel decat unul dus la capat: fara
  // asta, dashboardul spune „ai trimis banii" cand ei nu au plecat nicaieri.
  const stare = ETICHETE_STARE[tranzactie.status];
  const anulata = tranzactie.status === "anulata";

  return (
    <motion.div
      // O spalare care se stinge, ca sa se vada care rand tocmai a aparut:
      // verde la incasare, albastru la orice altceva. Culorile sunt scrise in
      // clar pentru ca motion animeaza valori, nu clase Tailwind; sunt aceleasi
      // --color-success / --color-primary-500 din globals.css, cu alfa mic.
      initial={
        fataMiscare
          ? false
          : { backgroundColor: primita ? "rgba(18,185,129,0.14)" : "rgba(76,134,245,0.12)" }
      }
      animate={{ backgroundColor: "rgba(0,0,0,0)" }}
      transition={{ duration: 1.1, ease: "easeOut", delay: 0.18 }}
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
        <span className="flex items-center gap-2 truncate text-[15px] text-ink">
          <span className="truncate">
            {tranzactie.intreConturiProprii ? (
              "Între conturile tale"
            ) : (
              <>
                {primita ? "Primit de la" : anulata ? "Anulat către" : "Trimis către"}{" "}
                <span className="font-semibold">{nume}</span>
              </>
            )}
          </span>
          {stare ? (
            <span
              className={cn(
                "shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium",
                stare.stil,
              )}
            >
              {stare.text}
            </span>
          ) : null}
        </span>
        <span className="block truncate text-[12.5px] text-ink-faint">
          {tranzactie.grup?.directie === "din"
            ? `din grupul ${tranzactie.grup.nume} · `
            : ""}
          {tranzactie.descriere ? `${tranzactie.descriere} · ` : ""}
          {new Date(tranzactie.creatLa).toLocaleDateString("ro-RO", {
            day: "numeric",
            month: "short",
            timeZone: "Europe/Bucharest",
          })}
        </span>
      </span>

      <span
        className={cn(
          "tabular shrink-0 text-[15px] font-semibold",
          // Suma anulata s-a intors in cont, deci nu mai e o iesire de bani:
          // se taie, ca sa nu para ca lipseste din sold.
          anulata ? "text-ink-faint line-through" : primita ? "text-success" : "text-ink",
        )}
      >
        {primita ? "+" : "−"} {formateazaSuma(tranzactie.suma, tranzactie.valuta)}
      </span>
    </motion.div>
  );
}
