"use client";

import Image from "next/image";
import { useState } from "react";
import { Check, Copy, Lock } from "lucide-react";
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
  onIntoarce,
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
   * CCV-ul, daca a fost deja dezvaluit prin butonul cu confirmare din panou.
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
   * Intoarce cardul inapoi pe fata.
   *
   * Il primeste doar cardul din centru. Cat timp datele sunt pe spate, tinta de
   * atins a caruselului se retrage (vezi `carusel-carduri.tsx`) ca sa lase
   * butoanele de copiere sa primeasca apasarile; spatele isi ia atunci singur
   * intoarcerea, ca sa nu ramana un card din care nu mai poti iesi.
   */
  onIntoarce?: () => void;
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

            Placi identice, esalonate pe Z si tot mai inchise la culoare. Stau
            in acelasi spatiu 3D ca fetele, deci cand cardul se inclina se ivesc
            pe latura dinspre care vine miscarea — exact ca marginea unui card
            adevarat. Nu e un truc de umbra: daca ar fi fost `box-shadow`, ar fi
            ramas lipita de contur la orice unghi.

            Stau INTRE cele doua fete, nu in spatele lor. Prima varianta le
            impingea la Z negativ, sub fata: mergea cat timp cardul statea pe
            fata, dar la intoarcere rotatia de 180° schimba semnul axei Z, iar
            placile — opace si de latimea cardului — ajungeau in fata spatelui
            si il acopereau complet. Se vedea un dreptunghi gol, in culoarea
            celei mai inchise placi, si nimic din ce scrie pe spate.

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
                  // Esalonate strict intre fete: niciuna nu ajunge la ±GROSIME/2,
                  // unde stau fetele, deci nu pot acoperi niciuna din ele.
                  transform: `translateZ(${
                    GROSIME / 2 - ((i + 1) / (PLACI + 1)) * GROSIME
                  }px)`,
                }}
              />
            ))
          : null}

        <Fata
          date={date}
          posesor={posesor}
          miniatura={miniatura}
          z={miniatura ? 0 : GROSIME / 2}
          inchis={inchis}
          oprit={oprit}
          stare={viu}
        />
        <Spate
          date={date}
          posesor={posesor}
          miniatura={miniatura}
          z={miniatura ? 0 : GROSIME / 2}
          inchis={inchis}
          oprit={oprit}
          ccv={ccv}
          numarComplet={numarComplet}
          onIntoarce={onIntoarce}
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

/**
 * Invelisul comun al celor doua fete: aceeasi raza, acelasi fundal, aceeasi
 * stare oprita, si aceeasi ridicare pe Z.
 *
 * `z` e jumatate din grosimea cardului: fata urca spre privitor, spatele — dupa
 * ce s-a rotit cu 180°, deci pe propria lui normala — coboara tot atat in
 * cealalta directie. Asa fiecare fata sta la suprafata muchiei ei, iar placile
 * dintre ele nu pot ajunge in fata vreuneia, in nicio pozitie a cardului.
 * Miniatura primeste 0: acolo nu se deseneaza muchie.
 */
function Invelis({
  stil,
  oprit = false,
  spate = false,
  z = 0,
  children,
}: {
  stil: StilCard;
  oprit?: boolean;
  spate?: boolean;
  z?: number;
  children: React.ReactNode;
}) {
  return (
    <div
      className="absolute inset-0 overflow-hidden rounded-card [backface-visibility:hidden]"
      style={{
        transform: `${spate ? "rotateY(180deg) " : ""}translateZ(${z}px)`,
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
  z,
  stare,
}: {
  date: DateFataCard;
  posesor?: string | null;
  miniatura: boolean;
  inchis: boolean;
  oprit: boolean;
  z: number;
  stare: StareInclinare | null;
}) {
  const tonTare = inchis ? "text-ink" : "text-white";
  const tonSlab = inchis ? "text-ink/70" : "text-white/75";

  return (
    <Invelis stil={date.stil} oprit={oprit} z={z}>
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
  onIntoarce,
  z,
  stare,
}: {
  date: DateFataCard;
  posesor?: string | null;
  miniatura: boolean;
  inchis: boolean;
  oprit: boolean;
  ccv?: string;
  numarComplet?: string;
  onIntoarce?: () => void;
  z: number;
  stare: StareInclinare | null;
}) {
  const tonTare = inchis ? "text-ink" : "text-white";
  const tonSlab = inchis ? "text-ink/70" : "text-white/70";
  const dezvaluit = Boolean(numarComplet);

  return (
    <Invelis stil={date.stil} oprit={oprit} spate z={z}>
      <Lucire stare={stare} inchis={inchis} oglindit />

      {/* Intoarcerea, cand tinta caruselului s-a retras ca sa lase butoanele
          de copiere sa functioneze. Sta SUB continut si e strapunsa de el:
          textul de deasupra are `pointer-events-none`, deci o apasare pe numar
          sau pe banda ajunge tot aici si intoarce cardul. Doar butoanele de
          copiere isi opresc apasarea la ele. */}
      {dezvaluit && onIntoarce ? (
        <button
          type="button"
          onClick={onIntoarce}
          aria-label="Întoarce cardul pe față"
          className="absolute inset-0 rounded-card focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-white/70"
        />
      ) : null}

      <div
        className={cn(
          "relative flex h-full flex-col",
          dezvaluit && onIntoarce && "pointer-events-none",
        )}
      >
        {/* Banda magnetica */}
        <div className={cn("w-full bg-ink/85", miniatura ? "mt-2 h-4" : "mt-4 h-10")} />

        {!miniatura ? (
          <div className="flex min-h-0 flex-1 flex-col px-5 pb-3 pt-3">
            <div className="flex items-center gap-2">
              <p
                className={cn(
                  "tabular text-[16px] tracking-[0.08em]",
                  dezvaluit ? tonTare : tonSlab,
                )}
              >
                {numarComplet ?? date.numarMascat}
              </p>
              {numarComplet ? (
                <ButonCopiere valoare={numarComplet} eticheta="numărul" inchis={inchis} />
              ) : null}
            </div>

            <p className={cn("mt-1.5 truncate text-[11px] uppercase tracking-wide", tonTare)}>
              {posesor ?? "Posesor card"}
            </p>

            {/* Expirarea si CCV-ul stau pe acelasi rand, fiecare cu eticheta
                lui deasupra: asa se citesc ca doua campuri de completat, in
                ordinea in care le cere orice formular de plata. */}
            <div className="mt-auto flex items-end justify-between gap-3">
              <div className="flex items-end gap-5">
                <CampSpate eticheta="Expiră" valoare={date.dataExpirare} ton={tonTare} tonSlab={tonSlab} />
                <CampSpate
                  eticheta="CCV"
                  valoare={ccv ?? "•••"}
                  ton={tonTare}
                  tonSlab={tonSlab}
                  deCopiat={ccv}
                  inchis={inchis}
                />
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
  deCopiat,
  inchis = false,
}: {
  eticheta: string;
  valoare: string;
  /** Valoarea adevarata, cand exista una de copiat. */
  deCopiat?: string;
  inchis?: boolean;
  ton: string;
  tonSlab: string;
}) {
  return (
    <div>
      <p className={cn("text-[8px] uppercase tracking-[0.12em]", tonSlab)}>{eticheta}</p>
      <span className="flex items-center gap-1.5">
        <p className={cn("tabular text-[13px] font-medium", ton)}>{valoare}</p>
        {deCopiat ? (
          <ButonCopiere valoare={deCopiat} eticheta={eticheta.toLowerCase()} inchis={inchis} />
        ) : null}
      </span>
    </div>
  );
}

/**
 * Copiaza o valoare de pe spatele cardului, de langa cifrele ei.
 *
 * Butoanele astea stateau in panoul de sub carusel, langa niste valori scrise a
 * doua oara acolo. Acum numarul si CCV-ul se vad intr-un singur loc — pe card —
 * si se copiaza din acelasi loc, deci nu mai e nevoie ca ochiul sa verifice ca
 * cele doua copii chiar spun acelasi lucru.
 *
 * `pointer-events-auto` il scoate din indiferenta pe care spatele o are cat
 * timp datele sunt afisate: restul suprafetei lasa apasarile sa treaca la
 * butonul de intoarcere de dedesubt, butonul asta si le opreste la el.
 */
function ButonCopiere({
  valoare,
  eticheta,
  inchis,
}: {
  valoare: string;
  eticheta: string;
  inchis: boolean;
}) {
  const [copiat, setCopiat] = useState(false);

  async function copiaza() {
    try {
      await navigator.clipboard.writeText(valoare.replace(/\s+/g, ""));
      setCopiat(true);
      setTimeout(() => setCopiat(false), 1500);
    } catch {
      // clipboard indisponibil (ex. context non-securizat) — nu blocam UI-ul
    }
  }

  return (
    <button
      type="button"
      onClick={copiaza}
      aria-label={copiat ? "Copiat" : `Copiază ${eticheta}`}
      // 24 px vizual, 40 px de tinta prin captuseala negativa — cat incape pe un
      // card de 292 px fara sa impinga cifrele de langa (DESIGN.md #10).
      className={cn(
        "pointer-events-auto -m-2 flex h-6 w-6 shrink-0 items-center justify-center rounded-full p-2",
        "transition-colors focus-visible:outline-none focus-visible:ring-2",
        inchis
          ? "text-ink/65 hover:bg-ink/10 hover:text-ink focus-visible:ring-ink/40"
          : "text-white/75 hover:bg-white/20 hover:text-white focus-visible:ring-white/70",
      )}
    >
      {copiat ? (
        <Check size={13} strokeWidth={2} aria-hidden />
      ) : (
        <Copy size={13} strokeWidth={2} aria-hidden />
      )}
    </button>
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
