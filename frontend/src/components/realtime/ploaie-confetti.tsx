"use client";

import { useEffect, useRef, useState } from "react";
import { motion, useReducedMotion } from "motion/react";

/** Cate bucati cad. Peste ~60 incepe sa se simta pe telefoanele slabe. */
const BUCATI = 44;

/** Paleta Libra (globals.css). Scrisa in clar: motion animeaza valori, nu clase. */
const CULORI = [
  "#12b981", // success — culoarea banilor primiti
  "#4c86f5", // primary-500
  "#2f6fed", // primary-600
  "#93b4fb", // primary-300
  "#f5a524", // warning, pentru contrast cald
];

type Bucata = {
  stanga: number;
  culoare: string;
  intarziere: number;
  durata: number;
  rotatie: number;
  driftX: number;
  latime: number;
  inaltime: number;
};

function creeazaBucati(): Bucata[] {
  return Array.from({ length: BUCATI }, () => ({
    stanga: Math.random() * 100,
    culoare: CULORI[Math.floor(Math.random() * CULORI.length)],
    intarziere: Math.random() * 0.55,
    durata: 2 + Math.random() * 1.4,
    rotatie: 240 + Math.random() * 540,
    // Un pic de derapaj lateral, ca sa nu para ca toate cad pe sina.
    driftX: (Math.random() - 0.5) * 120,
    latime: 6 + Math.random() * 4,
    inaltime: 9 + Math.random() * 6,
  }));
}

/**
 * Ploaie scurta de confetti peste tot ecranul, de sus in jos, la incasare.
 *
 * Se monteaza cu o cheie noua la fiecare incasare si se demonteaza singura prin
 * `laFinal` — nu ramane nimic in DOM intre notificari. Nu prinde clicuri
 * (pointer-events-none), deci nu blocheaza interfata de dedesubt.
 */
export function PloaieConfetti({ laFinal }: { laFinal: () => void }) {
  const fataMiscare = useReducedMotion();

  // Valorile aleatoare se fixeaza la montare: altfel fiecare re-randare ar muta
  // bucatile in alta parte in mijlocul caderii.
  const [bucati] = useState(creeazaBucati);

  // Cea mai lunga bucata decide cand s-a terminat tot.
  const ultima = bucati.reduce((a, b) =>
    a.intarziere + a.durata > b.intarziere + b.durata ? a : b,
  );

  // `laFinal` vine ca arrow inline din parinte, deci are alta identitate la
  // fiecare randare; tinut in ref, nu reporneste cronometrul de mai jos.
  const laFinalRef = useRef(laFinal);
  laFinalRef.current = laFinal;

  useEffect(() => {
    // Fara miscare: nicio ploaie, dar parintele tot trebuie sa-si stinga starea.
    if (fataMiscare) {
      laFinalRef.current();
      return;
    }

    // Plasa de siguranta: intr-un tab de fundal browserul incetineste rAF, deci
    // onAnimationComplete poate sa nu mai vina niciodata, iar stratul ar ramane
    // montat la nesfarsit. Il taiem oricum, cu putin peste durata reala.
    const cronometru = setTimeout(
      () => laFinalRef.current(),
      (ultima.intarziere + ultima.durata) * 1000 + 1500,
    );

    return () => clearTimeout(cronometru);
  }, [fataMiscare, ultima.intarziere, ultima.durata]);

  if (fataMiscare) return null;

  return (
    <div
      aria-hidden
      className="pointer-events-none fixed inset-0 z-[60] overflow-hidden"
    >
      {bucati.map((bucata, i) => (
        <motion.span
          key={i}
          // Caderea merge pe translateY, nu pe `top`: altfel 44 de noduri ar
          // recalcula layout-ul la fiecare cadru. Transformarile stau pe GPU.
          initial={{ y: "-8vh", x: 0, rotate: 0, opacity: 0 }}
          animate={{
            y: "108vh",
            x: bucata.driftX,
            rotate: bucata.rotatie,
            opacity: [0, 1, 1, 0],
          }}
          transition={{
            duration: bucata.durata,
            delay: bucata.intarziere,
            ease: "linear",
            // Bucata apare si dispare la capete, dar cade uniform.
            opacity: {
              duration: bucata.durata,
              delay: bucata.intarziere,
              times: [0, 0.08, 0.82, 1],
            },
          }}
          onAnimationComplete={bucata === ultima ? laFinal : undefined}
          style={{
            left: `${bucata.stanga}%`,
            top: 0,
            width: bucata.latime,
            height: bucata.inaltime,
            backgroundColor: bucata.culoare,
          }}
          className="absolute rounded-[2px]"
        />
      ))}
    </div>
  );
}
