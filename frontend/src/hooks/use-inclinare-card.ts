"use client";

import { useCallback, useRef, useState } from "react";
import { useMiscareRedusa } from "@/hooks/use-miscare-redusa";

/** Cat de mult se poate inclina cardul, in grade, pe fiecare axa. */
const MAXIM_GRADE = 15;

/** Cat de mult iese cardul din pagina cand e atins, in pixeli. */
const RIDICARE = 26;

export type StareInclinare = {
  /** Se pune pe elementul care se inclina. */
  transform: string;
  /** Pozitia luminii, ca procent — mutata de aceeasi miscare. */
  lumina: { x: number; y: number };
  /** Cat de vizibila e lumina acum (0 in repaus). */
  intensitate: number;
  /** Umbra de sub card, care se muta invers fata de inclinare. */
  umbra: string;
};

const REPAUS: StareInclinare = {
  transform: "rotateX(0deg) rotateY(0deg) translateZ(0px)",
  lumina: { x: 50, y: 50 },
  intensitate: 0,
  umbra: "0 10px 24px rgba(15, 27, 51, 0.18)",
};

/**
 * Inclinarea cardului dupa deget sau cursor, cu lumina si umbra care se muta
 * odata cu el.
 *
 * Trei lucruri care nu se vad din cod si conteaza:
 *
 * 1. `useMiscareRedusa` opreste TOTUL, nu doar animatia. Cand omul a cerut mai
 *    putina miscare, nu se ataseaza niciun handler si cardul ramane plat —
 *    regula din globals.css taie tranzitiile CSS, dar nu si transformarile
 *    calculate din JavaScript (vezi antetul hook-ului).
 *
 * 2. Plafonul e 15 grade, dublu fata de prima varianta. DESIGN.md #1.4 cere
 *    miscare discreta, iar 15 grade e peste ce inseamna „discret" — a fost
 *    cerut explicit ca 3D-ul sa se vada. Efectul ramane insa legat de deget:
 *    nu porneste singur, nu se repeta, si dispare cand ridici mana. Daca la
 *    vedere pare prea mult, singurul lucru de schimbat e numarul de aici.
 *
 * 3. Inclinarea NU se aplica la focus din tastatura. Cine navigheaza cu Tab
 *    primeste inelul de focus si un card drept — o transformare care apare fara
 *    ca omul sa fi miscat ceva ar fi dezorientanta, nu placuta.
 */
export function useInclinareCard() {
  const miscareRedusa = useMiscareRedusa();
  const [stare, setStare] = useState<StareInclinare>(REPAUS);
  // Cadrul deja programat, ca sa nu recalculam de mai multe ori intre doua
  // redesenari: `pointermove` se declanseaza mult mai des decat 60 Hz.
  const cadru = useRef<number | null>(null);

  const laMiscare = useCallback(
    (e: React.PointerEvent<HTMLElement>) => {
      if (miscareRedusa) return;

      const element = e.currentTarget;
      const zona = element.getBoundingClientRect();
      const x = (e.clientX - zona.left) / zona.width;
      const y = (e.clientY - zona.top) / zona.height;

      if (cadru.current !== null) cancelAnimationFrame(cadru.current);
      cadru.current = requestAnimationFrame(() => {
        const gradeX = (0.5 - y) * 2 * MAXIM_GRADE;
        const gradeY = (x - 0.5) * 2 * MAXIM_GRADE;

        setStare({
          // Degetul in dreapta inclina cardul spre dreapta: y da rotatia pe X,
          // cu semn schimbat, ca miscarea sa urmeze mana, nu sa fuga de ea.
          // `translateZ` ridica tot cardul spre privitor — fara el, inclinarea
          // singura poate fi confundata cu o deformare plata.
          transform: `rotateX(${gradeX}deg) rotateY(${gradeY}deg) translateZ(${RIDICARE}px)`,
          lumina: { x: x * 100, y: y * 100 },
          intensitate: 1,
          // Umbra pleaca in partea opusa inclinarii si se intinde cu cat cardul
          // e mai ridicat. Asta e ce face creierul sa citeasca „obiect ridicat
          // de pe masa" in loc de „dreptunghi desenat stramb".
          umbra: `${-gradeY * 1.6}px ${gradeX * 1.6 + 26}px 44px rgba(15, 27, 51, 0.32)`,
        });
      });
    },
    [miscareRedusa],
  );

  const laIesire = useCallback(() => {
    if (cadru.current !== null) {
      cancelAnimationFrame(cadru.current);
      cadru.current = null;
    }
    setStare(REPAUS);
  }, []);

  return {
    stare,
    activa: !miscareRedusa,
    handlers: miscareRedusa
      ? {}
      : {
          onPointerMove: laMiscare,
          onPointerLeave: laIesire,
          onPointerCancel: laIesire,
        },
  };
}
