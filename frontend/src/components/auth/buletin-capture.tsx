"use client";

import { IdCard, Camera, ImagePlus, RotateCcw } from "lucide-react";
import { useRef, useState, useTransition } from "react";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { Camp } from "@/components/ui/camp";
import { extrageCnp } from "@/lib/actions/identitate";
import { useCameraCapture } from "@/lib/camera";
import { pregatesteDocument } from "@/lib/imagine";
import { validCnp } from "@/lib/validare";

type Pas = "alegere" | "camera" | "confirmare";

/**
 * Primul pas al inregistrarii: poza buletinului, din care CNP-ul se citeste
 * automat prin OCR (backend/app/infrastructure/ocr.py). Cititul poate gresi
 * o cifra, asa ca userul confirma/corecteaza valoarea inainte sa continue —
 * ramane totusi validat cu aceeasi cifra de control ca la introducerea manuala.
 */
export function BuletinCapture({
  onFinalizat,
  onSarit,
}: {
  onFinalizat: (file: File, cnp: string) => void;
  /** Cand e prezent, userul poate trimite buletinul mai tarziu, din aplicatie. */
  onSarit?: () => void;
}) {
  const [pas, setPas] = useState<Pas>("alegere");
  const [poza, setPoza] = useState<File | null>(null);
  const [previzualizare, setPrevizualizare] = useState<string | null>(null);
  const [cnp, setCnp] = useState("");
  const [eroareCnp, setEroareCnp] = useState<string | null>(null);
  const [eroare, setEroare] = useState<string | null>(null);
  const [seCiteste, startTransition] = useTransition();

  const inputRef = useRef<HTMLInputElement>(null);
  const camera = useCameraCapture({ facingMode: "environment" });

  async function proceseaza(brut: Blob) {
    setEroare(null);

    let fisier: File;
    try {
      fisier = await pregatesteDocument(brut);
    } catch {
      setEroare("Nu am putut citi poza. Încearcă alt fișier.");
      return;
    }

    setPoza(fisier);
    setPrevizualizare(URL.createObjectURL(fisier));
    setPas("confirmare");
    setCnp("");

    startTransition(async () => {
      const trimitere = new FormData();
      trimitere.append("buletin", fisier);

      const rezultat = await extrageCnp(trimitere);

      if (rezultat.eroare) {
        setEroare(rezultat.eroare);
        return;
      }
      if (rezultat.cnp) setCnp(rezultat.cnp);
    });
  }

  async function alegeFisier(eveniment: React.ChangeEvent<HTMLInputElement>) {
    const fisier = eveniment.target.files?.[0];
    eveniment.target.value = "";
    if (fisier) await proceseaza(fisier);
  }

  async function fotografiaza() {
    const brut = await camera.fotografiaza();
    if (!brut) {
      setEroare("Nu am putut face poza. Încearcă din nou.");
      return;
    }
    await proceseaza(brut);
  }

  function reia() {
    if (previzualizare) URL.revokeObjectURL(previzualizare);
    setPoza(null);
    setPrevizualizare(null);
    setCnp("");
    setEroareCnp(null);
    setEroare(null);
    setPas("alegere");
  }

  function continua() {
    const eroareValidare = validCnp(cnp);
    setEroareCnp(eroareValidare);
    if (eroareValidare || !poza) return;

    onFinalizat(poza, cnp);
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h2 className="text-lg font-semibold text-ink">Poza buletinului</h2>
        <p className="mt-1 text-[13px] leading-[19px] text-ink-soft">
          Fotografiaza fata buletinului cu CNP-ul. Citim automat CNP-ul din
          poza — il poti corecta daca am greșit o cifra.
        </p>
      </div>

      {eroare ? <Banda ton="eroare">{eroare}</Banda> : null}

      {pas === "camera" ? (
        <>
          <div className="aspect-[8/5] w-full overflow-hidden rounded-card bg-ink shadow-md">
            <video
              ref={camera.videoRef}
              playsInline
              muted
              className="h-full w-full object-cover"
            />
          </div>

          {camera.eroare ? <Banda ton="eroare">{camera.eroare}</Banda> : null}

          <div className="flex gap-2">
            <Button varianta="secondary" className="flex-1" onClick={() => { camera.opreste(); setPas("alegere"); }}>
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
      ) : pas === "confirmare" ? (
        <>
          {previzualizare ? (
            <div className="aspect-[8/5] w-full animate-pop overflow-hidden rounded-card border border-line shadow-md">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={previzualizare} alt="Poza buletinului" className="h-full w-full object-cover" />
            </div>
          ) : null}

          <Camp
            eticheta="CNP"
            icoana={IdCard}
            inputMode="numeric"
            maxLength={13}
            autoComplete="off"
            placeholder={seCiteste ? "Se citeste din poza…" : "13 cifre"}
            className="tabular tracking-[0.04em]"
            value={cnp}
            onChange={(e) => { setCnp(e.target.value.replace(/\D/g, "")); setEroareCnp(null); }}
            onBlur={() => setEroareCnp(validCnp(cnp))}
            eroare={eroareCnp}
            disabled={seCiteste}
            ajutor={seCiteste ? undefined : "Verifica sa corespunda cu buletinul."}
          />

          <div className="flex gap-2">
            <Button
              varianta="secondary"
              className="flex-1"
              onClick={reia}
              iconaStanga={<RotateCcw size={18} strokeWidth={1.75} aria-hidden />}
            >
              Reia poza
            </Button>
            <Button className="flex-1" onClick={continua} loading={seCiteste} disabled={!cnp}>
              Continua
            </Button>
          </div>
        </>
      ) : (
        <div className="flex flex-col gap-2">
          <Button
            varianta="secondary"
            className="w-full"
            onClick={() => inputRef.current?.click()}
            iconaStanga={<ImagePlus size={18} strokeWidth={1.75} aria-hidden />}
          >
            Încarcă o poză
          </Button>

          <Button
            varianta="secondary"
            className="w-full"
            onClick={async () => { setPas("camera"); await camera.porneste(); }}
            iconaStanga={<Camera size={18} strokeWidth={1.75} aria-hidden />}
          >
            Fă o poză cu camera
          </Button>

          <input
            ref={inputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            className="sr-only"
            onChange={alegeFisier}
          />

          {onSarit ? (
            <button
              type="button"
              onClick={onSarit}
              className="mt-1 rounded text-center text-[13px] font-semibold text-primary-600 hover:text-primary-700 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
            >
              Trimit buletinul mai târziu
            </button>
          ) : null}
        </div>
      )}
    </div>
  );
}
