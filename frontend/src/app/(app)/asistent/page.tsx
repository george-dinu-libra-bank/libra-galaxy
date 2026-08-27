import type { Metadata } from "next";
import { Sparkles } from "lucide-react";
import { FereastraChat } from "@/components/asistent/fereastra-chat";
import { ListaConversatiiDrawer } from "@/components/asistent/lista-conversatii-drawer";
import { obtineConversatii, obtineMesaje } from "@/lib/data/asistent";

/** Plafon pentru textul venit din URL: nimeni nu trebuie sa poata lipi un roman in casuta. */
const MAX_INTREBARE = 300;

export const metadata: Metadata = {
  title: "Asistent · Galaxy Bank",
};

/**
 * Ecranul asistentului: reasoning-ul sta in orchestratorul Python din spatele
 * FastAPI (ARCHITECTURE.md 3.5 si 15) — pagina doar afiseaza conversatia si
 * trimite mesaje catre backend.
 *
 * `?c=<id>` alege conversatia activa; fara parametru se porneste implicit cea
 * mai recenta. `?nou=1` forteaza un ecran gol (nu se poate distinge altfel
 * "niciun parametru" de "utilizatorul a cerut explicit o conversatie noua" —
 * fara semnalul asta, "Conversație nouă" redeschidea tacit ultima conversatie).
 *
 * `?intrebare=<text>` pre-completeaza casuta, fara sa trimita. Vine din
 * notificarile bancii (components/dashboard/mesaje-banca.tsx): omul caruia i
 * s-a blocat contul ajunge aici cu intrebarea deja scrisa, dar apasa el
 * "Trimite" — si o poate schimba inainte.
 */
export default async function AsistentPage({
  searchParams,
}: {
  searchParams: Promise<{ c?: string; nou?: string; intrebare?: string }>;
}) {
  const { c, nou, intrebare } = await searchParams;

  const conversatii = await obtineConversatii();
  const conversatieId = nou ? null : (c ?? conversatii[0]?.id ?? null);
  const mesaje = conversatieId ? await obtineMesaje(conversatieId) : [];

  return (
    <div className="mx-auto flex w-full max-w-[440px] flex-col px-6 pb-6 pt-8 sm:max-w-2xl">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-xl font-bold tracking-[-0.02em] text-ink">
            <Sparkles size={20} strokeWidth={1.75} aria-hidden className="text-primary-600" />
            Asistent
          </h1>
          <p className="mt-1 text-[13px] text-ink-faint">Întrebări despre banii tăi, în cuvintele tale.</p>
        </div>

        <ListaConversatiiDrawer conversatii={conversatii} conversatieActivaId={conversatieId} />
      </div>

      <FereastraChat
        conversatieIdInitial={conversatieId}
        mesajeInitiale={mesaje}
        intrebareInitiala={intrebare?.slice(0, MAX_INTREBARE) ?? ""}
      />
    </div>
  );
}
