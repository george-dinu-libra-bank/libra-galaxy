import { Users } from "lucide-react";
import { cereAdmin } from "@/lib/admin";
import { obtineToateConturile } from "@/lib/data/admin-verificari";
import { obtineStareCarduriToti } from "@/lib/data/admin-tranzactii";
import type { ProfilAdmin, StareCarduri } from "@/lib/tipuri-admin";
import { BackendError } from "@/lib/backend";
import { Banda } from "@/components/ui/banda";
import { RestabilesteBiometrie } from "@/components/admin/restabileste-biometrie";
import { BlocareCont } from "@/components/admin/blocare-cont";
import { cn } from "@/lib/utils";

export const dynamic = "force-dynamic";

const ETICHETE_STATUS: Record<string, { text: string; clasa: string }> = {
  verified: { text: "Verificat", clasa: "bg-success/10 text-success" },
  pending_review: { text: "În revizuire", clasa: "bg-warning/10 text-warning" },
  rejected: { text: "Respins", clasa: "bg-danger/10 text-danger" },
  pending: { text: "Fără verificare", clasa: "bg-muted text-ink-faint" },
};

export default async function ConturiPage() {
  const admin = await cereAdmin();

  let conturi: ProfilAdmin[] = [];
  let eroare: string | null = null;

  // Starea cardurilor vine separat si nu blocheaza lista: daca ruta cade,
  // conturile se vad oricum, doar fara butoanele de blocare.
  let carduri: StareCarduri[] = [];

  try {
    [conturi, carduri] = await Promise.all([
      obtineToateConturile(admin.token),
      obtineStareCarduriToti(admin.token).catch(() => []),
    ]);
  } catch (exc) {
    eroare =
      exc instanceof BackendError
        ? exc.message
        : "Nu am putut incarca lista. Verifica daca backendul raspunde.";
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-[26px] font-bold leading-8 tracking-[-0.02em] text-ink">
          Toate conturile
        </h1>
        <p className="mt-1.5 text-[15px] leading-[22px] text-ink-soft">
          Blochează sau deblochează cardurile unui client, ori restabilește manual referința
          biometrică dacă pozele din storage au dispărut.
        </p>
      </div>

      {eroare ? <Banda ton="eroare">{eroare}</Banda> : null}

      {!eroare && conturi.length === 0 ? (
        <section className="flex flex-col items-center gap-3 rounded-card border border-dashed border-line bg-surface p-10 text-center">
          <span className="flex h-14 w-14 items-center justify-center rounded-full bg-muted">
            <Users size={26} strokeWidth={1.75} aria-hidden className="text-ink-faint" />
          </span>
          <p className="text-[15px] font-semibold text-ink">Niciun cont</p>
        </section>
      ) : null}

      {conturi.length > 0 ? (
        <div className="flex flex-col gap-3">
          {conturi.map((cont) => (
            <RandCont
              key={cont.id}
              cont={cont}
              carduri={carduri.find((c) => c.id_utilizator === cont.id) ?? null}
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}

function RandCont({
  cont,
  carduri,
}: {
  cont: ProfilAdmin;
  carduri: StareCarduri | null;
}) {
  const eticheta = ETICHETE_STATUS[cont.verification_status] ?? ETICHETE_STATUS.pending;

  return (
    <div className="flex items-center gap-4 rounded-card border border-line bg-surface p-4 shadow-sm">
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[15px] font-semibold text-ink">{cont.nume}</span>
        <span className="block truncate text-[12.5px] text-ink-faint">{cont.email}</span>
        <span
          className={cn(
            "mt-1.5 inline-block rounded-full px-2 py-0.5 text-[11px] font-medium",
            eticheta.clasa,
          )}
        >
          {eticheta.text}
        </span>

        {carduri && carduri.blocate > 0 ? (
          <span className="mt-1.5 ml-1.5 inline-block rounded-full bg-danger/10 px-2 py-0.5 text-[11px] font-medium text-danger">
            Carduri blocate
          </span>
        ) : null}
      </span>

      <span className="flex shrink-0 items-center gap-2">
        {carduri ? (
          <BlocareCont
            idUtilizator={cont.id}
            nume={cont.nume}
            total={carduri.total}
            blocate={carduri.blocate}
          />
        ) : null}
        <RestabilesteBiometrie userId={cont.id} nume={cont.nume} />
      </span>
    </div>
  );
}
