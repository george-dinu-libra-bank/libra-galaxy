"use client";

import { Camera, RotateCcw } from "lucide-react";
import { useRef, useState, useTransition } from "react";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { type ProblemaPoza, verificaCalitatePoza } from "@/lib/actions/identitate";
import { useIndiciuLumina } from "@/lib/calitate-poza";
import { useCameraCapture } from "@/lib/camera";
import { pregatesteAvatar } from "@/lib/imagine";

/**
 * De la a cata incercare esuata ii oferim si scaparea "Continua oricum".
 * Blocarea e moale intentionat: verificarea de calitate e un ajutor, iar
 * contul intra oricum in 'pending_review' pentru un om, deci o camera proasta
 * sau un ten pe care detectorul se descurca greu n-are voie sa blocheze
 * definitiv inregistrarea.
 */
const INCERCARI_PANA_LA_SCAPARE = 2;

/**
 * Al doilea pas al inregistrarii: un selfie facut pe loc, comparat de
 * DeepFace cu poza de pe buletin. Special doar cu camera (fara incarcare de
 * fisier) — o poza aleasa din galerie ar submina scopul verificarii "live",
 * desi DeepFace insusi nu detecteaza spoofing (limitare cunoscuta).
 *
 * Inainte de a trimite mai departe, poza trece pe la /api/identity/check-photo,
 * care spune concret ce e in neregula ("nu gasim nicio fata", "e prea
 * intunecata"). Fara asta, o poza proasta pleaca la fel de tacut ca una buna
 * si omul afla abia peste zile ca i-a ramas contul in asteptare.
 */
export function SelfieCapture({ onFinalizat }: { onFinalizat: (file: File) => void }) {
  const [previzualizare, setPrevizualizare] = useState<string | null>(null);
  const [poza, setPoza] = useState<File | null>(null);
  const [eroare, setEroare] = useState<string | null>(null);
  const [probleme, setProbleme] = useState<ProblemaPoza[]>([]);
  const [incercariEsuate, setIncercariEsuate] = useState(0);
  const [seVerifica, startTransition] = useTransition();

  // Verificarea e asincrona, iar "Reia poza" ramane apasabil cat tine. Fara
  // contorul asta, raspunsul pentru poza abandonata ar ateriza peste cea noua.
  const generatieRef = useRef(0);

  const camera = useCameraCapture({ facingMode: "user", oglindeste: true });
  const indiciuLumina = useIndiciuLumina(camera.videoRef, camera.pornita);

  const blocat = probleme.some((problema) => problema.blocanta);
  // Cand poza e respinsa, avertismentele secundare ("pare stearsa") doar
  // dilueaza motivul real — se arata doar cand nu blocheaza nimic.
  const deAfisat = blocat ? probleme.filter((problema) => problema.blocanta) : probleme;
  const poateSari = blocat && incercariEsuate >= INCERCARI_PANA_LA_SCAPARE;

  async function fotografiaza() {
    setEroare(null);
    setProbleme([]);
    const generatie = ++generatieRef.current;

    const brut = await camera.fotografiaza();

    if (!brut) {
      setEroare("Nu am putut face poza. Încearcă din nou.");
      return;
    }

    let fisier: File;
    try {
      fisier = await pregatesteAvatar(brut);
    } catch {
      setEroare("Nu am putut procesa poza. Încearcă din nou.");
      return;
    }

    setPoza(fisier);
    setPrevizualizare(URL.createObjectURL(fisier));

    startTransition(async () => {
      const rezultat = await verificaCalitatePoza(fisier, "selfie");
      if (generatieRef.current !== generatie) return; // poza a fost reluata intre timp

      setProbleme(rezultat.probleme);
      if (!rezultat.acceptabila) setIncercariEsuate((numar) => numar + 1);
    });
  }

  function reia() {
    generatieRef.current += 1;
    if (previzualizare) URL.revokeObjectURL(previzualizare);
    setPoza(null);
    setPrevizualizare(null);
    setEroare(null);
    setProbleme([]);
    // incercariEsuate ramane: e chiar contorul care deblocheaza "Continua oricum".
  }

  function trimite() {
    if (poza) onFinalizat(poza);
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

      {poza && previzualizare ? (
        <>
          <div className="mx-auto h-44 w-44 animate-pop overflow-hidden rounded-full border border-line shadow-md">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={previzualizare} alt="Selfie" className="h-full w-full object-cover" />
          </div>

          {blocat ? (
            <div className="flex gap-2">
              <Button
                className="flex-1"
                onClick={reia}
                iconaStanga={<RotateCcw size={18} strokeWidth={1.75} aria-hidden />}
              >
                Reia poza
              </Button>
              {poateSari ? (
                <Button varianta="secondary" className="flex-1" onClick={trimite}>
                  Continuă oricum
                </Button>
              ) : null}
            </div>
          ) : (
            <div className="flex gap-2">
              <Button
                varianta="secondary"
                className="flex-1"
                onClick={reia}
                iconaStanga={<RotateCcw size={18} strokeWidth={1.75} aria-hidden />}
              >
                Reia poza
              </Button>
              <Button className="flex-1" onClick={trimite} loading={seVerifica}>
                Continua
              </Button>
            </div>
          )}
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
          {/* Lumina e singurul lucru pe care il poate corecta uitandu-se la ecran. */}
          {!camera.eroare && indiciuLumina ? <Banda ton="info">{indiciuLumina}</Banda> : null}

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
