import { cn } from "@/lib/utils";

/**
 * Semnalul „ai ceva necitit", intr-un singur loc.
 *
 * Folosit de clopotel, de butonul de discutie si de cardul de credite din
 * dashboard. Trei copii ar arata diferit la prima ajustare de stil, iar o
 * bulina care nu arata la fel peste tot inceteaza sa mai fie citita ca semnal.
 *
 * `numar = 0` nu randeaza nimic: absenta e starea normala, si nu merita un
 * element gol in DOM.
 */
export function Bulina({
  numar,
  className,
  /** Fara cifra — doar punctul. Pentru locurile inguste, unde numarul n-ar incapea. */
  doarPunct = false,
}: {
  numar: number;
  className?: string;
  doarPunct?: boolean;
}) {
  if (numar <= 0) return null;

  if (doarPunct) {
    return (
      <span
        aria-label={`${numar} necitite`}
        className={cn("block h-2.5 w-2.5 rounded-full bg-danger", className)}
      />
    );
  }

  return (
    <span
      aria-label={`${numar} necitite`}
      className={cn(
        "flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-danger px-1",
        "text-[10.5px] font-bold leading-none text-white",
        className,
      )}
    >
      {numar > 9 ? "9+" : numar}
    </span>
  );
}
