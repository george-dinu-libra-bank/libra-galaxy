"use client";

import { useRef, useState, useTransition } from "react";
import { CheckCircle2, FileUp } from "lucide-react";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { incarcaAdeverinta } from "@/lib/actions/credite";
import { pregatesteDocument } from "@/lib/imagine";
import { formateazaSuma } from "@/lib/utils";

const TIPURI_ACCEPTATE = "application/pdf,image/jpeg,image/png,image/webp";
const MAX_OCTETI = 10 * 1024 * 1024;

/**
 * Încărcarea adeverinței de venit, în pasul de decizie.
 *
 * Apare doar când banca n-a putut confirma venitul din încasări — cine are
 * salariul vizibil în cont nu vede componenta deloc. Nu cerem hârtii pentru
 * ceva ce vedem deja.
 *
 * Poza trece prin `pregatesteDocument` (redimensionare la 1600px, fără tăiere
 * pătrată), scrisă pentru buletin și potrivită identic aici: un document tăiat
 * pierde exact cifrele pe care trebuie să le citim. PDF-ul se trimite neatins —
 * dacă are strat de text, e citit exact, fără OCR.
 */
export function IncarcaAdeverinta({ idCerere }: { idCerere: string }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [seTrimite, startTransition] = useTransition();
  const [eroare, setEroare] = useState<string | null>(null);
  const [citit, setCitit] = useState<{ venit: number | null } | null>(null);

  function alege(eveniment: React.ChangeEvent<HTMLInputElement>) {
    const brut = eveniment.target.files?.[0];
    // Input-ul se goleste imediat, ca acelasi fisier sa poata fi ales din nou
    // dupa o eroare — altfel `change` nu se mai declanseaza a doua oara.
    eveniment.target.value = "";
    if (!brut) return;

    if (brut.size > MAX_OCTETI) {
      setEroare("Fișierul e mai mare de 10 MB. Încearcă o poză mai mică.");
      return;
    }

    setEroare(null);
    startTransition(async () => {
      let fisier: File;
      try {
        // PDF-ul nu se atinge; doar pozele se redimensionează.
        fisier = brut.type.startsWith("image/")
          ? await pregatesteDocument(brut, "adeverinta.jpg")
          : brut;
      } catch {
        setEroare("Nu am putut pregăti fișierul. Încearcă altul.");
        return;
      }

      const formular = new FormData();
      formular.append("fisier", fisier);

      const rezultat = await incarcaAdeverinta(idCerere, formular);
      if (rezultat.eroare) {
        setEroare(rezultat.eroare);
        return;
      }
      setCitit({ venit: rezultat.venitCitit ?? null });
    });
  }

  if (citit) {
    return (
      <section className="rounded-card bg-surface p-5 shadow-sm">
        <div className="flex items-start gap-3">
          <CheckCircle2
            size={22}
            strokeWidth={1.75}
            aria-hidden
            className="mt-0.5 shrink-0 text-success"
          />
          <div>
            <h2 className="text-[15px] font-semibold text-ink">Adeverința a ajuns la noi</h2>
            <p className="mt-1 text-[13px] leading-[19px] text-ink-soft">
              {citit.venit === null
                ? "Nu am putut citi automat suma din document, dar un coleg se uită peste el."
                : `Am citit un venit net de ${formateazaSuma(citit.venit)}. Un coleg confirmă suma și primești răspunsul.`}
            </p>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="rounded-card bg-surface p-5 shadow-sm">
      <h2 className="text-[15px] font-semibold text-ink">Dovedește-ți venitul</h2>
      <p className="mt-1 text-[13px] leading-[19px] text-ink-soft">
        Nu vedem un salariu care intră constant în contul tău, așa că avem nevoie de o
        adeverință de venit de la angajator. O citim automat, iar un coleg confirmă suma.
      </p>

      {eroare ? (
        <div className="mt-4">
          <Banda ton="eroare">{eroare}</Banda>
        </div>
      ) : null}

      <input
        ref={inputRef}
        type="file"
        accept={TIPURI_ACCEPTATE}
        onChange={alege}
        className="sr-only"
        aria-hidden
        tabIndex={-1}
      />

      <Button
        className="mt-4 w-full"
        loading={seTrimite}
        onClick={() => inputRef.current?.click()}
        iconaStanga={<FileUp size={18} strokeWidth={1.75} aria-hidden />}
      >
        {seTrimite ? "Citim documentul…" : "Încarcă adeverința"}
      </Button>

      <p className="mt-3 text-[12px] leading-[17px] text-ink-faint">
        PDF sau poză, până în 10 MB. Documentul se șterge la 30 de zile după ce dosarul se
        închide.
      </p>
    </section>
  );
}
