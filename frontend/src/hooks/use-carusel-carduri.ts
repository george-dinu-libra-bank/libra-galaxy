"use client";

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { useMiscareRedusa } from "@/hooks/use-miscare-redusa";

/** Cat se roteste spre centru un card ajuns departe de mijloc. */
const MAXIM_GRADE = 32;
/** Cat de departe in spate ajunge un card de pe lateral, in pixeli. */
const ADANCIME = 120;
/** Cat de repede se aduna efectul pe masura ce cardul se departeaza de centru. */
const PANTA = 1.15;

/**
 * Caruselul rotit de carduri: unul in mijloc, drept si mare, restul pe laturi,
 * rotite spre centru si impinse in adancime.
 *
 * Derularea e a browserului, nu a noastra: pista e un `overflow-x-auto` cu
 * `scroll-snap`, deci degetul, rotita mouse-ului, sagetile si `scrollTo` merg
 * toate din prima si cu inertia platformei. Hook-ul doar MASOARA unde a ajuns
 * derularea si traduce asta in transformari — nu misca nimic de la sine.
 *
 * ---------------------------------------------------------------------------
 * De ce scrie direct in `element.style` in loc sa treaca prin React
 *
 * Prima varianta tinea pozitiile in `useState` si le dadea mai departe ca
 * `style`, iar cardurile aveau si o tranzitie CSS pe `transform`. Doua greseli
 * care se adunau:
 *
 *   1. o redesenare React completa la FIECARE cadru de derulare — reconciliere,
 *      diff, tot — pentru o schimbare care e doar o transformare;
 *   2. mai rau: o tranzitie de 280 ms pe exact proprietatea care se rescria la
 *      fiecare cadru. Tranzitia pornea de la capat de 60 de ori pe secunda, deci
 *      cardul nu ajungea niciodata unde trebuia si ramanea in urma degetului.
 *      Asta era "lag"-ul care se vedea.
 *
 * Acum transformarea se scrie direct pe noduri, in `requestAnimationFrame`, si
 * NU are nicio tranzitie: urmareste derularea cadru cu cadru, adica exact
 * degetul. React afla doar cand se schimba cardul din centru — de cateva ori pe
 * glisare, nu de sute.
 *
 * ---------------------------------------------------------------------------
 * De ce `tanh`
 *
 * Efectul trebuie sa creasca repede langa centru si sa se aplatizeze departe de
 * el, altfel cardurile indepartate ar continua sa se roteasca pana ajung pe
 * muchie. Varianta cu `min`/`max` facea exact asta, dar cu un COT: pana la o
 * latime de card crestea liniar, dupa care se oprea brusc. Cotul se vedea ca o
 * smucitura fix cand cardul urmator intra in cadru. `tanh` da aceeasi
 * aplatizare, dar neted peste tot — nicaieri nu-si schimba panta dintr-odata.
 */
export function useCaruselCarduri(numar: number) {
  const miscareRedusa = useMiscareRedusa();
  const pista = useRef<HTMLUListElement>(null);
  const cadru = useRef<number | null>(null);
  const [activ, setActiv] = useState(0);

  const aseaza = useCallback(() => {
    const el = pista.current;
    if (!el) return;

    const centruPistei = el.scrollLeft + el.clientWidth / 2;
    const copii = Array.from(el.children) as HTMLElement[];

    let celMaiApropiat = 0;
    let minim = Infinity;

    copii.forEach((copil, i) => {
      const centruCardului = copil.offsetLeft + copil.offsetWidth / 2;
      // Distanta pana la centru, masurata in latimi de card: 0 = fix in mijloc,
      // 1 = la o latime de card distanta.
      const p = (centruCardului - centruPistei) / (copil.offsetWidth || 1);
      const departare = Math.abs(p);

      if (departare < minim) {
        minim = departare;
        celMaiApropiat = i;
      }

      const curba = Math.tanh(departare * PANTA);

      if (miscareRedusa) {
        // Marimea si opacitatea raman: sunt stari, nu animatii, si fara ele
        // n-ai cum sa vezi care card e cel selectat.
        copil.style.transform = `scale(${1 - curba * 0.12})`;
      } else {
        // Semnul: un card aflat in dreapta se roteste cu unghi POZITIV, ceea ce
        // in CSS duce muchia lui dinspre centru spre privitor si pe cealalta in
        // spate. Asa cardurile par asezate in cerc in jurul omului, nu lipite
        // pe un perete.
        copil.style.transform =
          `translateZ(${-curba * ADANCIME}px)` +
          ` rotateY(${Math.tanh(p * PANTA) * MAXIM_GRADE}deg)` +
          ` scale(${1 - curba * 0.08})`;
      }

      copil.style.opacity = String(1 - curba * 0.34);
      // Pista are `overflow`, deci browserul o trateaza ca plana si deseneaza
      // copiii in ordinea din DOM — fara asta, cardul din DREAPTA celui central
      // i-ar trece peste colt, desi e mai in spate.
      copil.style.zIndex = String(100 - Math.round(departare * 10));
    });

    setActiv((vechi) => (vechi === celMaiApropiat ? vechi : celMaiApropiat));
  }, [miscareRedusa]);

  const laDerulare = useCallback(() => {
    if (cadru.current !== null) return; // un singur cadru programat odata
    cadru.current = requestAnimationFrame(() => {
      cadru.current = null;
      aseaza();
    });
  }, [aseaza]);

  // Asezarea initiala se face inainte de prima vopsire: altfel toate cardurile
  // apar o clipa drepte si de aceeasi marime, si abia apoi se aseaza — un salt
  // vizibil exact la intrarea in pagina.
  useLayoutEffect(() => {
    const el = pista.current;
    if (el) {
      for (const copil of Array.from(el.children) as HTMLElement[]) {
        copil.style.willChange = "transform, opacity";
      }
    }
    aseaza();
  }, [aseaza, numar]);

  useEffect(() => {
    const el = pista.current;
    if (!el) return;

    // Latimea cardurilor e in `clamp()`, deci se schimba cu fereastra fara sa
    // treaca prin React. Fara observator, transformarile ar ramane cele de la
    // latimea veche dupa o redimensionare.
    const observator = new ResizeObserver(laDerulare);
    observator.observe(el);
    return () => observator.disconnect();
  }, [laDerulare]);

  useEffect(() => {
    return () => {
      if (cadru.current !== null) cancelAnimationFrame(cadru.current);
    };
  }, []);

  const centreaza = useCallback(
    (index: number) => {
      const el = pista.current;
      const copil = el?.children[index] as HTMLElement | undefined;
      if (!el || !copil) return;

      el.scrollTo({
        left: copil.offsetLeft + copil.offsetWidth / 2 - el.clientWidth / 2,
        behavior: miscareRedusa ? "auto" : "smooth",
      });
    },
    [miscareRedusa],
  );

  return { pista, activ, centreaza, laDerulare };
}
