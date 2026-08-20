"use client";

import { Camera, X } from "lucide-react";
import { useState } from "react";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { useCameraCapture } from "@/lib/camera";
import { pregatesteAvatar } from "@/lib/imagine";

/**
 * Login biometric: doar camera (fara upload din galerie, ca la selfie-ul de
 * la inregistrare) — o poza statica ar submina scopul. Captura e trimisa
 * direct la confirmare, spre deosebire de SelfieCapture din inregistrare
 * (acolo userul o pastreaza pe cont, aici doar dovedeste identitatea o data).
 */
export function FaceLoginCapture({
  onCaptura,
  onRenunta,
  seTrimite,
}: {
  onCaptura: (fisier: File) => void;
  onRenunta: () => void;
  seTrimite: boolean;
}) {
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
      onCaptura(fisier);
    } catch {
      setEroare("Nu am putut procesa poza. Încearcă din nou.");
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-ink">Confirmă cu fața</h2>
          <p className="mt-1 text-[13px] leading-[19px] text-ink-soft">
            Privește direct spre cameră, într-un loc bine luminat.
          </p>
        </div>
        <button
          type="button"
          onClick={onRenunta}
          aria-label="Renunță"
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-ink-faint hover:bg-primary-50 hover:text-primary-700"
        >
          <X size={18} strokeWidth={1.75} aria-hidden />
        </button>
      </div>

      {eroare ? <Banda ton="eroare">{eroare}</Banda> : null}

      {camera.pornita ? (
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
            className="w-full"
            onClick={fotografiaza}
            loading={seTrimite}
            iconaStanga={<Camera size={18} strokeWidth={1.75} aria-hidden />}
          >
            {seTrimite ? "Se verifica…" : "Fotografiază"}
          </Button>
        </>
      ) : (
        <div className="flex flex-col items-center gap-4">
          <div className="h-44 w-44 rounded-full border border-dashed border-line" />
          <Button
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
