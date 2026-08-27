"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { CheckCircle2, Clock, FileSearch, FileUp, PenLine } from "lucide-react";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { ContractDrawer } from "@/components/credite/contract-drawer";
import { DiscutieDrawer } from "@/components/credite/discutie-drawer";
import { IncarcaAdeverinta } from "@/components/credite/incarca-adeverinta";
import { acceptaOferta, anuleazaCerere } from "@/lib/actions/credite";
import type { ContBancar } from "@/lib/data/conturi";
import type { CerereCredit, ContractCerere, MesajCerere } from "@/lib/data/credite";
import { formateazaSuma } from "@/lib/utils";

/**
 * Cererile care nu s-au terminat încă: ofertele de semnat și dosarele în analiză.
 *
 * Fără ecranul ăsta, o ofertă emisă după ce clientul a închis wizard-ul era
 * pierdută. Wizard-ul ținea oferta în starea lui de React și o arăta pe loc, dar
 * o cerere care trece prin analiză manuală primește oferta *mai târziu* — ore
 * sau zile după. Nu exista nicio cale înapoi la ea: `/credite` lista doar
 * creditele deja acordate.
 *
 * Se vede mai des de când o cerere fără venit confirmat nu se mai aprobă
 * automat: aproape orice ofertă ajunge acum să fie emisă în afara sesiunii.
 */
export function CereriInCurs({
  cereri,
  conturi,
  mesaje = {},
  contracte = {},
  discutieDeschisa = null,
}: {
  cereri: CerereCredit[];
  conturi: ContBancar[];
  /** Firul fiecarei cereri in curs, dupa id. Adus doar pentru ele — de obicei
   * zero sau una, deci fara N+1. */
  mesaje?: Record<string, MesajCerere[]>;
  /** Contractul fiecarei oferte, dupa id de cerere. Exista doar dupa aprobare. */
  contracte?: Record<string, ContractCerere | null>;
  /** Id-ul cererii al carei fir trebuie deschis din start (vine din notificare). */
  discutieDeschisa?: string | null;
}) {
  const oferte = cereri.filter((cerere) => cerere.status === "oferta");
  const inAnaliza = cereri.filter(
    (cerere) =>
      cerere.status === "analiza_manuala" ||
      cerere.status === "in_analiza" ||
      cerere.status === "asteapta_documente",
  );

  // Starile inchise nu se randau nicaieri: o cerere respinsa, expirata sau
  // retrasa disparea pur si simplu, iar clientul vedea ecranul de intrare
  // („n-ai niciun credit"), ca si cum n-ar fi depus nimic. Aici e si singurul
  // loc din care mai poate citi motivul si firul dosarului.
  const incheiate = cereri.filter((cerere) =>
    ["respinsa", "expirata", "anulata"].includes(cerere.status),
  );

  if (oferte.length === 0 && inAnaliza.length === 0 && incheiate.length === 0) return null;

  return (
    <div className="mt-6 space-y-3">
      {oferte.map((cerere) => (
        <Oferta
          key={cerere.id}
          cerere={cerere}
          conturi={conturi}
          mesaje={mesaje[cerere.id] ?? []}
          contract={contracte[cerere.id] ?? null}
          discutieDeschisa={discutieDeschisa === cerere.id}
        />
      ))}
      {inAnaliza.map((cerere) => (
        <InAnaliza
          key={cerere.id}
          cerere={cerere}
          mesaje={mesaje[cerere.id] ?? []}
          discutieDeschisa={discutieDeschisa === cerere.id}
        />
      ))}

      {incheiate.length > 0 ? (
        <section className="pt-3">
          <h2 className="text-[13px] font-semibold text-ink-faint">Cereri anterioare</h2>
          <div className="mt-2 space-y-2">
            {incheiate.map((cerere) => (
              <Incheiata
                key={cerere.id}
                cerere={cerere}
                mesaje={mesaje[cerere.id] ?? []}
                discutieDeschisa={discutieDeschisa === cerere.id}
              />
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}

/**
 * Retragerea cererii, din partea clientului.
 *
 * Nu e doar curatenie de ecran: inchiderea completeaza `finalizat_la` in
 * backend, deci porneste retentia documentelor. Fara ea, un dosar abandonat isi
 * tinea adeverinta in bucket la nesfarsit.
 *
 * Confirmare in doi pasi, in acelasi buton: e ireversibila, iar cererea
 * reprezinta munca deja facuta de om (venit, angajator, vechime).
 */
function RetrageCererea({ idCerere }: { idCerere: string }) {
  const router = useRouter();
  const [confirma, setConfirma] = useState(false);
  const [eroare, setEroare] = useState<string | null>(null);
  const [seTrimite, startTransition] = useTransition();

  if (eroare) {
    return <span className="text-[12.5px] text-danger">{eroare}</span>;
  }

  return (
    <button
      type="button"
      disabled={seTrimite}
      onClick={() => {
        if (!confirma) {
          setConfirma(true);
          return;
        }
        startTransition(async () => {
          const rezultat = await anuleazaCerere(idCerere);
          if (rezultat.eroare) {
            setEroare(rezultat.eroare);
            return;
          }
          router.refresh();
        });
      }}
      className="shrink-0 text-[12.5px] font-medium text-ink-faint underline-offset-2 hover:text-danger hover:underline disabled:opacity-50 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
    >
      {confirma ? "Sigur? Apasă din nou" : "Retrage cererea"}
    </button>
  );
}

const TEXT_INCHEIERE: Record<string, { eticheta: string; clasa: string }> = {
  respinsa: { eticheta: "Respinsă", clasa: "bg-danger/10 text-danger" },
  expirata: { eticheta: "Ofertă expirată", clasa: "bg-muted text-ink-soft" },
  anulata: { eticheta: "Retrasă de tine", clasa: "bg-muted text-ink-soft" },
};

/** Un dosar inchis. Se citeste, nu se mai continua — dar motivul si firul raman. */
function Incheiata({
  cerere,
  mesaje,
  discutieDeschisa,
}: {
  cerere: CerereCredit;
  mesaje: MesajCerere[];
  discutieDeschisa: boolean;
}) {
  const eticheta = TEXT_INCHEIERE[cerere.status] ?? TEXT_INCHEIERE.anulata;

  return (
    <section className="rounded-card border border-line bg-surface p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${eticheta.clasa}`}>
          {eticheta.eticheta}
        </span>
        <span className="tabular text-[13px] text-ink-soft">
          {formateazaSuma(cerere.sumaCeruta)} · {cerere.luni} luni
        </span>
      </div>

      {cerere.explicatie ? (
        <p className="mt-2 whitespace-pre-line text-[13px] leading-[19px] text-ink-soft">
          {cerere.explicatie}
        </p>
      ) : null}

      {/* Firul ramane accesibil si dupa inchidere: acolo sta motivul scris de
          analist, iar bulina de necitit n-are cum sa se stinga daca omul n-are
          unde deschide firul. */}
      <div className="mt-3">
        <DiscutieDrawer
          idCerere={cerere.id}
          mesaje={mesaje}
          necitite={cerere.mesajeNecitite}
          deschisInitial={discutieDeschisa}
        />
      </div>
    </section>
  );
}

function Oferta({
  cerere,
  conturi,
  mesaje,
  contract,
  discutieDeschisa,
}: {
  cerere: CerereCredit;
  conturi: ContBancar[];
  mesaje: MesajCerere[];
  contract: ContractCerere | null;
  discutieDeschisa: boolean;
}) {
  const router = useRouter();
  const [idCont, setIdCont] = useState(conturi[0]?.id ?? "");
  const [eroare, setEroare] = useState<string | null>(null);
  const [gata, setGata] = useState(false);
  const [seTrimite, startTransition] = useTransition();
  // Cat a parcurs clientul din contract, si daca a apasat „sunt de acord".
  // `null` = inca n-a acceptat; numarul se pastreaza in semnatura.
  const [derulatAcceptat, setDerulatAcceptat] = useState<number | null>(null);
  const contractAcceptat = derulatAcceptat !== null;

  // Conturile pot fi in valute diferite, dar creditul se acorda in RON: un
  // disbursement intr-un cont in EUR ar cere o conversie pe care nimeni n-a
  // cerut-o si la un curs pe care nimeni n-a vazut-o.
  const conturiRon = conturi.filter((cont) => cont.valuta === "RON");
  const expira = cerere.ofertaExpiraLa ? new Date(cerere.ofertaExpiraLa) : null;
  const expirata = expira !== null && expira.getTime() < Date.now();

  function semneaza() {
    if (!idCont) {
      setEroare("Alege contul în care intră banii.");
      return;
    }
    if (!contractAcceptat) {
      setEroare("Citește contractul și acceptă-l înainte de a semna.");
      return;
    }
    setEroare(null);

    startTransition(async () => {
      const rezultat = await acceptaOferta(cerere.id, idCont, true, derulatAcceptat ?? 0);
      if (rezultat.eroare) {
        setEroare(rezultat.eroare);
        return;
      }
      setGata(true);
      router.refresh();
    });
  }

  if (gata) {
    return (
      <section className="rounded-card bg-surface p-5 shadow-sm">
        <div className="flex items-center gap-3">
          <CheckCircle2 size={22} strokeWidth={1.75} aria-hidden className="text-success" />
          <p className="text-[15px] font-semibold text-ink">
            {formateazaSuma(cerere.sumaCeruta)} au intrat în cont
          </p>
        </div>
      </section>
    );
  }

  return (
    <section className="rounded-card border border-primary-600/30 bg-surface p-5 shadow-sm">
      <div className="flex items-center gap-2">
        <span className="rounded-full bg-success/10 px-2 py-0.5 text-[11px] font-medium text-success">
          Ofertă aprobată
        </span>
        <span className="text-[13px] text-ink-faint">{cerere.luni} luni</span>
      </div>

      <p className="tabular mt-2 text-[22px] font-bold leading-[28px] text-ink">
        {formateazaSuma(cerere.sumaCeruta)}
      </p>
      <p className="text-[13px] text-ink-faint">
        rată {cerere.rataLunara ? formateazaSuma(cerere.rataLunara) : "—"}
        {cerere.dae ? ` · DAE ${(cerere.dae * 100).toFixed(2).replace(".", ",")}%` : ""}
      </p>

      {expira ? (
        <p className={`mt-2 text-[12.5px] ${expirata ? "text-danger" : "text-ink-faint"}`}>
          {expirata
            ? "Oferta a expirat. Depune o cerere nouă."
            : `Valabilă până pe ${expira.toLocaleDateString("ro-RO", {
                day: "numeric",
                month: "long",
              })}`}
        </p>
      ) : null}

      {cerere.explicatie ? (
        <p className="mt-3 whitespace-pre-line text-[13px] leading-[19px] text-ink-soft">
          {cerere.explicatie}
        </p>
      ) : null}

      {eroare ? (
        <div className="mt-4">
          <Banda ton="eroare">{eroare}</Banda>
        </div>
      ) : null}

      {!expirata ? (
        <>
          {/* Contractul stă înaintea alegerii contului: e primul lucru de
              făcut, nu un detaliu de lângă buton. */}
          {contract ? (
            <div className="mt-4">
              <ContractDrawer
                contract={contract}
                acceptat={contractAcceptat}
                onAccepta={(derulat) => {
                  setDerulatAcceptat(derulat);
                  setEroare(null);
                }}
              />
            </div>
          ) : (
            <div className="mt-4">
              <Banda ton="eroare">
                Contractul nu s-a putut încărca. Reîmprospătează pagina — fără el nu se poate
                semna.
              </Banda>
            </div>
          )}

          <label className="mt-4 block text-[13px] text-ink-faint" htmlFor={`cont-${cerere.id}`}>
            Banii intră în
          </label>
          <select
            id={`cont-${cerere.id}`}
            value={idCont}
            onChange={(eveniment) => setIdCont(eveniment.target.value)}
            className="mt-1.5 h-12 w-full rounded-field border border-line bg-bg px-3 text-[15px] text-ink focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
          >
            {(conturiRon.length > 0 ? conturiRon : conturi).map((cont) => (
              <option key={cont.id} value={cont.id}>
                {cont.nume} · {cont.ibanMascat}
              </option>
            ))}
          </select>

          <Button
            className="mt-4 w-full"
            loading={seTrimite}
            disabled={!contractAcceptat}
            onClick={semneaza}
            iconaStanga={<PenLine size={18} strokeWidth={1.75} aria-hidden />}
          >
            Semnează și primește {formateazaSuma(cerere.sumaCeruta)}
          </Button>

          {!contractAcceptat ? (
            <p className="mt-2 text-center text-[12.5px] text-ink-faint">
              Deschide contractul de mai sus ca să poți semna.
            </p>
          ) : null}
        </>
      ) : null}

      {/* Firul si aici, nu doar in analiza: odata emisa oferta, clientul nu mai
          avea unde citi ce i-a scris banca, iar „Deschide discutia" din
          notificare nu deschidea nimic. */}
      <div className="mt-4">
        <DiscutieDrawer
          idCerere={cerere.id}
          mesaje={mesaje}
          necitite={cerere.mesajeNecitite}
          deschisInitial={discutieDeschisa}
        />
      </div>
    </section>
  );
}

/**
 * Un dosar care nu s-a terminat încă.
 *
 * Trei stări, cu trei mesaje diferite, fiindcă cer trei lucruri diferite de la
 * client: „se verifică" (nu face nimic), „un coleg se uită" (așteaptă), și
 * „așteaptă acte" (trebuie să acționeze). Un text unic pentru toate l-ar lăsa
 * pe ultimul să creadă că nu are nimic de făcut.
 *
 * Încărcarea se oferă în ambele stări de analiză, nu doar când actele sunt
 * cerute explicit: motorul poate cere singur o adeverință atunci când nu vede
 * niciun venit confirmat, iar până acum clientul n-avea unde s-o pună — 
 * `IncarcaAdeverinta` exista doar în wizard, deci se pierdea la ieșirea din el.
 */
function InAnaliza({
  cerere,
  mesaje,
  discutieDeschisa,
}: {
  cerere: CerereCredit;
  mesaje: MesajCerere[];
  discutieDeschisa: boolean;
}) {
  const asteaptaActe = cerere.status === "asteapta_documente";
  const manuala = cerere.status === "analiza_manuala";
  const poateIncarca = asteaptaActe || manuala;

  return (
    <section className="rounded-card bg-surface p-5 shadow-sm">
      <div className="flex items-start gap-3">
        {asteaptaActe ? (
          <FileUp size={20} strokeWidth={1.75} aria-hidden className="mt-0.5 text-warning" />
        ) : manuala ? (
          <FileSearch size={20} strokeWidth={1.75} aria-hidden className="mt-0.5 text-warning" />
        ) : (
          <Clock size={20} strokeWidth={1.75} aria-hidden className="mt-0.5 text-ink-faint" />
        )}
        <div className="min-w-0 flex-1">
          <p className="text-[15px] font-semibold text-ink">
            Cerere de {formateazaSuma(cerere.sumaCeruta)} · {cerere.luni} luni
          </p>
          <p className="mt-1 text-[13px] leading-[19px] text-ink-soft">
            {asteaptaActe
              ? "Mai avem nevoie de un document ca să mergem mai departe."
              : manuala
                ? "Un coleg se uită peste dosar. Primești răspunsul în cel mult două zile lucrătoare."
                : "Se verifică."}
          </p>

        </div>
      </div>

      <div className="mt-4 flex items-center gap-3">
        <DiscutieDrawer
          idCerere={cerere.id}
          mesaje={mesaje}
          necitite={cerere.mesajeNecitite}
          deschisInitial={discutieDeschisa}
        />
        {/* Retragerea doar aici: pe o oferta omul are ceva de semnat, iar
            ignorarea duce singura la 'expirata'. */}
        <RetrageCererea idCerere={cerere.id} />
      </div>

      {poateIncarca ? (
        <div className="mt-4 border-t border-line pt-4">
          <IncarcaAdeverinta idCerere={cerere.id} incastrat />
        </div>
      ) : null}
    </section>
  );
}
