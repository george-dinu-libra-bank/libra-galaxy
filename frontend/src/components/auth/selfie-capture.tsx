"use client";

import { Camera, RotateCcw } from "lucide-react";
import { useState } from "react";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { useCameraCapture } from "@/lib/camera";
import { pregatesteAvatar } from "@/lib/imagine";

/**
 * Al doilea pas al inregistrarii: un selfie facut pe loc, comparat de
 * DeepFace cu poza de pe buletin. Special doar cu camera (fara incarcare de
 * fisier) — o poza aleasa din galerie ar submina scopul verificarii "live",
 * desi DeepFace insusi nu detecteaza spoofing (limitare cunoscuta).
 */
export function SelfieCapture({ onFinalizat }: { onFinalizat: (file: File) => void }) {
  const [previzualizare, setPrevizualizare] = useState<string | null>(null);
  const [poza, setPoza] = useState<File | null>(null);
  const [eroare, setEroare] = useState<string | null>(null);
  const camera = useCameraCapture({ facingMode: "user", oglindeste: true });

  async function fotografiaza() {
    setEroare(null);
    const brut = await camera.fotografiaza();

    if (!brut) {
      setEroare("Nu am putut face poza. Încearcă din nou.");
      return;
    }

    try {
      const fisier = await pregatesteAvatar(brut);
      setPoza(fisier);
      setPrevizualizare(URL.createObjectURL(fisier));
    } catch {
      setEroare("Nu am putut procesa poza. Încearcă din nou.");
    }
  }

  function reia() {
    if (previzualizare) URL.revokeObjectURL(previzualizare);
    setPoza(null);
    setPrevizualizare(null);
    setEroare(null);
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h2 className="text-lg font-semibold text-ink">Un selfie, ca sa te recunoaștem</h2>
        <p className="mt-1 text-[13px] leading-[19px] text-ink-soft">
          Comparăm fata din selfie cu poza de pe buletin. Privește direct spre cameră, într-un loc bine luminat.
        </p>
      </div>

      {eroare ? <Banda ton="eroare">{eroare}</Banda> : null}

      {poza && previzualizare ? (
        <>
          <div className="mx-auto h-44 w-44 animate-pop overflow-hidden rounded-full border border-line shadow-md">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={previzualizare} alt="Selfie" className="h-full w-full object-cover" />
          </div>

          <div className="flex gap-2">
            <Button
              varianta="secondary"
              className="flex-1"
              onClick={reia}
              iconaStanga={<RotateCcw size={18} strokeWidth={1.75} aria-hidden />}
            >
              Reia poza
            </Button>
            <Button className="flex-1" onClick={() => { if (poza) onFinalizat(poza); }}>
              Continua
            </Button>
          </div>
        </>
      ) : camera.pornita ? (
        <>
          <div className="mx-auto h-44 w-44 overflow-hidden rounded-full bg-ink shadow-md">
            <video
              ref={camera.videoRef}
              playsInline
              muted
              className="h-full w-full -scale-x-100 object-cover"
            />
          </div>

          {camera.eroare ? <Banda ton="eroare">{camera.eroare}</Banda> : null}

          <div className="flex gap-2">
            <Button varianta="secondary" className="flex-1" onClick={camera.opreste}>
              Renunță
            </Button>
            <Button
              className="flex-1"
              onClick={fotografiaza}
              iconaStanga={<Camera size={18} strokeWidth={1.75} aria-hidden />}
            >
              Fotografiază
            </Button>
          </div>
        </>
      ) : (
        <div className="flex flex-col items-center gap-4">
          <div className="h-44 w-44 rounded-full border border-dashed border-line" />
          <Button
            varianta="secondary"
            className="w-full"
            onClick={camera.porneste}
            iconaStanga={<Camera size={18} strokeWidth={1.75} aria-hidden />}
          >
            Pornește camera
          </Button>
        </div>
      )}
    </div>
  );
}
