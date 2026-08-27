import { Inbox } from "lucide-react";
import { cereAdmin } from "@/lib/admin";
import { BackendError } from "@/lib/backend";
import { obtineCoadaSesizari, type SesizareSuport } from "@/lib/data/admin-tranzactii";
import { Banda } from "@/components/ui/banda";
import { RaspunsSesizare } from "@/components/admin/raspuns-sesizare";
import { dataSiOra } from "@/lib/momente";
import { cn } from "@/lib/utils";

export const dynamic = "force-dynamic";

const ETICHETE_STATUS: Record<string, { text: string; clasa: string }> = {
  deschisa: { text: "Deschisă", clasa: "bg-warning/10 text-warning" },
  in_lucru: { text: "În lucru", clasa: "bg-primary-500/10 text-primary-600" },
  rezolvata: { text: "Rezolvată", clasa: "bg-success/10 text-success" },
};

export default async function PaginaSesizari({
  searchParams,
}: {
  searchParams: Promise<{ toate?: string }>;
}) {
  const [{ toate }, admin] = await Promise.all([searchParams, cereAdmin()]);
  const doarDeschise = toate !== "1";

  let sesizari: SesizareSuport[] = [];
  let eroare: string | null = null;

  try {
    sesizari = await obtineCoadaSesizari(admin.token, doarDeschise);
  } catch (exc) {
    eroare =
      exc instanceof BackendError
        ? exc.message
        : "Nu am putut încărca sesizările. Verifică dacă backendul răspunde.";
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-[26px] font-bold leading-8 tracking-[-0.02em] text-ink">Sesizări</h1>
        <p className="mt-1.5 text-[15px] leading-[22px] text-ink-soft">
          Cereri scrise de clienți din conversația cu asistentul. Cea mai veche prima — cine
          așteaptă de mai mult timp e deasupra.
        </p>
      </div>

      <div className="flex gap-2">
        <a
          href="/admin/sesizari"
          className={cn(
            "rounded-full px-3 py-1.5 text-[13px] font-medium",
            doarDeschise ? "bg-primary-600 text-white" : "bg-muted text-ink-soft",
          )}
        >
          De rezolvat
        </a>
        <a
          href="/admin/sesizari?toate=1"
          className={cn(
            "rounded-full px-3 py-1.5 text-[13px] font-medium",
            doarDeschise ? "bg-muted text-ink-soft" : "bg-primary-600 text-white",
          )}
        >
          Toate
        </a>
      </div>

      {eroare ? (
        <Banda ton="info">
          <strong className="font-semibold">Sesizările nu sunt disponibile.</strong> {eroare} Dacă
          migrarea <code className="tabular">0039_cereri_suport.sql</code> nu a fost rulată încă,
          tabela lipsește.
        </Banda>
      ) : null}

      {!eroare && sesizari.length === 0 ? (
        <section className="flex flex-col items-center gap-3 rounded-card border border-dashed border-line bg-surface p-10 text-center">
          <span className="flex h-14 w-14 items-center justify-center rounded-full bg-muted">
            <Inbox size={26} strokeWidth={1.75} aria-hidden className="text-ink-faint" />
          </span>
          <p className="text-[15px] font-semibold text-ink">
            {doarDeschise ? "Nicio sesizare de rezolvat" : "Nicio sesizare"}
          </p>
        </section>
      ) : null}

      {sesizari.map((s) => {
        const eticheta = ETICHETE_STATUS[s.status] ?? ETICHETE_STATUS.deschisa;
        return (
          <article key={s.id} className="rounded-card border border-line bg-surface p-5 shadow-sm">
            <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <h2 className="text-[15px] font-semibold text-ink">{s.subiect}</h2>
              <span
                className={cn(
                  "rounded-full px-2 py-0.5 text-[11px] font-medium",
                  eticheta.clasa,
                )}
              >
                {eticheta.text}
              </span>
              <span className="text-[12.5px] text-ink-faint">{dataSiOra(s.creat_la)}</span>
            </div>

            <p className="mt-3 whitespace-pre-line text-[13.5px] leading-[20px] text-ink-soft">
              {s.rezumat}
            </p>

            {s.raspuns ? (
              <div className="mt-4 rounded-field bg-muted p-3">
                <p className="text-[12px] font-semibold text-ink-faint">Răspunsul băncii</p>
                <p className="mt-1 whitespace-pre-line text-[13px] leading-[19px] text-ink-soft">
                  {s.raspuns}
                </p>
              </div>
            ) : null}

            {s.status !== "rezolvata" ? <RaspunsSesizare idSesizare={s.id} /> : null}
          </article>
        );
      })}
    </div>
  );
}
