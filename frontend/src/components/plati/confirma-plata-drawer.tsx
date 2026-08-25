"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { CheckCircle2, Clock, CreditCard, Store, XCircle } from "lucide-react";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { Drawer, DrawerContent } from "@/components/ui/drawer";
import { usePlatiInAsteptare } from "@/hooks/use-plati-in-asteptare";
import type { PlataInAsteptare } from "@/lib/plati";
import { formateazaSuma } from "@/lib/utils";

type Pas = "intreaba" | "aprobata" | "respinsa" | "expirata" | "esuata";

const TITLURI: Record<Pas, string> = {
  intreaba: "Confirmă plata",
  aprobata: "Plată aprobată",
  respinsa: "Plată respinsă",
  expirata: "Plată expirată",
  esuata: "Plata nu a putut fi făcută",
};

/** 92 -> "1:32" */
function formateazaRamas(secunde: number) {
  const minute = Math.floor(secunde / 60);
  return `${minute}:${String(secunde % 60).padStart(2, "0")}`;
}

/**
 * Drawerul prin care utilizatorul confirma o plata ceruta de un comerciant.
 *
 * Butoanele nu ating niciodata baza de date direct: trec prin
 * /api/payments/approve si /decline, unde se reverifica proprietarul, starea,
 * expirarea, cardul si fondurile. Aici raman doar starile de interfata.
 */
export function ConfirmaPlataDrawer({
  idUtilizator,
  initiale,
}: {
  idUtilizator: string;
  initiale: PlataInAsteptare[];
}) {
  const router = useRouter();
  const { plati, elimina } = usePlatiInAsteptare(idUtilizator, initiale);

  // Plata afisata se tine separat de coada: cand raspunsul soseste, randul iese
  // din coada, dar drawerul trebuie sa mai stea o clipa pe confirmare.
  const [activa, setActiva] = useState<PlataInAsteptare | null>(null);
  const [pas, setPas] = useState<Pas>("intreaba");
  const [seTrimite, setSeTrimite] = useState<"aproba" | "respinge" | null>(null);
  const [eroare, setEroare] = useState<string | null>(null);
  const [ramas, setRamas] = useState(0);

  // Prima plata din coada urca in drawer.
  useEffect(() => {
    if (activa || plati.length === 0) return;

    setActiva(plati[0]);
    setPas("intreaba");
    setEroare(null);
    setSeTrimite(null);
  }, [plati, activa]);

  // Numaratoarea inversa pana la expira_la. Serverul refuza oricum o plata
  // expirata; asta e doar ca ecranul sa nu ramana blocat pe o intrebare moarta.
  useEffect(() => {
    const expiraLa = activa?.expiraLa;

    if (!expiraLa || pas !== "intreaba") return;

    function bate() {
      const secunde = Math.max(
        0,
        Math.ceil((new Date(expiraLa!).getTime() - Date.now()) / 1000),
      );

      setRamas(secunde);

      if (secunde === 0) setPas("expirata");
    }

    bate();
    const cronometru = setInterval(bate, 1000);

    return () => clearInterval(cronometru);
  }, [activa, pas]);

  const inchide = useCallback(() => {
    // Scoasa din coada si la inchidere: altfel drawerul s-ar redeschide imediat.
    // Plata ramane PENDING_APPROVAL pana expira — doar intrebarea a fost amanata.
    if (activa) elimina(activa.id);
    setActiva(null);
  }, [activa, elimina]);

  async function raspunde(actiune: "aproba" | "respinge") {
    if (!activa || seTrimite) return;

    setSeTrimite(actiune);
    setEroare(null);

    try {
      const raspuns = await fetch(
        actiune === "aproba" ? "/api/payments/approve" : "/api/payments/decline",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ paymentId: activa.id }),
        },
      );

      const date = (await raspuns.json().catch(() => null)) as {
        status?: string;
        motiv?: string | null;
        eroare?: string;
      } | null;

      if (!raspuns.ok) {
        setEroare(date?.eroare ?? "Nu am putut trimite răspunsul. Încearcă din nou.");
        return;
      }

      elimina(activa.id);

      if (date?.status === "APPROVED") {
        setPas("aprobata");
        // Soldul si istoricul s-au schimbat: Server Components se recitesc.
        router.refresh();
      } else if (date?.status === "DECLINED") {
        setPas("respinsa");
      } else if (date?.status === "EXPIRED") {
        setPas("expirata");
      } else {
        setEroare(date?.motiv ?? "Plata nu a putut fi procesată.");
        setPas("esuata");
      }
    } catch {
      setEroare("Nu am putut trimite răspunsul. Verifică conexiunea.");
    } finally {
      setSeTrimite(null);
    }
  }

  if (!activa) return null;

  const final = pas !== "intreaba";

  return (
    <Drawer open onOpenChange={(deschis) => !deschis && inchide()}>
      <DrawerContent
        title={TITLURI[pas]}
        description={
          pas === "intreaba"
            ? "Un comerciant cere o plată de pe cardul tău."
            : "Rezultatul cererii de plată."
        }
        cuInchidere={pas === "intreaba"}
        footer={
          pas === "intreaba" ? (
            <div className="grid grid-cols-2 gap-3">
              <Button
                varianta="secondary"
                loading={seTrimite === "respinge"}
                disabled={seTrimite !== null}
                onClick={() => raspunde("respinge")}
              >
                Respinge
              </Button>
              <Button
                loading={seTrimite === "aproba"}
                disabled={seTrimite !== null}
                onClick={() => raspunde("aproba")}
              >
                Confirmă
              </Button>
            </div>
          ) : (
            <Button className="w-full" onClick={inchide}>
              Închide
            </Button>
          )
        }
      >
        {final ? (
          <div className="flex flex-col items-center gap-3 py-8 text-center">
            {pas === "aprobata" ? (
              <CheckCircle2 size={48} strokeWidth={1.5} className="animate-pop text-success" />
            ) : pas === "expirata" ? (
              <Clock size={48} strokeWidth={1.5} className="animate-pop text-ink-faint" />
            ) : (
              <XCircle size={48} strokeWidth={1.5} className="animate-pop text-danger" />
            )}

            <p className="text-[16px] font-semibold text-ink">{TITLURI[pas]}</p>
            <p className="tabular text-[20px] font-semibold text-primary-600">
              {formateazaSuma(activa.suma, activa.valuta)}
            </p>
            <p className="max-w-xs text-[13.5px] leading-[19px] text-ink-faint">
              {pas === "aprobata"
                ? `${activa.comerciant} a primit confirmarea. Suma a fost scoasă din ${activa.numeCont ?? "contul cardului"}.`
                : pas === "respinsa"
                  ? "Nu s-a mișcat niciun ban."
                  : pas === "expirata"
                    ? "Timpul de confirmare a trecut. Reia plata din magazin."
                    : (eroare ?? "Plata nu a putut fi procesată.")}
            </p>
          </div>
        ) : (
          <div className="flex flex-col gap-5">
            <div className="flex flex-col items-center gap-1.5 py-2 text-center">
              <span className="flex items-center gap-1.5 text-[13px] text-ink-faint">
                <Store size={14} strokeWidth={1.75} aria-hidden />
                {activa.comerciant}
              </span>
              <p className="tabular text-[30px] font-bold leading-[36px] text-ink">
                {formateazaSuma(activa.suma, activa.valuta)}
              </p>
              {activa.descriere ? (
                <p className="max-w-xs text-[13px] leading-[18px] text-ink-faint">
                  {activa.descriere}
                </p>
              ) : null}
            </div>

            <div className="flex items-center gap-3 rounded-card border border-line p-3">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-field bg-primary-50 text-primary-700">
                <CreditCard size={18} strokeWidth={1.75} aria-hidden />
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-[14.5px] font-semibold text-ink">
                  {activa.numeCont ?? `Card ${activa.cardMascat}`}
                </p>
                <p className="tabular text-[12.5px] text-ink-faint">
                  Card {activa.cardMascat}
                  {ramas > 0 ? ` · expiră în ${formateazaRamas(ramas)}` : " · se verifică…"}
                </p>
              </div>
            </div>

            {eroare ? <Banda ton="eroare">{eroare}</Banda> : null}
          </div>
        )}
      </DrawerContent>
    </Drawer>
  );
}
