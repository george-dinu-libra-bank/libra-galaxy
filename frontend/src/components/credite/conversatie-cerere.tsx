"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, useTransition } from "react";
import { FileText, Send } from "lucide-react";
import { Banda } from "@/components/ui/banda";
import { cn, etichetaZi, formateazaOra as ora } from "@/lib/utils";

/**
 * Firul de discutie de pe un dosar de credit.
 *
 * Aceeasi componenta pe ambele parti — clientul si analistul —, cu `parteaMea`
 * ca singura diferenta. Doua copii ar diverge la primul bug reparat in una din
 * ele (REGULI.md #2), iar aici bug-ul ar insemna ca un om nu-si vede raspunsul.
 *
 * Mesajele vin randate de pe server; dupa trimitere se cere un refresh, deci
 * lista se reincarca prin acelasi drum, fara stare duplicata in client. Acelasi
 * tipar ca la conversatia de grup (components/grupuri/conversatie-grup.tsx).
 */

export type MesajFir = {
  id: string;
  autor: "client" | "analist" | "sistem";
  text: string;
  id_document: string | null;
  creat_la: string;
};

const NUME_AUTOR: Record<MesajFir["autor"], string> = {
  client: "Tu",
  analist: "Banca",
  sistem: "Automat",
};

export function ConversatieCerere({
  mesaje,
  parteaMea,
  trimite,
  eticheta = "Discuție cu banca",
  doarCitire = false,
}: {
  mesaje: MesajFir[];
  /** Cine se uita: bulele lui stau in dreapta. */
  parteaMea: "client" | "analist";
  /** Actiunea de server care scrie mesajul. Difera intre client si administrare. */
  trimite: (text: string) => Promise<{ eroare?: string }>;
  eticheta?: string;
  /** Firul se citeste, dar nu se mai scrie — dosar inchis. Caseta dispare de
   * tot: lasata acolo cu un `trimite` care refuza, omul scrie tot mesajul si
   * afla abia dupa ce apasa. */
  doarCitire?: boolean;
}) {
  const router = useRouter();
  const [continut, setContinut] = useState("");
  const [eroare, setEroare] = useState<string | null>(null);
  const [seTrimite, startTransition] = useTransition();
  const sfarsit = useRef<HTMLDivElement>(null);

  // Firul se citeste de jos in sus: la fiecare mesaj nou coboram la capat.
  useEffect(() => {
    sfarsit.current?.scrollIntoView({ block: "end" });
  }, [mesaje.length]);

  function trimiteMesajul() {
    const text = continut.trim();
    if (!text) return;

    setEroare(null);
    startTransition(async () => {
      const rezultat = await trimite(text);
      if (rezultat.eroare) {
        setEroare(rezultat.eroare);
        return;
      }
      setContinut("");
      router.refresh();
    });
  }

  let ziAnterioara = "";

  return (
    <section className="flex flex-col">
      <p className="text-[12px] font-semibold text-ink">{eticheta}</p>

      <div
        role="log"
        aria-live="polite"
        aria-label={eticheta}
        className="mt-2 flex max-h-72 flex-col gap-3 overflow-y-auto rounded-field bg-muted/60 p-3"
      >
        {mesaje.length === 0 ? (
          <p className="py-4 text-center text-[13px] text-ink-faint">
            Niciun mesaj încă.
          </p>
        ) : (
          mesaje.map((mesaj) => {
            const zi = etichetaZi(mesaj.creat_la);
            const zisNou = zi !== ziAnterioara;
            ziAnterioara = zi;

            const alMeu = mesaj.autor === parteaMea;

            return (
              <div key={mesaj.id} className="flex flex-col gap-2">
                {zisNou ? (
                  <p className="text-center text-[11.5px] text-ink-faint">{zi}</p>
                ) : null}

                <div className={cn("flex", alMeu ? "justify-end" : "justify-start")}>
                  <div
                    className={cn(
                      "max-w-[85%] rounded-card px-3.5 py-2.5",
                      alMeu
                        ? "bg-primary-600 text-white"
                        : "bg-surface text-ink shadow-sm",
                    )}
                  >
                    {!alMeu ? (
                      <p
                        className={cn(
                          "text-[11px] font-semibold",
                          mesaj.autor === "sistem" ? "text-ink-faint" : "text-primary-700",
                        )}
                      >
                        {NUME_AUTOR[mesaj.autor]}
                      </p>
                    ) : null}

                    <p className="whitespace-pre-line text-[13px] leading-[19px]">
                      {/* Mesajele de document poarta o iconita, ca sa se vada
                          dintr-o privire ca acolo a venit un fisier — firul e si
                          cronologia dosarului, nu doar o discutie. */}
                      {mesaj.id_document ? (
                        <FileText
                          size={13}
                          strokeWidth={2}
                          aria-hidden
                          className="mr-1.5 inline-block align-[-2px]"
                        />
                      ) : null}
                      {mesaj.text}
                    </p>

                    <p
                      className={cn(
                        "mt-1 text-right text-[10.5px] tabular",
                        alMeu ? "text-white/70" : "text-ink-faint",
                      )}
                    >
                      {ora(mesaj.creat_la)}
                    </p>
                  </div>
                </div>
              </div>
            );
          })
        )}
        <div ref={sfarsit} />
      </div>

      {eroare ? (
        <div className="mt-2">
          <Banda ton="eroare">{eroare}</Banda>
        </div>
      ) : null}

      {doarCitire ? null : (
      <div className="mt-2 flex items-end gap-2">
        <textarea
          value={continut}
          onChange={(eveniment) => setContinut(eveniment.target.value)}
          onKeyDown={(eveniment) => {
            // Enter trimite, Shift+Enter face rand nou — cum se asteapta oricine
            // care a mai scris intr-un chat.
            if (eveniment.key === "Enter" && !eveniment.shiftKey) {
              eveniment.preventDefault();
              trimiteMesajul();
            }
          }}
          rows={2}
          maxLength={2000}
          placeholder="Scrie un mesaj…"
          aria-label="Mesaj"
          className="min-h-[44px] flex-1 resize-none rounded-field border border-line bg-surface px-3 py-2.5 text-[13px] leading-[19px] text-ink placeholder:text-ink-faint focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
        />
        <button
          type="button"
          onClick={trimiteMesajul}
          disabled={seTrimite || !continut.trim()}
          aria-label="Trimite mesajul"
          className="flex h-[44px] w-[44px] shrink-0 items-center justify-center rounded-field bg-primary-600 text-white transition-colors hover:bg-primary-700 disabled:bg-primary-100 disabled:text-primary-300 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
        >
          <Send size={17} strokeWidth={1.75} aria-hidden />
        </button>
      </div>
      )}
    </section>
  );
}
