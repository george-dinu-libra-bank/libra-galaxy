import { cn } from "@/lib/utils";

/** Antetul unei sectiuni de pe landing: supratitlu, titlu, subtitlu. */
export function AntetSectiune({
  supratitlu,
  titlu,
  subtitlu,
  className,
}: {
  supratitlu: string;
  titlu: string;
  subtitlu?: string;
  className?: string;
}) {
  return (
    <div className={cn("max-w-[56ch]", className)}>
      <p className="text-[12.5px] font-semibold uppercase tracking-[0.08em] text-primary-600">
        {supratitlu}
      </p>
      <h2 className="mt-2 text-[26px] font-bold leading-[32px] tracking-[-0.02em] text-ink sm:text-[30px] sm:leading-[36px]">
        {titlu}
      </h2>
      {subtitlu ? (
        <p className="mt-3 text-[15px] leading-[22px] text-ink-soft">{subtitlu}</p>
      ) : null}
    </div>
  );
}
