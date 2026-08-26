import { etichetaZi, formateazaOra as ora } from "@/lib/utils";
import type { EvenimentCerere } from "@/lib/tipuri-admin";

/**
 * Jurnalul dosarului — cine l-a atins, ce a facut, si cand.
 *
 * `credit_evenimente` se scrie din 16 locuri din serviciu de la primul commit
 * al creditarii, dar pana acum n-o citea nicio ruta: auditul exista si nu-l
 * vedea nimeni. Un credit fara urma nu se poate nici contesta, nici apara.
 *
 * Textele sunt scrise pentru om, nu preluate din `tip`: „decizie_manuala_respins"
 * spune ceva unui dezvoltator, nu unui analist care deschide dosarul altcuiva
 * peste trei luni.
 */

const ETICHETE: Record<string, string> = {
  cerere_depusa: "Cerere depusă",
  cerere_evaluata: "Evaluată automat",
  cerere_anulata: "Retrasă de client",
  documente_cerute: "S-au cerut documente",
  document_incarcat: "Document încărcat",
  document_confirmat: "Venit confirmat de analist",
  client_notificat: "Mesaj către client",
  decizie_manuala_aprobat: "Aprobată de analist",
  decizie_manuala_respins: "Respinsă de analist",
  decizie_lasata_la_analist: "Trimisă spre decizie umană",
  oferta_retrasa: "Ofertă retrasă",
  oferta_expirata: "Ofertă expirată",
  oferta_acceptata: "Ofertă semnată de client",
  credit_acordat: "Credit acordat",
};

const ACTOR: Record<string, string> = {
  client: "clientul",
  administrator: "analistul",
  sistem: "automat",
};

export function JurnalCerere({ evenimente }: { evenimente: EvenimentCerere[] }) {
  if (evenimente.length === 0) return null;

  return (
    <section className="rounded-card border border-line bg-surface p-5">
      <h2 className="text-[15px] font-semibold text-ink">Ce s-a întâmplat cu dosarul</h2>
      <p className="mt-1 text-[13px] leading-[19px] text-ink-faint">
        Fiecare schimbare de stare, în ordine. Se adaugă, nu se modifică și nu se șterge.
      </p>

      <ol className="mt-4 flex flex-col">
        {evenimente.map((eveniment, indice) => (
          <li key={eveniment.id} className="flex gap-3">
            {/* Bulina plus linia care coboara — ultima nu are linie, ca sirul
                sa se termine vizibil, nu sa para taiat. */}
            <div className="flex flex-col items-center">
              <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-primary-600" />
              {indice < evenimente.length - 1 ? (
                <span className="w-px flex-1 bg-line" />
              ) : null}
            </div>

            <div className="min-w-0 flex-1 pb-4">
              <p className="text-[13.5px] font-medium text-ink">
                {ETICHETE[eveniment.tip] ?? eveniment.tip}
              </p>
              <p className="mt-0.5 text-[12px] text-ink-faint">
                {etichetaZi(eveniment.creat_la)} · {ora(eveniment.creat_la)}
                {eveniment.actor ? ` · ${ACTOR[eveniment.actor] ?? eveniment.actor}` : ""}
              </p>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
