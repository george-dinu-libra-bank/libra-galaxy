"use client";

import { useRouter } from "next/navigation";
import { ArrowDownLeft, ChevronRight } from "lucide-react";
import { toast } from "sonner";
import { AvatarProfil } from "@/components/ui/avatar-profil";
import type { EvenimentTranzactie } from "@/hooks/use-canal-utilizator";
import { formateazaSuma } from "@/lib/utils";

/**
 * Notificarea de incasare. Nu folosim toastul implicit al lui sonner, ci o
 * carte in limbajul Libra: aceeasi poza cu badge de directie ca un rand din
 * istoric (vezi dashboard/ultimele-tranzactii.tsx) si suma verde. Atinsa, duce
 * in istoric. Verdele badge-ului si al sumei e tot semnalul de care e nevoie —
 * fara accent pe muchie.
 */
export function ToastIncasare({
  eveniment,
  idToast,
}: {
  eveniment: EvenimentTranzactie;
  /** Id-ul dat de sonner, ca sa inchidem cartea dupa ce am navigat. */
  idToast: string | number;
}) {
  const router = useRouter();

  const nume = eveniment.contraparte ?? "un cont Libra";

  return (
    <button
      type="button"
      onClick={() => {
        router.push("/istoric");
        toast.dismiss(idToast);
      }}
      aria-label={`Ai primit ${formateazaSuma(eveniment.suma, eveniment.valuta)} de la ${nume}. Vezi istoricul.`}
      className="flex w-full items-center gap-3 rounded-card border border-line bg-surface p-3.5 text-left shadow-lg transition-transform duration-200 ease-soft hover:-translate-y-px active:translate-y-0 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-success/30"
    >
      <span className="relative h-11 w-11 shrink-0">
        <AvatarProfil url={eveniment.poza} nume={nume} marimeIcoana={20} />

        <span className="absolute -bottom-0.5 -right-0.5 flex h-[19px] w-[19px] items-center justify-center rounded-full border-2 border-surface bg-success">
          <ArrowDownLeft size={11} strokeWidth={2.5} aria-hidden className="text-white" />
        </span>
      </span>

      <span className="min-w-0 flex-1">
        <span className="tabular block text-[17px] font-semibold leading-tight text-success">
          + {formateazaSuma(eveniment.suma, eveniment.valuta)}
        </span>
        <span className="mt-0.5 block truncate text-[13px] text-ink-soft">
          de la <span className="font-semibold text-ink">{nume}</span>
        </span>
        {eveniment.descriere ? (
          <span className="block truncate text-[12.5px] text-ink-faint">
            {eveniment.descriere}
          </span>
        ) : null}
      </span>

      <ChevronRight
        size={16}
        strokeWidth={2}
        aria-hidden
        className="shrink-0 text-ink-faint"
      />
    </button>
  );
}
