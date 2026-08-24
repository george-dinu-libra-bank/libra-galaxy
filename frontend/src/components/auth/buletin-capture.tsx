"use client";

import { IdCard, Camera, ImagePlus, RotateCcw } from "lucide-react";
import { useRef, useState, useTransition } from "react";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { Camp } from "@/components/ui/camp";
import { extrageCnp, type ProblemaPoza, verificaCalitatePoza } from "@/lib/actions/identitate";
import { useIndiciuLumina } from "@/lib/calitate-poza";
import { useCameraCapture } from "@/lib/camera";
import { pregatesteDocument } from "@/lib/imagine";
import { validCnp } from "@/lib/validare";

type Pas = "alegere" | "camera" | "confirmare";

/** Vezi selfie-capture.tsx: blocarea e moale, ca sa nu ramana nimeni infundat. */
const INCERCARI_PANA_LA_SCAPARE = 2;

/**
 * Primul pas al inregistrarii: poza buletinului, din care CNP-ul se citeste
 * automat prin OCR (backend/app/infrastructure/ocr.py). Cititul poate gresi
 * o cifra, asa ca userul confirma/corecteaza valoarea inainte sa continue —
 * ramane totusi validat cu aceeasi cifra de control ca la introducerea manuala.
 *
 * In paralel cu OCR-ul, poza trece pe la /api/identity/check-photo, care spune
 * de ce nu s-a putut citi ("e neclara", "se reflecta lumina in buletin") in
 * loc de vagul "Nu am putut citi CNP-ul". Verificarea prinde si cazul in care
 * OCR-ul nimereste totusi cifrele dintr-o poza proasta — care apoi pica la
 * comparatia fetelor, mult mai tarziu si fara nicio explicatie.
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
  const [probleme, setProbleme] = useState<ProblemaPoza[]>([]);
  const [incercariEsuate, setIncercariEsuate] = useState(0);
  const [seCiteste, startTransition] = useTransition();

  const inputRef = useRef<HTMLInputElement>(null);
  // OCR-ul si verificarea de calitate sunt asincrone, iar "Reia poza" ramane
  // apasabil cat tin. Fara contorul asta, raspunsurile pentru poza abandonata
  // ar ateriza peste cea noua — inclusiv un CNP citit de pe alt buletin.
  const generatieRef = useRef(0);
  const camera = useCameraCapture({ facingMode: "environment" });
  const indiciuLumina = useIndiciuLumina(camera.videoRef, camera.pornita);

  const blocat = probleme.some((problema) => problema.blocanta);
  const deAfisat = blocat ? probleme.filter((problema) => problema.blocanta) : probleme;
  const poateSari = blocat && incercariEsuate >= INCERCARI_PANA_LA_SCAPARE;

  async function proceseaza(brut: Blob) {
    setEroare(null);
    setProbleme([]);
    const generatie = ++generatieRef.current;

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

      // In paralel, nu in serie: verificarea de calitate n-are voie sa adauge
      // timp de asteptare peste OCR, care oricum e partea lenta.
      const [rezultat, calitate] = await Promise.all([
        extrageCnp(trimitere),
        verificaCalitatePoza(fisier, "buletin"),
      ]);

      if (generatieRef.current !== generatie) return; // poza a fost reluata intre timp

      setProbleme(calitate.probleme);
      if (!calitate.acceptabila) setIncercariEsuate((numar) => numar + 1);

      // Cand stim exact de ce e proasta poza, nu mai spunem si vagul "nu am
      // putut citi CNP-ul" — e acelasi lucru, spus mai prost.
      if (rezultat.eroare) {
        if (calitate.acceptabila) setEroare(rezultat.eroare);
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
    generatieRef.current += 1;
    if (previzualizare) URL.revokeObjectURL(previzualizare);
    setPoza(null);
    setPrevizualizare(null);
    setCnp("");
    setEroareCnp(null);
    setEroare(null);
    setProbleme([]);
    // incercariEsuate ramane: e contorul care deblocheaza "Continua oricum".
    setPas("alegere");
  }

  function continua() {
    if (blocat && !poateSari) return;

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

      {deAfisat.length > 0 ? (
        <Banda ton={blocat ? "eroare" : "info"}>
          {deAfisat.length === 1 ? (
            deAfisat[0].mesaj
          ) : (
            <ul className="flex flex-col gap-1">
              {deAfisat.map((problema) => (
                <li key={problema.cod}>{problema.mesaj}</li>
              ))}
            </ul>
          )}
        </Banda>
      ) : null}

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
          {/* Lumina e singurul lucru pe care il poate corecta uitandu-se la ecran. */}
          {!camera.eroare && indiciuLumina ? <Banda ton="info">{indiciuLumina}</Banda> : null}

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
            <Button
              className="flex-1"
              onClick={continua}
              loading={seCiteste}
              disabled={!cnp || (blocat && !poateSari)}
            >
              {poateSari ? "Continuă oricum" : "Continua"}
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
