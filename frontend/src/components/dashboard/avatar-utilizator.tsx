"use client";

import { useRouter } from "next/navigation";
import { Camera, ImagePlus, Trash2 } from "lucide-react";
import { useCallback, useEffect, useRef, useState, useTransition } from "react";
import { AvatarProfil } from "@/components/ui/avatar-profil";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { Drawer, DrawerContent, DrawerTrigger } from "@/components/ui/drawer";
import { salveazaAvatar, stergeAvatar } from "@/lib/actions/profil";
import { pregatesteAvatar } from "@/lib/imagine";

type Actiune = "salvare" | "stergere" | null;

/**
 * Poza de profil din header-ul dashboardului. La apasare se deschide un drawer
 * din care utilizatorul isi incarca o poza din fisiere sau isi face una cu
 * camera laptopului. Fara poza, se afiseaza iconita `User` pe fundal gri.
 */
export function AvatarUtilizator({
  avatarUrl,
  nume,
}: {
  avatarUrl: string | null;
  nume: string;
}) {
  const router = useRouter();

  const [deschis, setDeschis] = useState(false);
  const [previzualizare, setPrevizualizare] = useState<string | null>(null);
  const [poza, setPoza] = useState<File | null>(null);
  const [cameraPornita, setCameraPornita] = useState(false);
  const [eroare, setEroare] = useState<string | null>(null);
  const [actiune, setActiune] = useState<Actiune>(null);
  const [seTrimite, startTransition] = useTransition();

  const inputRef = useRef<HTMLInputElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const fluxRef = useRef<MediaStream | null>(null);
  const urlRef = useRef<string | null>(null);

  const opresteCamera = useCallback(() => {
    fluxRef.current?.getTracks().forEach((pista) => pista.stop());
    fluxRef.current = null;
    setCameraPornita(false);
  }, []);

  /** Un singur obiect-URL viu la un moment dat, ca sa nu curgem memorie. */
  const arataPreview = useCallback((fisier: File | null) => {
    if (urlRef.current) URL.revokeObjectURL(urlRef.current);
    urlRef.current = fisier ? URL.createObjectURL(fisier) : null;
    setPoza(fisier);
    setPrevizualizare(urlRef.current);
  }, []);

  // Camera si obiect-URL-ul raman deschise daca utilizatorul navigheaza cu
  // drawerul deschis — le inchidem la demontare.
  useEffect(() => {
    return () => {
      fluxRef.current?.getTracks().forEach((pista) => pista.stop());
      if (urlRef.current) URL.revokeObjectURL(urlRef.current);
    };
  }, []);

  // Fluxul exista inainte sa se monteze <video>, deci il legam dupa randare.
  useEffect(() => {
    const video = videoRef.current;

    if (!cameraPornita || !video || !fluxRef.current) return;

    video.srcObject = fluxRef.current;
    void video.play().catch(() => {});
  }, [cameraPornita]);

  async function preia(brut: Blob) {
    try {
      arataPreview(await pregatesteAvatar(brut));
      setEroare(null);
    } catch {
      setEroare("Nu am putut citi poza. Încearcă alt fișier.");
    }
  }

  async function alegeFisier(eveniment: React.ChangeEvent<HTMLInputElement>) {
    const fisier = eveniment.target.files?.[0];
    // Golim inputul ca sa se declanseze change si daca alege acelasi fisier.
    eveniment.target.value = "";
    if (fisier) await preia(fisier);
  }

  async function porneCamera() {
    setEroare(null);

    if (!navigator.mediaDevices?.getUserMedia) {
      setEroare("Browserul acesta nu are acces la cameră.");
      return;
    }

    try {
      fluxRef.current = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user", width: { ideal: 1280 }, height: { ideal: 1280 } },
        audio: false,
      });
      arataPreview(null);
      setCameraPornita(true);
    } catch {
      setEroare("Nu am putut porni camera. Verifică permisiunile browserului.");
    }
  }

  async function fotografiaza() {
    const video = videoRef.current;

    if (!video?.videoWidth) return;

    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Previzualizarea e in oglinda, ca la orice camera de selfie. Daca am salva
    // cadrul brut, poza ar iesi intoarsa fata de ce tocmai a vazut omul — deci
    // oglindim si panza, ca rezultatul sa fie exact previzualizarea.
    ctx.translate(canvas.width, 0);
    ctx.scale(-1, 1);
    ctx.drawImage(video, 0, 0);

    const brut = await new Promise<Blob | null>((rezolva) =>
      canvas.toBlob(rezolva, "image/jpeg", 0.92),
    );

    opresteCamera();

    if (!brut) {
      setEroare("Nu am putut face poza. Încearcă din nou.");
      return;
    }

    await preia(brut);
  }

  function inchide() {
    opresteCamera();
    arataPreview(null);
    setEroare(null);
    setDeschis(false);
  }

  function salveaza() {
    if (!poza) return;

    setEroare(null);
    setActiune("salvare");

    startTransition(async () => {
      const date = new FormData();
      date.append("poza", poza);

      const rezultat = await salveazaAvatar(date);
      setActiune(null);

      if (rezultat.eroare) {
        setEroare(rezultat.eroare);
        return;
      }

      inchide();
      router.refresh();
    });
  }

  function sterge() {
    setEroare(null);
    setActiune("stergere");

    startTransition(async () => {
      const rezultat = await stergeAvatar();
      setActiune(null);

      if (rezultat.eroare) {
        setEroare(rezultat.eroare);
        return;
      }

      inchide();
      router.refresh();
    });
  }

  const afisat = previzualizare ?? avatarUrl;

  return (
    <Drawer
      open={deschis}
      onOpenChange={(valoare) => (valoare ? setDeschis(true) : inchide())}
    >
      <DrawerTrigger
        aria-label={avatarUrl ? "Schimbă poza de profil" : "Adaugă o poză de profil"}
        className="h-10 w-10 shrink-0 overflow-hidden rounded-full shadow-sm transition-transform duration-[180ms] ease-soft hover:scale-105 active:scale-[0.98] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
      >
        <AvatarProfil url={avatarUrl} nume={nume} marimeIcoana={18} />
      </DrawerTrigger>

      <DrawerContent
        title="Poza de profil"
        description="Încarcă o poză din fișiere sau fă una acum, cu camera."
        footer={
          <div className="flex flex-col gap-2">
            <Button
              className="w-full"
              disabled={!poza}
              loading={seTrimite && actiune === "salvare"}
              onClick={salveaza}
            >
              Salvează poza
            </Button>

            {avatarUrl ? (
              <Button
                varianta="ghost"
                className="w-full text-danger hover:bg-danger/8 hover:text-danger"
                loading={seTrimite && actiune === "stergere"}
                onClick={sterge}
                iconaStanga={
                  seTrimite && actiune === "stergere" ? undefined : (
                    <Trash2 size={18} strokeWidth={1.75} aria-hidden />
                  )
                }
              >
                Șterge poza
              </Button>
            ) : null}
          </div>
        }
      >
        <div className="flex flex-col items-center gap-5">
          {eroare ? (
            <div className="w-full">
              <Banda ton="eroare">{eroare}</Banda>
            </div>
          ) : null}

          {cameraPornita ? (
            <>
              <div className="h-44 w-44 overflow-hidden rounded-full bg-ink shadow-md">
                <video
                  ref={videoRef}
                  playsInline
                  muted
                  className="h-full w-full -scale-x-100 object-cover"
                />
              </div>

              <div className="flex w-full gap-2">
                <Button varianta="secondary" className="flex-1" onClick={opresteCamera}>
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
            <>
              <div className="h-44 w-44 animate-pop overflow-hidden rounded-full border border-line shadow-md">
                <AvatarProfil url={afisat} nume={nume} marimeIcoana={56} />
              </div>

              {previzualizare ? (
                <p className="text-[13px] text-ink-faint">
                  Așa va arăta. Apasă „Salvează poza" ca să o păstrezi.
                </p>
              ) : null}

              <div className="flex w-full flex-col gap-2">
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
                  onClick={porneCamera}
                  iconaStanga={<Camera size={18} strokeWidth={1.75} aria-hidden />}
                >
                  Fă o poză cu camera
                </Button>
              </div>

              <input
                ref={inputRef}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                className="sr-only"
                onChange={alegeFisier}
              />
            </>
          )}
        </div>
      </DrawerContent>
    </Drawer>
  );
}
