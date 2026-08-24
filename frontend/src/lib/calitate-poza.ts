"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Indiciu de lumina calculat direct pe fluxul camerei, inainte de captura.
 *
 * Verificarea serioasa e in backend (/api/identity/check-photo: detectie de
 * fata, blur, contrast) si nu poate rula pe fiecare cadru. Asta e complementul
 * ei ieftin: singurul lucru pe care omul il poate corecta *in timp ce se uita
 * la ecran* e lumina, iar pentru asta ajunge media luminantei. Ii spunem sa
 * aprinda becul inainte sa apese Fotografiaza, nu dupa.
 *
 * Pragurile sunt intentionat mai blande decat cele din backend
 * (CALITATE_LUMA_MIN/MAX): asta e un indiciu, nu o poarta, si un avertisment
 * care apare si dispare la fiecare miscare ar fi mai enervant decat util.
 */
const LUMA_MIN = 45;
const LUMA_MAX = 215;

/** Destul cat sa se simta imediat, rar cat sa nu clipeasca mesajul pe ecran. */
const INTERVAL_MS = 700;

/** Panza minuscula: media luminantei nu are nevoie de rezolutie, iar 32x32 costa practic zero. */
const LATURA_ESANTION = 32;

export function useIndiciuLumina(
  videoRef: React.RefObject<HTMLVideoElement | null>,
  activ: boolean,
): string | null {
  const [indiciu, setIndiciu] = useState<string | null>(null);
  // O singura panza refolosita: una noua la fiecare tick ar produce gunoi
  // constant cat sta camera pornita.
  const panzaRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    if (!activ) {
      setIndiciu(null);
      return;
    }

    function masoara() {
      const video = videoRef.current;
      if (!video?.videoWidth) return;

      panzaRef.current ??= document.createElement("canvas");
      const panza = panzaRef.current;
      panza.width = panza.height = LATURA_ESANTION;

      const ctx = panza.getContext("2d", { willReadFrequently: true });
      if (!ctx) return;

      ctx.drawImage(video, 0, 0, LATURA_ESANTION, LATURA_ESANTION);

      let date: Uint8ClampedArray;
      try {
        date = ctx.getImageData(0, 0, LATURA_ESANTION, LATURA_ESANTION).data;
      } catch {
        // Canvas "murdarit" de un flux dintr-o alta origine — n-avem ce citi.
        return;
      }

      let suma = 0;
      for (let i = 0; i < date.length; i += 4) {
        // Rec.709, ca in backend (infrastructure/calitate_poza.py).
        suma += 0.2126 * date[i] + 0.7152 * date[i + 1] + 0.0722 * date[i + 2];
      }
      const medie = suma / (date.length / 4);

      if (medie < LUMA_MIN) setIndiciu("E cam întuneric — caută o lumină sau apropie-te de o fereastră.");
      else if (medie > LUMA_MAX) setIndiciu("E prea multă lumină. Evită să ai becul sau soarele în spate.");
      else setIndiciu(null);
    }

    masoara();
    const cronometru = window.setInterval(masoara, INTERVAL_MS);
    return () => window.clearInterval(cronometru);
  }, [activ, videoRef]);

  return indiciu;
}
