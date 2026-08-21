"use client";

import { Camera, RotateCcw } from "lucide-react";
import { useState } from "react";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { useCameraCapture } from "@/lib/camera";
import { pregatesteAvatar } from "@/lib/imagine";

/**
 * Doar camera pentru login biometric (fara upload din galerie, ca la selfie-ul
 * de la inregistrare) — o poza statica ar submina scopul.
 *
 * Traieste pe acelasi ecran cu emailul (vezi LoginForm): nu trimite nimic
 * singura, doar anunta parintele de fiecare data cand poza se schimba
 * (facuta sau reluata) — parintele decide cand si cu ce trimite mai departe.
 */
export function FaceLoginCapture({
  poza,
  onSchimbat,
  disabled,
}: {
  poza: File | null;
  onSchimbat: (fisier: File | null) => void;
  disabled?: boolean;
}) {
  const [previzualizare, setPrevizualizare] = useState<string | null>(null);
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
      setPrevizualizare(URL.createObjectURL(fisier));
      onSchimbat(fisier);
    } catch {
      setEroare("Nu am putut procesa poza. Încearcă din nou.");
    }
  }

  function reia() {
    if (previzualizare) URL.revokeObjectURL(previzualizare);
    setPrevizualizare(null);
    setEroare(null);
    onSchimbat(null);
  }

  return (
    <div className="flex flex-col gap-3">
      {eroare ? <Banda ton="eroare">{eroare}</Banda> : null}

      {poza && previzualizare ? (
        <>
          <div className="mx-auto h-44 w-44 animate-pop overflow-hidden rounded-full border border-line shadow-md">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={previzualizare} alt="Poza ta" className="h-full w-full object-cover" />
          </div>
          <Button
            type="button"
            varianta="secondary"
            className="w-full"
            onClick={reia}
            disabled={disabled}
            iconaStanga={<RotateCcw size={18} strokeWidth={1.75} aria-hidden />}
          >
            Reia poza
          </Button>
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

          <Button
            type="button"
            className="w-full"
            onClick={fotografiaza}
            disabled={disabled}
            iconaStanga={<Camera size={18} strokeWidth={1.75} aria-hidden />}
          >
            Fotografiază
          </Button>
        </>
      ) : (
        <div className="flex flex-col items-center gap-4">
          <div className="h-44 w-44 rounded-full border border-dashed border-line" />
          <Button
            type="button"
            className="w-full"
            onClick={camera.porneste}
            disabled={disabled}
            iconaStanga={<Camera size={18} strokeWidth={1.75} aria-hidden />}
          >
            Pornește camera
          </Button>
        </div>
      )}
    </div>
  );
}
