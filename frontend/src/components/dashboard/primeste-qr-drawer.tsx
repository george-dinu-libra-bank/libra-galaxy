"use client";

import { useEffect, useState } from "react";
import QRCode from "qrcode";
import {
  Check,
  ChevronLeft,
  Copy,
  Download,
  FileText,
  QrCode,
  Share2,
} from "lucide-react";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { Camp } from "@/components/ui/camp";
import { Drawer, DrawerContent, DrawerTrigger } from "@/components/ui/drawer";
import type { ContBancar } from "@/lib/data/conturi";
import { construiesteLinkPlata } from "@/lib/qr-plata";
import { cn, formateazaIban, formateazaSuma } from "@/lib/utils";

/** Numele sub care pleaca imaginea la descarcare sau la distribuire. */
const NUME_FISIER = "cerere-plata.png";

/**
 * Codul QR prin care ceri bani.
 *
 * Doi pasi, in ordinea in care se gandeste omul: intai spui in ce cont vrei
 * banii, cat si de ce, si abia apoi apesi „Generează codul". Codul e ultimul
 * lucru care apare, nu ceva ce pulseaza sub degete cat completezi.
 *
 * In cod sta un link catre propriul ecran de transfer, cu cele trei valori puse
 * ca parametri (lib/qr-plata.ts). Cine il scaneaza deschide aplicatia cu totul
 * completat si nu mai are de facut decat sa confirme.
 *
 * Codul nu se salveaza nicaieri — nici in baza, nici in storage. E desenat din
 * link, deci se poate reface oricand, identic; ce ramane la om e imaginea, daca
 * o descarca sau o trimite mai departe.
 */
export function PrimesteQrDrawer({
  conturi,
  numeUtilizator,
  className,
}: {
  conturi: ContBancar[];
  numeUtilizator: string;
  /** Stilul dalei din „Actiuni rapide", dat de ecran ca sa arate ca surorile ei. */
  className?: string;
}) {
  const [deschis, setDeschis] = useState(false);
  const [pas, setPas] = useState<"date" | "cod">("date");
  const [idCont, setIdCont] = useState<string | null>(conturi[0]?.id ?? null);
  const [suma, setSuma] = useState("");
  const [detalii, setDetalii] = useState("");
  const [imagine, setImagine] = useState<string | null>(null);
  const [fisier, setFisier] = useState<File | null>(null);
  const [eroare, setEroare] = useState<string | null>(null);
  const [copiat, setCopiat] = useState(false);

  // Adresa publica difera intre laptop, telefon si productie, iar codul e citit
  // de camera altui telefon: linkul trebuie sa fie absolut. `window` exista abia
  // in browser, deci se citeste dupa montare.
  const [origine, setOrigine] = useState("");

  useEffect(() => setOrigine(window.location.origin), []);

  const cont = conturi.find((c) => c.id === idCont) ?? null;
  const sumaNumar = Number(suma.replace(",", "."));
  const sumaCeruta = Number.isFinite(sumaNumar) && sumaNumar > 0 ? sumaNumar : null;
  const sumaGresita = suma.trim().length > 0 && sumaCeruta === null;

  const link =
    cont && origine
      ? construiesteLinkPlata(origine, {
          iban: cont.iban,
          suma: sumaCeruta,
          detalii: detalii.trim() || null,
        })
      : "";

  // Codul se deseneaza abia la pasul lui, din linkul deja compus.
  useEffect(() => {
    if (pas !== "cod" || !link) return;

    let valabil = true;

    QRCode.toDataURL(link, {
      width: 512,
      margin: 1,
      errorCorrectionLevel: "M",
      color: { dark: "#0f172a", light: "#ffffff" },
    })
      .then(async (dataUrl) => {
        if (!valabil) return;
        setImagine(dataUrl);

        // Fisierul se pregateste din timp, nu la apasarea butonului: pe iOS,
        // `navigator.share` cere sa fie chemat din gestul utilizatorului, iar un
        // `await` inaintea lui rupe lantul si sistemul refuza distribuirea.
        try {
          const blob = await (await fetch(dataUrl)).blob();
          if (valabil) setFisier(new File([blob], NUME_FISIER, { type: "image/png" }));
        } catch {
          if (valabil) setFisier(null);
        }
      })
      .catch(() => {
        if (!valabil) return;
        setImagine(null);
        setFisier(null);
        setEroare("Nu am putut genera codul QR. Încearcă din nou.");
      });

    return () => {
      valabil = false;
    };
  }, [pas, link]);

  function inchide() {
    setDeschis(false);
    setPas("date");
    setIdCont(conturi[0]?.id ?? null);
    setSuma("");
    setDetalii("");
    setImagine(null);
    setFisier(null);
    setEroare(null);
    setCopiat(false);
  }

  function inapoiLaDate() {
    setPas("date");
    setImagine(null);
    setFisier(null);
    setEroare(null);
    setCopiat(false);
  }

  /** Textul care insoteste imaginea in WhatsApp, mail sau oriunde ajunge. */
  function mesaj() {
    const cine = numeUtilizator.trim() || "Cineva";
    const cat = sumaCeruta ? ` ${formateazaSuma(sumaCeruta, cont?.valuta ?? "RON")}` : "";
    const motiv = detalii.trim() ? ` pentru „${detalii.trim()}"` : "";
    return `${cine} îți cere${cat}${motiv} prin Galaxy Bank.`;
  }

  async function copiaza() {
    try {
      await navigator.clipboard.writeText(link);
      setCopiat(true);
      setTimeout(() => setCopiat(false), 2000);
    } catch {
      setEroare("Nu am putut copia linkul. Trimite codul ca imagine.");
    }
  }

  async function distribuie() {
    // Trei trepte, in ordinea a cat de bine arata rezultatul: imaginea plus
    // text (telefoane), doar linkul (browsere care stiu sa distribuie, dar nu
    // fisiere), copierea linkului (desktop).
    const text = `${mesaj()}\n${link}`;

    try {
      if (fisier && navigator.canShare?.({ files: [fisier] })) {
        await navigator.share({ files: [fisier], title: "Cerere de plată", text });
        return;
      }

      if (navigator.share) {
        await navigator.share({ title: "Cerere de plată", text: mesaj(), url: link });
        return;
      }
    } catch (exc) {
      // Anularea din foaia de distribuire nu e o eroare de aratat.
      if (exc instanceof Error && exc.name === "AbortError") return;
      setEroare("Nu am putut deschide meniul de distribuire. Copiază linkul.");
      return;
    }

    await copiaza();
  }

  return (
    <Drawer open={deschis} onOpenChange={(valoare) => (valoare ? setDeschis(true) : inchide())}>
      <DrawerTrigger aria-label="Primește bani prin cod QR" className={className}>
        <QrCode size={22} strokeWidth={1.75} aria-hidden className="text-primary-600" />
        <span className="text-center text-xs leading-4 text-ink-soft">Primește</span>
      </DrawerTrigger>

      <DrawerContent
        title={pas === "date" ? "Primește bani" : "Codul tău de plată"}
        description={
          pas === "date"
            ? "Alege contul în care vrei banii, cât ceri și pentru ce. Codul se generează la final."
            : "Arată-l sau trimite-l mai departe. Cine îl scanează ajunge cu totul completat în ecranul de transfer."
        }
        className="h-[90vh] max-h-[90vh]"
        footer={
          pas === "date" && conturi.length > 0 ? (
            <Button
              className="w-full"
              disabled={!cont || sumaGresita || !origine}
              onClick={() => {
                setEroare(null);
                setPas("cod");
              }}
              iconaStanga={<QrCode size={18} strokeWidth={1.75} aria-hidden />}
            >
              Generează codul QR
            </Button>
          ) : null
        }
      >
        <div className="flex flex-col gap-4">
          {eroare ? <Banda ton="eroare">{eroare}</Banda> : null}

          {conturi.length === 0 ? (
            <p className="rounded-card bg-muted p-6 text-center text-[15px] text-ink-faint">
              Nu ai niciun cont în care să primești bani.
            </p>
          ) : pas === "date" ? (
            <>
              <div className="flex flex-col gap-2">
                <span className="text-[13px] font-medium text-ink-soft">
                  În ce cont primești?
                </span>

                {conturi.map((c) => (
                  <button
                    key={c.id}
                    type="button"
                    onClick={() => setIdCont(c.id)}
                    aria-pressed={c.id === idCont}
                    className={cn(
                      "flex w-full items-center gap-3 rounded-field border px-4 py-3 text-left transition-colors duration-150 ease-soft",
                      "focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25",
                      c.id === idCont
                        ? "border-primary-500 bg-primary-500/12"
                        : "border-line bg-surface hover:bg-muted",
                    )}
                  >
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-[15px] font-medium text-ink">
                        {c.nume}
                      </span>
                      <span className="tabular flex items-center gap-2 text-[12.5px] text-ink-faint">
                        {c.ibanMascat}
                        <span className="rounded-full bg-muted px-1.5 py-0.5 text-[10.5px] font-semibold text-ink-soft">
                          {c.valuta}
                        </span>
                      </span>
                    </span>

                    {c.id === idCont ? (
                      <Check
                        size={18}
                        strokeWidth={1.75}
                        aria-hidden
                        className="shrink-0 text-primary-600"
                      />
                    ) : null}
                  </button>
                ))}
              </div>

              <Camp
                eticheta={`Sumă (${cont?.valuta ?? "RON"}, opțional)`}
                inputMode="decimal"
                placeholder="0,00"
                value={suma}
                onChange={(e) => setSuma(e.target.value.replace(/[^0-9,.]/g, ""))}
                eroare={sumaGresita ? "Introdu o sumă validă." : null}
                ajutor="Lasă gol dacă vrei ca plătitorul să aleagă suma."
              />

              <Camp
                eticheta="Motiv (opțional)"
                icoana={FileText}
                placeholder="Ex. Partea ta la cină"
                value={detalii}
                onChange={(e) => setDetalii(e.target.value)}
                maxLength={140}
              />
            </>
          ) : (
            <>
              <button
                type="button"
                onClick={inapoiLaDate}
                className="-ml-1 flex items-center gap-1 self-start rounded-field px-1 py-1 text-[13px] font-medium text-primary-600 transition-colors hover:bg-primary-50 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
              >
                <ChevronLeft size={16} strokeWidth={2} aria-hidden />
                Modifică datele
              </button>

              <div className="flex flex-col items-center gap-3 rounded-card border border-line bg-surface p-5">
                {imagine ? (
                  // Codul e o imagine, nu un desen decorativ: are nevoie de text
                  // alternativ, iar IBAN-ul din el se vede si scris dedesubt.
                  <img
                    src={imagine}
                    alt={`Cod QR pentru plată către ${formateazaIban(cont?.iban ?? "")}`}
                    width={220}
                    height={220}
                    className="h-[220px] w-[220px] rounded-[14px]"
                  />
                ) : (
                  <div className="h-[220px] w-[220px] animate-pulse rounded-[14px] bg-muted" />
                )}

                {sumaCeruta ? (
                  <p className="text-[17px] font-bold text-ink">
                    {formateazaSuma(sumaCeruta, cont?.valuta ?? "RON")}
                  </p>
                ) : (
                  <p className="text-[13px] text-ink-faint">
                    Fără sumă fixă — o alege plătitorul.
                  </p>
                )}

                {detalii.trim() ? (
                  <p className="text-center text-[13px] text-ink-soft">„{detalii.trim()}"</p>
                ) : null}

                <p className="tabular text-center text-[12.5px] leading-4 text-ink-faint">
                  {formateazaIban(cont?.iban ?? "")}
                </p>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <Button
                  varianta="secondary"
                  marime="sm"
                  className="w-full"
                  iconaStanga={<Share2 size={16} strokeWidth={1.75} aria-hidden />}
                  onClick={distribuie}
                  disabled={!imagine}
                >
                  Distribuie
                </Button>

                {/* Link de descarcare, nu buton: browserul stie singur ce sa
                    faca cu un `download` pe un data URL, iar pe telefon imaginea
                    ajunge in galerie. */}
                <a
                  href={imagine ?? undefined}
                  download={NUME_FISIER}
                  aria-disabled={!imagine}
                  className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-field border border-primary-100 bg-primary-50 px-4 text-sm font-semibold text-primary-700 transition-colors hover:bg-primary-100 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25 aria-disabled:pointer-events-none aria-disabled:opacity-50"
                >
                  <Download size={16} strokeWidth={1.75} aria-hidden />
                  Descarcă
                </a>
              </div>

              <Button
                varianta="ghost"
                marime="sm"
                className="w-full"
                iconaStanga={
                  copiat ? (
                    <Check size={16} strokeWidth={2} aria-hidden />
                  ) : (
                    <Copy size={16} strokeWidth={1.75} aria-hidden />
                  )
                }
                onClick={copiaza}
                disabled={!link}
              >
                {copiat ? "Link copiat" : "Copiază linkul"}
              </Button>
            </>
          )}
        </div>
      </DrawerContent>
    </Drawer>
  );
}
