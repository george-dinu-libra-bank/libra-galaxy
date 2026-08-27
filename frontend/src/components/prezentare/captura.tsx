import Image from "next/image";
import { Camera, Monitor, Moon, Sun } from "lucide-react";
import { cn } from "@/lib/utils";

export type Tema = "deschisă" | "întunecată";

export type DateCaptura = {
  /** Calea publica a imaginii, ex. "/capturi/dashboard.png". Lipseste = slot gol. */
  src?: string;
  /** Text alternativ, obligatoriu si cand slotul e gol (ajunge in figcaption). */
  alt: string;
  /** Ruta din aplicatie care trebuie fotografiata, ex. "/dashboard". */
  ruta: string;
  /** Numele fisierului asteptat, relativ la `frontend/public/`. */
  fisier: string;
  /** Latimea x inaltimea cadrului, ex. "390×844". */
  dimensiune: string;
  /** Ce anume trebuie sa se vada in cadru. */
  detaliu: string;
  tema?: Tema;
  /** Pasi in plus inainte de captura (autentificare, date de test etc.). */
  pregatire?: string;
  /** Proportia cadrului, ca layout-ul sa nu sara cand apare imaginea. */
  raport?: string;
};

type CapturaProps = DateCaptura & {
  className?: string;
  priority?: boolean;
};

/**
 * Un loc rezervat pentru o captura de ecran.
 *
 * Capturile nu se pot genera din cod, deci pana cand cineva pune fisierul in
 * `public/capturi/` slotul afiseaza chiar instructiunea: ce ruta se deschide, ce
 * trebuie sa se vada in cadru, la ce latime si sub ce tema, si unde se salveaza
 * rezultatul. Cand `src` primeste o valoare, acelasi component devine imaginea.
 *
 * Lista completa a capturilor e si in `public/capturi/README.md`.
 */
export function Captura({
  src,
  alt,
  ruta,
  fisier,
  dimensiune,
  detaliu,
  tema = "deschisă",
  pregatire,
  className,
  raport = "390 / 844",
  priority = false,
}: CapturaProps) {
  const IconitaTema = tema === "întunecată" ? Moon : Sun;

  if (src) {
    return (
      <figure
        className={cn("relative overflow-hidden rounded-card bg-muted", className)}
        style={{ aspectRatio: raport }}
      >
        <Image
          src={src}
          alt={alt}
          fill
          sizes="(min-width: 1024px) 420px, 88vw"
          className="object-cover"
          priority={priority}
        />
      </figure>
    );
  }

  return (
    <figure
      className={cn(
        // `min-h-fit`: proportia da inaltimea obisnuita a slotului, dar daca
        // instructiunea nu incape (cadru ingust, font marit), cutia creste in
        // loc sa taie textul.
        "flex min-h-fit flex-col gap-4 overflow-hidden rounded-card border-2 border-dashed border-line bg-muted p-5",
        className,
      )}
      style={{ aspectRatio: raport }}
    >
      <div className="flex items-center gap-2">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-primary-50">
          <Camera size={18} strokeWidth={1.75} aria-hidden className="text-primary-600" />
        </span>
        <p className="text-[13px] font-semibold leading-[18px] text-ink">Captură necesară</p>
      </div>

      <figcaption className="flex flex-col gap-2.5 text-[12.5px] leading-[18px] text-ink-soft">
        <p>
          <span className="text-ink-faint">Deschide </span>
          <code className="rounded bg-surface px-1.5 py-0.5 font-mono text-[12px] text-primary-700">
            {ruta}
          </code>
        </p>

        <p>
          <span className="text-ink-faint">Trebuie să se vadă: </span>
          {detaliu}
        </p>

        {pregatire ? (
          <p>
            <span className="text-ink-faint">Înainte: </span>
            {pregatire}
          </p>
        ) : null}

        <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-ink-faint">
          <span className="inline-flex items-center gap-1.5">
            <Monitor size={16} strokeWidth={1.75} aria-hidden />
            {dimensiune}
          </span>
          <span className="inline-flex items-center gap-1.5">
            <IconitaTema size={16} strokeWidth={1.75} aria-hidden />
            temă {tema}
          </span>
        </p>

        {/* `break-all`: caile sunt mai lungi decat cadrul de 240 px al unei rame
            de telefon, iar un `<code>` nu rupe singur cuvantul. */}
        <p className="text-ink-faint">
          Salvează în{" "}
          <code className="break-all rounded bg-surface px-1.5 py-0.5 font-mono text-[12px] text-ink-soft">
            frontend/public/{fisier}
          </code>{" "}
          și adaugă{" "}
          <code className="break-all font-mono text-[12px]">src=&quot;/{fisier}&quot;</code>.
        </p>
      </figcaption>
    </figure>
  );
}
