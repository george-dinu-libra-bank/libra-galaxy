import { User } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Poza unei persoane — utilizatorul curent in header sau contrapartea unei
 * tranzactii. Fara poza (avatar_url null in profiles) se afiseaza iconita
 * `User` de la lucide pe fundal gri.
 *
 * Umple containerul, deci marimea se da din afara (`h-20 w-20` etc.).
 */
export function AvatarProfil({
  url,
  nume,
  marimeIcoana = 20,
  className,
}: {
  url: string | null;
  nume: string;
  /** Dimensiunea iconitei implicite; se scaleaza cu cercul. */
  marimeIcoana?: number;
  className?: string;
}) {
  if (!url) {
    return (
      <span
        className={cn(
          "flex h-full w-full items-center justify-center rounded-full bg-muted text-ink-faint",
          className,
        )}
      >
        <User size={marimeIcoana} strokeWidth={1.75} aria-hidden />
      </span>
    );
  }

  // URL public din Supabase Storage, poza fiind deja redimensionata la 512 px
  // in browser inainte de upload — nu are ce optimiza next/image peste ea.
  // eslint-disable-next-line @next/next/no-img-element
  return (
    <img
      src={url}
      alt={`Poza de profil a lui ${nume}`}
      className={cn("h-full w-full rounded-full object-cover", className)}
    />
  );
}
