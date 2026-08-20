"use client";

import { useCallback, useEffect, useRef, useState } from "react";

type OptiuniCamera = {
  facingMode: "user" | "environment";
  /** Oglindeste previzualizarea si poza finala (potrivit pentru selfie-uri). */
  oglindeste?: boolean
};

/**
 * Logica de camera (getUserMedia + captura pe canvas), extrasa din
 * AvatarUtilizator ca sa fie refolosita si pentru poza buletinului si pentru
 * selfie-ul de verificare a identitatii.
 */
export function useCameraCapture({ facingMode, oglindeste = false }: OptiuniCamera) {
  const [pornita, setPornita] = useState(false);
  const [eroare, setEroare] = useState<string | null>(null);

  const videoRef = useRef<HTMLVideoElement>(null);
  const fluxRef = useRef<MediaStream | null>(null);

  const opreste = useCallback(() => {
    fluxRef.current?.getTracks().forEach((pista) => pista.stop());
    fluxRef.current = null;
    setPornita(false);
  }, []);

  useEffect(() => opreste, [opreste]);

  useEffect(() => {
    const video = videoRef.current;
    if (!pornita || !video || !fluxRef.current) return;

    video.srcObject = fluxRef.current;
    void video.play().catch(() => {});
  }, [pornita]);

  const porneste = useCallback(async () => {
    setEroare(null);

    if (!navigator.mediaDevices?.getUserMedia) {
      setEroare("Browserul acesta nu are acces la cameră.");
      return;
    }

    try {
      fluxRef.current = await navigator.mediaDevices.getUserMedia({
        video: { facingMode, width: { ideal: 1600 }, height: { ideal: 1600 } },
        audio: false,
      });
      setPornita(true);
    } catch {
      setEroare("Nu am putut porni camera. Verifică permisiunile browserului.");
    }
  }, [facingMode]);

  const fotografiaza = useCallback(async (): Promise<Blob | null> => {
    const video = videoRef.current;
    if (!video?.videoWidth) return null;

    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    const ctx = canvas.getContext("2d");
    if (!ctx) return null;

    if (oglindeste) {
      // Previzualizarea unui selfie e in oglinda; oglindim si panza, ca
      // rezultatul sa fie exact ce a vazut omul pe ecran.
      ctx.translate(canvas.width, 0);
      ctx.scale(-1, 1);
    }
    ctx.drawImage(video, 0, 0);

    const brut = await new Promise<Blob | null>((rezolva) =>
      canvas.toBlob(rezolva, "image/jpeg", 0.92),
    );

    opreste();

    return brut;
  }, [oglindeste, opreste]);

  return { videoRef, pornita, eroare, porneste, opreste, fotografiaza };
}
