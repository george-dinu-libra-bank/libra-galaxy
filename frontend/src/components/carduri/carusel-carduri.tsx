"use client";

import { useEffect } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { FataCard } from "@/components/carduri/fata-card";
import { useCaruselCarduri } from "@/hooks/use-carusel-carduri";
import type { DateSensibileCard } from "@/lib/actions/carduri";
import type { CardAfisat } from "@/lib/data/carduri";
import { ETICHETE_STIL_CARD, INEL_FOCUS_CARD } from "@/lib/stil-card";
import { cn, formateazaSuma } from "@/lib/utils";

/**
 * Numele accesibil al unui card, intr-o singura propozitie.
 *
 * Fara el, un cititor de ecran insira tot ce scrie pe card, in ordinea in care e
 * desenat: „Galaxy Bank Standard 4821 punct punct punct 12 slash 29". Corect ca
 * text, inutil ca informatie — omul nu afla care card e, si nu afla deloc ca e
 * blocat, fiindca lacatul e o iconita fara text.
 *
 * Contul si soldul intra tot aici, desi nu mai sunt scrise pe card: la ochi se
 * citesc din panoul de sub carusel, dar un cititor de ecran care trece prin
 * carduri unul cate unul n-ar ajunge la panou decat la sfarsit.
 */
function etichetaCard(card: CardAfisat, intors: boolean): string {
  const bucati = [
    card.tip === "virtual" ? "Card virtual" : `Card ${ETICHETE_STIL_CARD[card.stil]}`,
    `terminat în ${card.numarMascat.slice(-4)}`,
    card.numeCont ? `contul ${card.numeCont}` : "fără cont",
    formateazaSuma(card.sold, card.valuta),
  ];

  if (card.blocatDeBanca) bucati.push("blocat de bancă");
  else if (card.blocat) bucati.push("blocat de tine");

  bucati.push(intors ? "Întoarce cardul pe față" : "Întoarce cardul pe spate");

  return bucati.join(", ");
}

/**
 * Caruselul de carduri: unul in mijloc, restul rotite pe laturi.
 *
 * De ce nu mai e o lista verticala de carduri mari: pe ecran lat cardul se
 * intindea pe toata latimea containerului si ajungea sa fie cel mai mare obiect
 * din aplicatie, desi e doar unul dintre mai multe. Aici latimea e plafonata, iar
 * ecranul lat aduce mai multe carduri in cadru, nu unul mai mare.
 *
 * Apasarea cardului il INTOARCE, si atat — in ambele sensuri, oricand, fara
 * consecinte. Inainte deschidea un drawer cu detalii, si cardul devenise un
 * buton care ducea in alta parte, desi lucrul pe care omul vrea sa-l vada e
 * chiar pe el. Detaliile stau acum permanent in panoul de dedesubt
 * (`panou-card.tsx`), iar numarul complet si CCV-ul apar pe spatele cardului
 * dupa confirmarea ceruta de butonul din acelasi panou.
 *
 * Un card de pe lateral nu se intoarce la prima apasare: prima apasare il aduce
 * in centru. Altfel ar trebui sa nimeresti un card rotit si pe jumatate iesit
 * din cadru, iar `scroll-snap` ti l-ar muta de sub deget in aceeasi clipa.
 */
export function CaruselCarduri({
  carduri,
  posesor,
  intorsId,
  onIntoarce,
  onActivChange,
  dateSensibile,
}: {
  carduri: CardAfisat[];
  posesor?: string | null;
  /** Cardul intors pe spate acum, daca e vreunul. */
  intorsId: string | null;
  onIntoarce: (card: CardAfisat) => void;
  /** Anunta ce card a ajuns in centru, ca panoul de dedesubt sa-l urmeze. */
  onActivChange: (index: number) => void;
  /** Numarul complet si CCV-ul, daca au fost dezvaluite pentru cardul intors. */
  dateSensibile: DateSensibileCard | null;
}) {
  const { pista, activ, centreaza, laDerulare } = useCaruselCarduri(carduri.length);

  useEffect(() => {
    onActivChange(activ);
  }, [activ, onActivChange]);

  return (
    <div>
      <ul
        ref={pista}
        onScroll={laDerulare}
        onKeyDown={(e) => {
          if (e.key === "ArrowRight") {
            e.preventDefault();
            centreaza(Math.min(activ + 1, carduri.length - 1));
          } else if (e.key === "ArrowLeft") {
            e.preventDefault();
            centreaza(Math.max(activ - 1, 0));
          }
        }}
        // `--latime-card` tine latimea intr-un singur loc: o folosesc si
        // cardurile, si captuseala pistei, care trebuie sa fie exact jumatatea
        // ecranului minus jumatate de card, ca primul si ultimul card sa poata
        // ajunge in centru.
        style={{ "--latime-card": "clamp(232px, 68vw, 292px)" } as React.CSSProperties}
        className={cn(
          "relative flex list-none snap-x snap-mandatory gap-4 overflow-x-auto",
          "px-[calc(50%-var(--latime-card)/2)] py-10",
          // Perspectiva sta pe pista, nu pe carduri: asa toate cardurile sunt
          // vazute din acelasi punct — cel din mijlocul ecranului — si se
          // aseaza in cerc in jurul lui. Cu perspectiva pe fiecare card in
          // parte, fiecare ar avea propriul punct de fuga si ar arata rotite
          // aiurea, nu asezate.
          //
          // `preserve-3d` NU se pune aici, desi ar parea locul lui: un element
          // cu `overflow` diferit de `visible` il primeste fortat inapoi pe
          // `flat`, deci ar fi o clasa care nu face nimic. Nici nu e nevoie de
          // el — adancimea dinauntrul cardului are propriul strat 3D, in
          // `fata-card.tsx`.
          "[perspective:1100px]",
          // Bara de derulare taiata: sub carduri ar fi singurul element de
          // crom din pagina. Navigarea ramane prin deget, sageti si taste.
          "[-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden",
        )}
      >
        {carduri.map((card, i) => {
          const inCentru = i === activ;
          const intors = intorsId === card.id;
          const dezvaluit = intors && Boolean(dateSensibile);

          return (
            // `<li>` e tinta de scroll-snap si ramane NETRANSFORMAT: aria dupa
            // care browserul alege unde sa se opreasca derularea e border-box-ul
            // transformat, deci o transformare scrisa aici la fiecare cadru ar
            // muta chiar tinta spre care se deruleaza. Miscarea sta pe invelisul
            // de dedesubt (vezi antetul din use-carusel-carduri.ts).
            //
            // Fara `style` si fara clasa de tranzitie pe invelis: transformarea
            // o scrie hook-ul, direct pe nod, la fiecare cadru de derulare. O
            // tranzitie CSS acolo ar reporni de zeci de ori pe secunda si ar
            // tine cardul in urma degetului.
            //
            // `preserve-3d` pe `<li>` nu e decorativ: `perspective` de pe pista
            // se aplica numai COPIILOR DIRECTI. Fara el, invelisul de dedesubt
            // ar fi aplatizat in planul lui `<li>` — `translateZ` n-ar mai face
            // nimic, iar `rotateY` ar turti cardul pe orizontala in loc sa-l
            // roteasca. Aici e permis, spre deosebire de pista, care are
            // `overflow` si e impinsa fortat inapoi pe `flat`.
            <li
              key={card.id}
              className="w-[var(--latime-card)] shrink-0 snap-center [transform-style:preserve-3d]"
            >
              <div>
                <FataCard
                  date={card}
                  posesor={posesor}
                  intoarsa={intors}
                  ccv={intors ? dateSensibile?.ccv : undefined}
                  numarComplet={intors ? dateSensibile?.numar : undefined}
                  // Intoarcerea trece la spatele cardului cat timp datele sunt pe
                  // el, fiindca tinta de mai jos se retrage atunci.
                  onIntoarce={inCentru ? () => onIntoarce(card) : undefined}
                  // Cardurile de pe laturi nu se inclina: sunt deja rotite de
                  // carusel, iar a doua rotatie peste prima arata a defectiune.
                  inert={!inCentru}
                >
                  {/* Tinta care acopera tot cardul: intoarce cardul din centru,
                      aduce in centru un card de pe lateral.

                      Se retrage — `pointer-events-none`, si iese si din arborele
                      de accesibilitate — cat timp numarul si CCV-ul sunt pe
                      spate. Altfel ar sta peste butoanele de copiere de pe card
                      si le-ar manca apasarile, fiindca ea e in afara stratului 3D
                      si se deseneaza mereu deasupra lui. Intoarcerea nu se pierde
                      in rastimpul asta: si-o ia spatele cardului, pe dedesubtul
                      propriului continut (`fata-card.tsx`). */}
                  <button
                    type="button"
                    onClick={() => (inCentru ? onIntoarce(card) : centreaza(i))}
                    {...(dezvaluit ? { tabIndex: -1, "aria-hidden": true } : {})}
                    // Focusul din tastatura aduce cardul in centru. Fara asta,
                    // Tab ar muta focusul pe un card lasat pe jumatate in afara
                    // cadrului, iar `scroll-snap` l-ar trage inapoi imediat.
                    onFocus={() => centreaza(i)}
                    aria-pressed={inCentru ? intors : undefined}
                    aria-label={
                      inCentru
                        ? etichetaCard(card, intors)
                        : `${etichetaCard(card, intors)}. Adu cardul în față.`
                    }
                    className={cn(
                      "absolute inset-0 rounded-card transition-transform duration-150 ease-soft",
                      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset",
                      INEL_FOCUS_CARD[card.stil],
                      inCentru && !dezvaluit && "active:scale-[0.99]",
                      dezvaluit && "pointer-events-none",
                    )}
                  />
                </FataCard>
              </div>
            </li>
          );
        })}
      </ul>

      <div className="mt-1 flex items-center justify-center gap-1 px-6">
        <SageataCarusel
          directie={-1}
          eticheta="Cardul anterior"
          dezactivat={activ === 0}
          onClick={() => centreaza(activ - 1)}
        />

        <div className="flex items-center gap-0.5 px-1">
          {carduri.map((card, i) => (
            <button
              key={card.id}
              type="button"
              onClick={() => centreaza(i)}
              aria-label={`Cardul ${i + 1} din ${carduri.length}`}
              aria-current={i === activ}
              // 6 px la vedere, 44 px la atins — inaltimea si captuseala fac
              // tinta, nu punctul (DESIGN.md #10).
              className="flex h-11 w-5 items-center justify-center rounded-full focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
            >
              <span
                aria-hidden
                className={cn(
                  "block rounded-full transition-all duration-200 ease-soft",
                  i === activ ? "h-1.5 w-4 bg-primary-600" : "h-1.5 w-1.5 bg-line",
                )}
              />
            </button>
          ))}
        </div>

        <SageataCarusel
          directie={1}
          eticheta="Cardul următor"
          dezactivat={activ === carduri.length - 1}
          onClick={() => centreaza(activ + 1)}
        />
      </div>
    </div>
  );
}

function SageataCarusel({
  directie,
  eticheta,
  dezactivat,
  onClick,
}: {
  directie: 1 | -1;
  eticheta: string;
  dezactivat: boolean;
  onClick: () => void;
}) {
  const Icona = directie === 1 ? ChevronRight : ChevronLeft;

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={dezactivat}
      aria-label={eticheta}
      className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-ink-soft transition-colors hover:bg-primary-50 hover:text-primary-700 disabled:opacity-35 disabled:hover:bg-transparent focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
    >
      <Icona size={20} strokeWidth={1.75} aria-hidden />
    </button>
  );
}
