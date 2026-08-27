"use client";

import { useEffect, useState } from "react";
import {
  CheckCircle2,
  Clock,
  CreditCard,
  Loader2,
  Lock,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { Camp } from "@/components/ui/camp";
import { Drawer, DrawerContent, DrawerTrigger } from "@/components/ui/drawer";
import { useStarePlata } from "@/hooks/use-stare-plata";
import { obtineProdus } from "@/lib/data/produse";
import { formateazaSuma } from "@/lib/utils";
import { ProdusVizual } from "./produs-vizual";

/** 4111111111111111 -> "4111 1111 1111 1111", maxim 16 cifre. */
function formateazaNumarCard(valoare: string) {
  const cifre = valoare.replace(/\D/g, "").slice(0, 16);
  return (cifre.match(/.{1,4}/g) ?? []).join(" ");
}

/** 1225 -> "12/25", maxim 4 cifre. */
function formateazaExpirare(valoare: string) {
  const cifre = valoare.replace(/\D/g, "").slice(0, 4);
  if (cifre.length <= 2) return cifre;
  return `${cifre.slice(0, 2)}/${cifre.slice(2)}`;
}

function formularValid(date: {
  numarCard: string;
  numeCard: string;
  expirare: string;
  cvv: string;
}) {
  const cifreCard = date.numarCard.replace(/\D/g, "");

  return (
    cifreCard.length === 16 &&
    date.numeCard.trim().length >= 3 &&
    /^(0[1-9]|1[0-2])\/\d{2}$/.test(date.expirare) &&
    /^\d{3}$/.test(date.cvv)
  );
}

const FORM_INITIAL = { numarCard: "", numeCard: "", expirare: "", cvv: "" };

type Pas = "form" | "asteptare" | "aprobata" | "respinsa" | "expirata" | "esuata";

const TITLURI: Record<Pas, string> = {
  form: "Finalizează comanda",
  asteptare: "Confirmare plată",
  aprobata: "Plata a fost aprobată",
  respinsa: "Plata a fost respinsă",
  expirata: "Plata a expirat",
  esuata: "Plata nu a reușit",
};

/**
 * Drawer de cumparare: rezumatul produsului, formularul de card si asteptarea
 * confirmarii din aplicatia de banking.
 *
 * Nu cere nicio sesiune. Ca la orice comerciant, tot ce se da sunt datele
 * cardului; banca gaseste posesorul si il intreaba pe el, oricine ar fi cel de
 * la casa. Formularul nu decide nimic, dar nici POST /api/payments nu mai
 * decide mare lucru: de la 0046 acolo se afla doar cine e posesorul, iar cardul,
 * contul si soldul se verifica abia dupa ce el autorizeaza. Un card blocat sau
 * un cont fara bani se vede deci aici ca plata terminata in „esuata", cu motivul
 * venit prin Realtime, nu ca eroare in formular.
 *
 * Primeste doar slug-ul (nu produsul intreg): un obiect cu o componenta de
 * icoana nu poate trece ca prop dintr-o pagina server intr-un client
 * component, deci produsul se cauta aici, in client. Pretul trimis serverului
 * n-ar conta oricum — acolo se citeste tot din catalog, dupa acelasi slug.
 */
export function CumparaDrawer({ slug }: { slug: string }) {
  const produs = obtineProdus(slug);

  const [deschis, setDeschis] = useState(false);
  const [pas, setPas] = useState<Pas>("form");
  const [date, setDate] = useState(FORM_INITIAL);
  const [eroare, setEroare] = useState<string | null>(null);
  const [seTrimite, setSeTrimite] = useState(false);
  const [idPlata, setIdPlata] = useState<string | null>(null);
  const [expiraLa, setExpiraLa] = useState<string | null>(null);

  const { status, motiv } = useStarePlata(idPlata);

  // Raspunsul din aplicatia de banking ajunge aici, prin Realtime.
  useEffect(() => {
    if (!status || status === "PENDING_APPROVAL") return;

    if (status === "APPROVED") setPas("aprobata");
    else if (status === "DECLINED") setPas("respinsa");
    else if (status === "EXPIRED") setPas("expirata");
    else setPas("esuata");
  }, [status]);

  // Daca nimeni nu raspunde, cererea moare singura la expira_la. Serverul refuza
  // oricum aprobarea dupa acest moment; asta doar deblocheaza ecranul.
  useEffect(() => {
    if (pas !== "asteptare" || !expiraLa) return;

    const ramas = new Date(expiraLa).getTime() - Date.now();
    const cronometru = setTimeout(() => setPas("expirata"), Math.max(ramas, 0));

    return () => clearTimeout(cronometru);
  }, [pas, expiraLa]);

  if (!produs) return null;

  function reseteaza(v: boolean) {
    setDeschis(v);

    if (!v) {
      setPas("form");
      setDate(FORM_INITIAL);
      setEroare(null);
      setSeTrimite(false);
      setIdPlata(null);
      setExpiraLa(null);
    }
  }

  async function plateste() {
    setEroare(null);

    if (!formularValid(date)) {
      setEroare("Verifică datele cardului — par incomplete sau greșite.");
      return;
    }

    setSeTrimite(true);

    try {
      const raspuns = await fetch("/api/payments", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          slug,
          numarCard: date.numarCard,
          dataExpirare: date.expirare,
          cvv: date.cvv,
        }),
      });

      const rezultat = (await raspuns.json().catch(() => null)) as {
        paymentId?: string;
        expiraLa?: string | null;
        eroare?: string;
      } | null;

      if (!raspuns.ok || !rezultat?.paymentId) {
        setEroare(rezultat?.eroare ?? "Nu am putut porni plata. Încearcă din nou.");
        return;
      }

      // Datele cardului nu mai stau in memoria paginii dupa ce si-au facut treaba.
      setDate(FORM_INITIAL);
      setExpiraLa(rezultat.expiraLa ?? null);
      setIdPlata(rezultat.paymentId);
      setPas("asteptare");
    } catch {
      setEroare("Nu am putut porni plata. Verifică conexiunea.");
    } finally {
      setSeTrimite(false);
    }
  }

  const final = pas !== "form" && pas !== "asteptare";

  return (
    <Drawer open={deschis} onOpenChange={reseteaza}>
      <DrawerTrigger className="flex h-[52px] w-full items-center justify-center gap-2 rounded-field bg-primary-600 text-[15px] font-semibold text-white shadow-btn transition-colors duration-150 ease-soft hover:bg-primary-700 active:scale-[0.98] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25">
        <CreditCard size={18} strokeWidth={1.75} aria-hidden />
        Cumpără acum
      </DrawerTrigger>

      <DrawerContent
        title={TITLURI[pas]}
        description={
          pas === "form"
            ? "Rezumatul comenzii și datele cardului."
            : pas === "asteptare"
              ? "Așteptăm confirmarea posesorului cardului."
              : "Rezultatul plății."
        }
        className="h-[92vh]"
        // Cat timp asteptam raspunsul, „X"-ul ar sugera ca plata se poate anula
        // de aici — dar ea traieste mai departe pe server pana expira.
        cuInchidere={pas !== "asteptare"}
        footer={
          pas === "form" ? (
            <Button className="w-full" loading={seTrimite} onClick={plateste}>
              {seTrimite ? "Se trimite cererea…" : `Plătește ${formateazaSuma(produs.pret)}`}
            </Button>
          ) : pas === "asteptare" ? null : (
            <Button className="w-full" onClick={() => reseteaza(false)}>
              Închide
            </Button>
          )
        }
      >
        {pas === "asteptare" ? (
          <div className="flex flex-col items-center gap-3 py-10 text-center">
            <span className="flex items-center gap-1.5 text-[13px] text-ink-faint">
              <ShieldCheck size={14} strokeWidth={1.75} aria-hidden />
              Galaxy Shop
            </span>

            <p className="tabular text-[30px] font-bold leading-[36px] text-ink">
              {formateazaSuma(produs.pret)}
            </p>

            <p className="mt-2 flex items-center gap-2 text-[14px] font-medium text-ink-soft">
              <Loader2 size={18} strokeWidth={1.75} className="animate-spin" aria-hidden />
              Se așteaptă confirmarea din aplicația Galaxy Bank…
            </p>

            <p className="max-w-xs text-[12.5px] leading-[18px] text-ink-faint">
              Am trimis cererea de autorizare posesorului cardului. Plata se face doar
              după ce el apasă „Confirmă” în aplicație.
            </p>
          </div>
        ) : final ? (
          <div className="flex flex-col items-center gap-3 py-10 text-center">
            {pas === "aprobata" ? (
              <CheckCircle2 size={48} strokeWidth={1.5} className="animate-pop text-success" />
            ) : pas === "expirata" ? (
              <Clock size={48} strokeWidth={1.5} className="animate-pop text-ink-faint" />
            ) : (
              <XCircle size={48} strokeWidth={1.5} className="animate-pop text-danger" />
            )}

            <p className="text-[16px] font-semibold text-ink">{TITLURI[pas]}</p>
            <p className="tabular text-[20px] font-semibold text-primary-600">
              {formateazaSuma(produs.pret)}
            </p>
            <p className="max-w-xs text-[13.5px] leading-[19px] text-ink-faint">
              {pas === "aprobata"
                ? `${produs.nume} — plata a fost confirmată cu succes.`
                : pas === "respinsa"
                  ? "Cererea a fost respinsă din aplicația de banking. Nu s-a mișcat niciun ban."
                  : pas === "expirata"
                    ? "Nimeni nu a confirmat la timp. Poți relua comanda."
                    : (motiv ?? "Plata nu a putut fi procesată.")}
            </p>
          </div>
        ) : (
          <div className="flex flex-col gap-5">
            <div className="flex items-center gap-3 rounded-card border border-line p-3">
              <ProdusVizual produs={produs} marime="mic" />
              <div className="min-w-0 flex-1">
                <p className="truncate text-[14.5px] font-semibold text-ink">{produs.nume}</p>
                <p className="tabular text-[13.5px] text-ink-faint">
                  {formateazaSuma(produs.pret)}
                </p>
              </div>
            </div>

            {eroare ? <Banda ton="eroare">{eroare}</Banda> : null}

            <Banda ton="info">
              Plata se face cu un card Galaxy Bank. Posesorul cardului primește cererea în
              aplicație și o confirmă de acolo.
            </Banda>

            <div className="flex flex-col gap-4">
              <Camp
                eticheta="Număr card"
                icoana={CreditCard}
                inputMode="numeric"
                autoComplete="off"
                placeholder="1234 5678 9012 3456"
                value={date.numarCard}
                onChange={(e) =>
                  setDate((d) => ({ ...d, numarCard: formateazaNumarCard(e.target.value) }))
                }
              />

              <Camp
                eticheta="Nume pe card"
                placeholder="ION POPESCU"
                autoComplete="off"
                value={date.numeCard}
                onChange={(e) =>
                  setDate((d) => ({ ...d, numeCard: e.target.value.toUpperCase() }))
                }
              />

              <div className="grid grid-cols-2 gap-4">
                <Camp
                  eticheta="Expiră (LL/AA)"
                  inputMode="numeric"
                  autoComplete="off"
                  placeholder="12/28"
                  value={date.expirare}
                  onChange={(e) =>
                    setDate((d) => ({ ...d, expirare: formateazaExpirare(e.target.value) }))
                  }
                />

                <Camp
                  eticheta="CVV"
                  icoana={Lock}
                  inputMode="numeric"
                  autoComplete="off"
                  placeholder="123"
                  value={date.cvv}
                  onChange={(e) =>
                    setDate((d) => ({ ...d, cvv: e.target.value.replace(/\D/g, "").slice(0, 3) }))
                  }
                />
              </div>
            </div>

            <p className="flex items-center gap-1.5 text-[12px] text-ink-faint">
              <Lock size={13} strokeWidth={1.75} aria-hidden />
              CVV-ul se verifică o singură dată și nu se salvează nicăieri.
            </p>
          </div>
        )}
      </DrawerContent>
    </Drawer>
  );
}
