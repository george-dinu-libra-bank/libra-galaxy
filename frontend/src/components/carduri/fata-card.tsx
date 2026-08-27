"use client";

import Image from "next/image";
import { Lock } from "lucide-react";
import { useInclinareCard, type StareInclinare } from "@/hooks/use-inclinare-card";
import type { StilCard, TipCard } from "@/lib/data/carduri";
import {
  ETICHETE_STIL_CARD,
  FILTRU_SIGLA_CARD,
  GRADIENT_CIP_CARD,
  GRADIENT_HOLOGRAMA,
  GRADIENTE_STIL_CARD,
  TON_STIL_CARD,
} from "@/lib/stil-card";
import { cn } from "@/lib/utils";

/**
 * Fata unui card bancar — singura definitie a felului in care arata un card.
 *
 * Pana acum forma cardului era scrisa de doua ori: o data in lista reala
 * (`lista-carduri.tsx`) si o data in previzualizarea de la emitere
 * (`adauga-card-drawer.tsx`). Cele doua deviasera deja — previzualizarea era un
 * simplu dreptunghi cu gradient, deci omul alegea tematica fara sa vada ce
 * primeste. Acum e o componenta, cu doua marimi.
 *
 * NU se foloseste in bula asistentului: acolo se deseneaza un CONT (IBAN si
 * buton de transfer), care doar imprumuta acelasi gradient. Un cont nu are cip
 * si nu are numar de card.
 *
 * Ce NU mai scrie pe card: numele contului si soldul. Un card tiparit n-are asa
 * ceva, si pe cardul micsorat din carusel inghesuiau coltul de jos. Amandoua
 * apar sub carusel, unde e loc sa fie citite (`carusel-carduri.tsx`).
 *
 * 3D-ul e in intregime CSS — `perspective` pe invelis, `preserve-3d` pe card,
 * `backface-visibility` pe cele doua fete, si o muchie facuta din placi
 * suprapuse in adancime. Fara biblioteci si fara resurse desenate in alta parte.
 */

export type DateFataCard = {
  stil: StilCard;
  tip: TipCard;
  numarMascat: string;
  dataExpirare: string;
  blocat: boolean;
  blocatDeBanca: boolean;
};

/** Raportul unui card bancar real: 85,6 × 53,98 mm. */
const RAPORT = "1.586 / 1";

/**
 * Grosimea cardului, in pixeli, si din cate placi e facuta.
 *
 * O singura placa impinsa in spate lasa un gol intre ea si fata: la inclinari
 * mari se vede prin cardul „gol pe dinauntru". Mai multe placi apropiate
 * umplu golul si dau o muchie plina, ca la un obiect turnat.
 */
const GROSIME = 16;
const PLACI = 8;

export function FataCard({
  date,
  posesor,
  miniatura = false,
  intoarsa = false,
  ccv,
  numarComplet,
  inert = false,
  className,
  children,
}: {
  date: DateFataCard;
  /** Numele de pe card. Lipsa lui nu lasa un gol: randul dispare cu totul. */
  posesor?: string | null;
  /** Varianta mica, statica — pentru selectorul de tematica. */
  miniatura?: boolean;
  /** Arata spatele (banda magnetica si CCV). */
  intoarsa?: boolean;
  /**
   * CCV-ul, daca a fost deja dezvaluit prin fluxul de confirmare din detalii.
   * Lipsa lui inseamna `•••` — intoarcerea cardului e un gest vizual, nu o
   * portita prin care datele sensibile apar fara confirmare.
   */
  ccv?: string;
  /**
   * Numarul complet, dupa aceeasi confirmare ca `ccv`.
   *
   * Se scrie pe SPATE, nu pe fata, desi pe un card tiparit numarul e in fata:
   * cine intoarce cardul ca sa vada CCV-ul are nevoie si de numar, si a-l pune
   * pe cealalta fata l-ar pune sa intoarca cardul inainte si inapoi ca sa
   * copieze un singur formular.
   */
  numarComplet?: string;
  /**
   * Opreste inclinarea, fara sa schimbe nimic altceva.
   *
   * In carusel o primesc cardurile de pe laturi: ele sunt deja rotite de
   * carusel, iar o a doua rotatie peste ea, dupa deget, arata ca o defectiune.
   * Cardul din centru ramane interactiv.
   */
  inert?: boolean;
  className?: string;
  /**
   * Comenzile puse peste card (deschide detaliile).
   *
   * Stau AICI, inauntrul invelisului cu `perspective`, si nu langa el: altfel
   * degetul plimbat peste buton n-ar mai ajunge la handlerele de inclinare, iar
   * cardul ar ramane teapan exact acolo unde omul il atinge. Raman insa in
   * afara stratului `preserve-3d`, deci nu se rotesc odata cu el.
   */
  children?: React.ReactNode;
}) {
  const { stare, activa, handlers } = useInclinareCard();

  const oprit = date.blocat || date.blocatDeBanca;
  const inchis = TON_STIL_CARD[date.stil] === "inchis";
  const interactiv = !miniatura && !inert;
  const viu = interactiv && activa ? stare : null;

  return (
    <div
      className={cn("relative [perspective:1400px]", className)}
      {...(interactiv ? handlers : {})}
    >
      <div
        className={cn(
          "relative w-full [transform-style:preserve-3d]",
          // Revenirea la drept e mai lenta decat urmarirea degetului, ca sa nu
          // para ca sare inapoi. Sub 300 ms, cum cere DESIGN.md #1.4.
          "transition-transform duration-[280ms] ease-soft",
          "motion-reduce:transition-none",
        )}
        style={{
          aspectRatio: RAPORT,
          transform: `${intoarsa ? "rotateY(180deg)" : ""} ${viu ? viu.transform : ""}`.trim(),
        }}
      >
        {/* Muchia cardului.

            Placi identice, tot mai in spate pe Z si tot mai inchise la culoare.
            Stau in acelasi spatiu 3D ca fetele, deci cand cardul se inclina se
            ivesc pe latura dinspre care vine miscarea — exact ca marginea unui
            card adevarat. Nu e un truc de umbra: daca ar fi fost `box-shadow`,
            ar fi ramas lipita de contur la orice unghi.

            Pe miniatura nu are rost: la 24 px latime, 16 px de adancime ar
            arata ca o eroare de desen, nu ca grosime. */}
        {!miniatura
          ? Array.from({ length: PLACI }, (_, i) => (
              <div
                key={i}
                aria-hidden
                className="absolute inset-0 rounded-card"
                style={{
                  background: GRADIENTE_STIL_CARD[date.stil],
                  // Cu cat placa e mai in spate, cu atat mai putina lumina
                  // ajunge la ea — asa muchia are un degrade, nu o culoare
                  // plata care ar arata ca un chenar desenat.
                  filter: `brightness(${0.72 - (i / PLACI) * 0.34})`,
                  transform: `translateZ(-${((i + 1) / PLACI) * GROSIME}px)`,
                }}
              />
            ))
          : null}

        <Fata
          date={date}
          posesor={posesor}
          miniatura={miniatura}
          inchis={inchis}
          oprit={oprit}
          stare={viu}
        />
        <Spate
          date={date}
          posesor={posesor}
          miniatura={miniatura}
          inchis={inchis}
          oprit={oprit}
          ccv={ccv}
          numarComplet={numarComplet}
          stare={viu}
        />
      </div>

      {/* Umbra de pe „masa".

          Sta sub card, in afara stratului 3D, si se muta invers fata de
          inclinare. E stratul care convinge ochiul ca obiectul e ridicat:
          rotatia singura, fara umbra care sa o urmeze, se citeste ca un desen
          deformat, nu ca un card tinut in mana. */}
      {!miniatura ? (
        <div
          aria-hidden
          className="pointer-events-none absolute inset-x-4 bottom-0 top-4 -z-10 rounded-card transition-[box-shadow] duration-[280ms] ease-soft"
          style={{ boxShadow: viu ? viu.umbra : "0 10px 24px rgba(15, 27, 51, 0.18)" }}
        />
      ) : null}

      {children}
    </div>
  );
}

/** Invelisul comun al celor doua fete: aceeasi raza, acelasi fundal, aceeasi stare oprita. */
function Invelis({
  stil,
  oprit = false,
  spate = false,
  children,
}: {
  stil: StilCard;
  oprit?: boolean;
  spate?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div
      className={cn(
        "absolute inset-0 overflow-hidden rounded-card [backface-visibility:hidden]",
        spate && "[transform:rotateY(180deg)]",
      )}
      style={{
        background: GRADIENTE_STIL_CARD[stil],
        // Cardul oprit se stinge prin desaturare, nu prin `opacity`. Opacitatea
        // ridica fundalul paginii peste text si cobora contrastul sub pragul din
        // DESIGN.md #2.5 — exact pe cardul despre care omul are nevoie sa
        // citeasca cel mai atent.
        filter: oprit ? "grayscale(0.75)" : undefined,
      }}
    >
      {children}
    </div>
  );
}

/**
 * Lucirea care urmeaza degetul. In repaus e invizibila, deci cardul sta
 * linistit pana cand cineva il atinge.
 *
 * Pe spate lumina se oglindeste (`x` devine `100 - x`): fata din spate e rotita
 * cu 180°, deci fara oglindire lumina ar aparea pe latura opusa celei dinspre
 * care vine degetul — adica exact pe unde nu e mana.
 */
function Lucire({
  stare,
  inchis,
  oglindit = false,
}: {
  stare: StareInclinare | null;
  inchis: boolean;
  oglindit?: boolean;
}) {
  const x = stare ? (oglindit ? 100 - stare.lumina.x : stare.lumina.x) : 50;

  return (
    <div
      aria-hidden
      className="pointer-events-none absolute inset-0 transition-opacity duration-[280ms]"
      style={{
        opacity: stare ? stare.intensitate * (inchis ? 0.5 : 0.85) : 0,
        background: stare
          ? `radial-gradient(circle at ${x}% ${stare.lumina.y}%, rgba(255,255,255,0.42), transparent 55%)`
          : undefined,
      }}
    />
  );
}

function Fata({
  date,
  posesor,
  miniatura,
  inchis,
  oprit,
  stare,
}: {
  date: DateFataCard;
  posesor?: string | null;
  miniatura: boolean;
  inchis: boolean;
  oprit: boolean;
  stare: StareInclinare | null;
}) {
  const tonTare = inchis ? "text-ink" : "text-white";
  const tonSlab = inchis ? "text-ink/70" : "text-white/75";

  return (
    <Invelis stil={date.stil} oprit={oprit}>
      <Lucire stare={stare} inchis={inchis} />

      <div
        className={cn(
          "relative flex h-full flex-col justify-between",
          miniatura ? "p-2.5" : "p-5",
        )}
      >
        <div className="flex items-start justify-between gap-2">
          <span className="flex items-center gap-2">
            <Image
              src="/logo.png"
              alt=""
              aria-hidden
              width={miniatura ? 16 : 26}
              height={miniatura ? 16 : 26}
              className="shrink-0"
              style={{ filter: FILTRU_SIGLA_CARD[date.stil] }}
            />
            {!miniatura ? (
              <span className={cn("text-[13px] font-semibold tracking-[-0.01em]", tonTare)}>
                Galaxy Bank
              </span>
            ) : null}
          </span>

          {!miniatura ? (
            <span className={cn("text-[11px] uppercase tracking-wide", tonSlab)}>
              {date.tip === "virtual" ? "Virtual" : ETICHETE_STIL_CARD[date.stil]}
            </span>
          ) : null}
        </div>

        <div className={cn("flex items-center", miniatura ? "gap-1.5" : "gap-3")}>
          <Cip stil={date.stil} miniatura={miniatura} />
          {!miniatura ? <Contactless inchis={inchis} /> : null}
        </div>

        {!miniatura ? (
          <p className={cn("tabular text-[18px] tracking-[0.1em]", tonTare)}>
            {date.numarMascat}
          </p>
        ) : null}

        {!miniatura ? (
          <div className="flex items-end justify-between gap-3">
            <p className={cn("min-w-0 truncate text-[12px] uppercase tracking-wide", tonTare)}>
              {posesor ?? " "}
            </p>
            <div className="shrink-0 text-right">
              <p className={cn("text-[9px] uppercase tracking-wide", tonSlab)}>Expiră</p>
              <p className={cn("tabular text-[13px]", tonTare)}>{date.dataExpirare}</p>
            </div>
          </div>
        ) : null}
      </div>

      {oprit && !miniatura ? (
        <span className="absolute right-4 top-14 flex items-center gap-1 rounded-full bg-ink/70 px-2.5 py-1 text-[11px] font-medium text-white">
          <Lock size={12} strokeWidth={1.75} aria-hidden />
          {date.blocatDeBanca ? "Blocat de bancă" : "Blocat"}
        </span>
      ) : null}
    </Invelis>
  );
}

/**
 * Spatele cardului — toate datele intr-un singur loc.
 *
 * Prima varianta avea doar banda magnetica pe un fundal gol: cine intorcea
 * cardul ajungea la o suprafata pe care nu era nimic de vazut. A doua avea
 * fasia de semnatura, ca pe un card tiparit — corect, dar fasia ocupa
 * jumatate din latime ca sa nu spuna nimic.
 *
 * Acum spatele e ecranul de date: numar, posesor, expirare si CCV, unul sub
 * altul. Asta e tot ce se cere la o plata online, si e adunat pe o singura
 * fata, deci nu mai trebuie intors cardul inainte si inapoi ca sa completezi
 * un formular. Banda magnetica ramane fiindca ea e semnul dupa care ochiul
 * recunoaste, dintr-o privire, ca s-a intors ceva.
 *
 * Aranjamentul e ACELASI si cand datele sunt ascunse: mascatele ocupa exact
 * cate randuri ocupa si cele adevarate. Altfel confirmarea ar muta textul sub
 * degetul omului, exact in clipa in care se uita la el.
 */
function Spate({
  date,
  posesor,
  miniatura,
  inchis,
  oprit,
  ccv,
  numarComplet,
  stare,
}: {
  date: DateFataCard;
  posesor?: string | null;
  miniatura: boolean;
  inchis: boolean;
  oprit: boolean;
  ccv?: string;
  numarComplet?: string;
  stare: StareInclinare | null;
}) {
  const tonTare = inchis ? "text-ink" : "text-white";
  const tonSlab = inchis ? "text-ink/70" : "text-white/70";
  const dezvaluit = Boolean(numarComplet);

  return (
    <Invelis stil={date.stil} oprit={oprit} spate>
      <Lucire stare={stare} inchis={inchis} oglindit />

      <div className="relative flex h-full flex-col">
        {/* Banda magnetica */}
        <div className={cn("w-full bg-ink/85", miniatura ? "mt-2 h-4" : "mt-4 h-10")} />

        {!miniatura ? (
          <div className="flex min-h-0 flex-1 flex-col px-5 pb-3 pt-3">
            <p
              className={cn(
                "tabular text-[16px] tracking-[0.08em]",
                dezvaluit ? tonTare : tonSlab,
              )}
            >
              {numarComplet ?? date.numarMascat}
            </p>

            <p className={cn("mt-1.5 truncate text-[11px] uppercase tracking-wide", tonTare)}>
              {posesor ?? "Posesor card"}
            </p>

            {/* Expirarea si CCV-ul stau pe acelasi rand, fiecare cu eticheta
                lui deasupra: asa se citesc ca doua campuri de completat, in
                ordinea in care le cere orice formular de plata. */}
            <div className="mt-auto flex items-end justify-between gap-3">
              <div className="flex items-end gap-5">
                <CampSpate eticheta="Expiră" valoare={date.dataExpirare} ton={tonTare} tonSlab={tonSlab} />
                <CampSpate eticheta="CCV" valoare={ccv ?? "•••"} ton={tonTare} tonSlab={tonSlab} />
              </div>

              <div className="flex shrink-0 items-center gap-2">
                <Image
                  src="/logo.png"
                  alt=""
                  aria-hidden
                  width={15}
                  height={15}
                  className="shrink-0"
                  style={{ filter: FILTRU_SIGLA_CARD[date.stil] }}
                />
                <Holograma />
              </div>
            </div>
          </div>
        ) : null}
      </div>
    </Invelis>
  );
}

/** Un camp de pe spate: eticheta mica deasupra, valoarea dedesubt. */
function CampSpate({
  eticheta,
  valoare,
  ton,
  tonSlab,
}: {
  eticheta: string;
  valoare: string;
  ton: string;
  tonSlab: string;
}) {
  return (
    <div>
      <p className={cn("text-[8px] uppercase tracking-[0.12em]", tonSlab)}>{eticheta}</p>
      <p className={cn("tabular text-[13px] font-medium", ton)}>{valoare}</p>
    </div>
  );
}

/** Peticul care isi schimba culoarea cu unghiul. */
function Holograma() {
  return (
    <span
      aria-hidden
      className="block h-7 w-7 shrink-0 rounded-[5px] opacity-80 mix-blend-screen"
      style={{ background: GRADIENT_HOLOGRAMA }}
    />
  );
}

function Cip({ stil, miniatura }: { stil: StilCard; miniatura: boolean }) {
  return (
    <span
      aria-hidden
      className={cn(
        "relative block shrink-0 overflow-hidden rounded-[4px]",
        miniatura ? "h-3.5 w-5" : "h-7 w-10",
      )}
      style={{ background: GRADIENT_CIP_CARD[stil] }}
    >
      {/* Contactele cipului: doua linii orizontale si una verticala, ca pe cardurile reale. */}
      <span className="absolute inset-x-1 top-1/3 h-px bg-black/25" />
      <span className="absolute inset-x-1 top-2/3 h-px bg-black/25" />
      <span className="absolute inset-y-1 left-1/2 w-px bg-black/25" />
    </span>
  );
}

function Contactless({ inchis }: { inchis: boolean }) {
  return (
    <svg
      aria-hidden
      viewBox="0 0 24 24"
      className={cn("h-5 w-5", inchis ? "text-ink/70" : "text-white/80")}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
    >
      <path d="M7 8.5a6 6 0 0 1 0 7" />
      <path d="M10.5 6a10 10 0 0 1 0 12" />
      <path d="M14 3.5a14 14 0 0 1 0 17" />
    </svg>
  );
}
