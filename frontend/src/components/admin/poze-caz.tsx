"use client";

import { useState } from "react";
import { ImageOff, Maximize2 } from "lucide-react";
import { Drawer, DrawerContent } from "@/components/ui/drawer";

/**
 * Buletinul si selfie-ul, unul langa altul.
 *
 * Link-urile vin semnate de la backend si expira in cateva minute: bucket-urile
 * raman private, iar o adresa scursa nu mai inseamna nimic dupa aceea. De aceea
 * nu se folosesc componente care optimizeaza si cacheaza imaginile — o poza de
 * buletin nu are ce cauta intr-un cache de imagini.
 */
export function PozeCaz({
  urlBuletin,
  urlSelfie,
  secunde,
}: {
  urlBuletin: string | null;
  urlSelfie: string | null;
  secunde: number;
}) {
  const [marita, setMarita] = useState<{ url: string; titlu: string } | null>(null);

  return (
    <section>
      <div className="flex items-baseline justify-between">
        <h2 className="text-[15px] font-semibold text-ink">Pozele trimise</h2>
        <p className="text-[12.5px] text-ink-faint">
          Link-uri temporare, valabile {Math.round(secunde / 60)} minute
        </p>
      </div>

      <div className="mt-3 grid gap-4 sm:grid-cols-2">
        <Poza
          titlu="Buletin"
          url={urlBuletin}
          onMareste={(url) => setMarita({ url, titlu: "Buletin" })}
        />
        <Poza
          titlu="Selfie"
          url={urlSelfie}
          onMareste={(url) => setMarita({ url, titlu: "Selfie" })}
        />
      </div>

      <Drawer
        open={marita !== null}
        onOpenChange={(deschis) => {
          if (!deschis) setMarita(null);
        }}
      >
        <DrawerContent
          title={marita?.titlu ?? ""}
          description="Poza la dimensiune mare, pentru comparație."
          className="sm:max-w-[720px]"
        >
          {marita ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={marita.url}
              alt={marita.titlu}
              className="max-h-[70vh] w-full rounded-field object-contain"
            />
          ) : null}
        </DrawerContent>
      </Drawer>
    </section>
  );
}

function Poza({
  titlu,
  url,
  onMareste,
}: {
  titlu: string;
  url: string | null;
  onMareste: (url: string) => void;
}) {
  if (!url) {
    return (
      <div className="flex aspect-[4/3] flex-col items-center justify-center gap-2 rounded-card border border-dashed border-line bg-surface text-center">
        <ImageOff size={22} strokeWidth={1.75} aria-hidden className="text-ink-faint" />
        <p className="text-[13px] text-ink-faint">{titlu}: poza nu a putut fi încărcată</p>
      </div>
    );
  }

  return (
    <button
      type="button"
      onClick={() => onMareste(url)}
      className="group relative aspect-[4/3] overflow-hidden rounded-card border border-line bg-muted focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={url} alt={titlu} className="h-full w-full object-cover" />

      <span className="absolute inset-x-0 bottom-0 flex items-center justify-between bg-ink/60 px-3 py-2 text-white">
        <span className="text-[13px] font-medium">{titlu}</span>
        <Maximize2 size={14} strokeWidth={2} aria-hidden />
      </span>
    </button>
  );
}
