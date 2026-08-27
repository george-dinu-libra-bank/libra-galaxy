import { Captura, type DateCaptura } from "./captura";
import { cn } from "@/lib/utils";

/**
 * Rama de telefon in care se aseaza o captura. Proportia e cea a ecranului
 * pentru care se proiecteaza aplicatia (390x844, DESIGN.md 1).
 */
export function RamaTelefon({
  captura,
  className,
  priority = false,
}: {
  captura: DateCaptura;
  className?: string;
  priority?: boolean;
}) {
  return (
    <div
      className={cn(
        "relative w-full max-w-[300px] rounded-sheet border border-line bg-surface p-2.5 shadow-lg",
        className,
      )}
    >
      {/* Decupajul camerei — doar cat timp slotul e gol, ca sa se citeasca
          „telefon". Peste o captura reala ar fi o bara straina desenata exact
          peste antetul ecranului fotografiat. */}
      {captura.src ? null : (
        <span
          aria-hidden
          className="absolute left-1/2 top-4 z-10 h-1.5 w-16 -translate-x-1/2 rounded-full bg-line"
        />
      )}
      <Captura {...captura} priority={priority} className="w-full" />
    </div>
  );
}
