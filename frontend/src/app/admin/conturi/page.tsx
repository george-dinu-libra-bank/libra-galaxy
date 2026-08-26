import { Users } from "lucide-react";
import { cereAdmin } from "@/lib/admin";
import { obtineToateConturile } from "@/lib/data/admin-verificari";
import { obtineStareConturiToti } from "@/lib/data/admin-tranzactii";
import type { ProfilAdmin, StareConturi } from "@/lib/tipuri-admin";
import { BackendError } from "@/lib/backend";
import { Banda } from "@/components/ui/banda";
import { RestabilesteBiometrie } from "@/components/admin/restabileste-biometrie";
import { BlocareCont } from "@/components/admin/blocare-cont";
import { CereriStergere } from "@/components/admin/cereri-stergere";
import { CereriInchidere } from "@/components/admin/cereri-inchidere";
import { obtineCereriStergere, type CerereStergere } from "@/lib/data/admin-stergeri";
import { obtineCereriInchidere, type CerereInchidere } from "@/lib/data/admin-inchideri";
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

  // Starea conturilor vine separat si nu blocheaza lista: daca ruta cade,
  // lista se vede oricum, doar fara butoanele de blocare.
  let stariConturi: StareConturi[] = [];
  // Cozile nu pot darama lista de conturi: daca o ruta cade, restul paginii se
  // vede la fel. Dar caderea NU se mai inghite in tacere.
  //
  // Asa s-a ascuns o functie complet nefunctionala: metodele cozii ajunsesera pe
  // alta clasa din depozit, ruta raspundea 500, iar `.catch(() => [])` transforma
  // asta intr-o lista goala. Analistul vedea „nicio cerere" si credea ca nu e
  // niciuna. O coada goala si o coada care nu s-a putut incarca arata acum diferit.
  let cereriStergere: CerereStergere[] = [];
  let cereriInchidere: CerereInchidere[] = [];
  const cozicazute: string[] = [];

  async function incarca<T>(
    ce: string,
    promisiune: Promise<T[]>,
  ): Promise<T[]> {
    try {
      return await promisiune;
    } catch (exc) {
      console.error(`ERROR incarcare ${ce}:`, exc);
      cozicazute.push(ce);
      return [];
    }
  }

  try {
    [conturi, stariConturi, cereriStergere, cereriInchidere] = await Promise.all([
      obtineToateConturile(admin.token),
      incarca("starea conturilor", obtineStareConturiToti(admin.token)),
      incarca("cererile de închidere a relației", obtineCereriStergere(admin.token)),
      incarca("cererile de închidere a conturilor", obtineCereriInchidere(admin.token)),
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
          Blochează sau deblochează conturile unui client, ori restabilește manual referința
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
              stare={stariConturi.find((c) => c.id_utilizator === cont.id) ?? null}
            />
          ))}
        </div>
      ) : null}

      {cozicazute.length > 0 ? (
        <Banda ton="eroare">
          Nu am putut încărca {cozicazute.join(" și ")}. Ce vezi mai jos poate fi
          incomplet — reîncarcă pagina sau verifică backendul.
        </Banda>
      ) : null}

      {/* Inchiderea unui cont bancar sta inaintea plecarii din banca: e
          operatiunea mai deasa, si cea reversibila. */}
      <CereriInchidere cereri={cereriInchidere} />
      <CereriStergere cereri={cereriStergere} />
    </div>
  );
}

function RandCont({
  cont,
  stare,
}: {
  cont: ProfilAdmin;
  stare: StareConturi | null;
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

        {stare && stare.blocate > 0 ? (
          <span className="mt-1.5 ml-1.5 inline-block rounded-full bg-danger/10 px-2 py-0.5 text-[11px] font-medium text-danger">
            Conturi blocate
          </span>
        ) : null}
      </span>

      <span className="flex shrink-0 items-center gap-2">
        {stare ? (
          <BlocareCont
            idUtilizator={cont.id}
            nume={cont.nume}
            total={stare.total}
            blocate={stare.blocate}
          />
        ) : null}
        <RestabilesteBiometrie userId={cont.id} nume={cont.nume} />
      </span>
    </div>
  );
}
