"use client";

import { useRouter } from "next/navigation";
import { ArrowDownLeft, ArrowUpRight, Send } from "lucide-react";
import { useEffect, useRef, useState, useTransition, type FormEvent } from "react";
import { AvatarProfil } from "@/components/ui/avatar-profil";
import { Banda } from "@/components/ui/banda";
import type { MesajGrup } from "@/lib/data/grupuri";
import { trimiteMesaj } from "@/lib/actions/grupuri";
import { cn, etichetaZi, formateazaOra as ora } from "@/lib/utils";

/**
 * Conversatia din grup: mesajele existente si campul de scris.
 *
 * Mesajele vin randate de pe server; dupa trimitere se cere un refresh, deci
 * lista se reincarca prin acelasi drum (fara stare duplicata in client).
 */
export function ConversatieGrup({
  idGrup,
  mesaje,
}: {
  idGrup: number;
  mesaje: MesajGrup[];
}) {
  const router = useRouter();
  const [continut, setContinut] = useState("");
  const [eroare, setEroare] = useState<string | null>(null);
  const [seTrimite, startTransition] = useTransition();
  const sfarsit = useRef<HTMLDivElement>(null);

  // Conversatia se citeste de jos in sus: la fiecare mesaj nou coboram la capat.
  useEffect(() => {
    sfarsit.current?.scrollIntoView({ block: "end" });
  }, [mesaje.length]);

  function trimite() {
    const text = continut.trim();
    if (!text) return;

    setEroare(null);

    startTransition(async () => {
      const rezultat = await trimiteMesaj(idGrup, text);

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
    <section className="mt-8">
      <h2 className="text-lg font-semibold text-ink">Conversație</h2>

      {/* Conversatia ocupa aproape tot ecranul: un chat scurt s-ar citi ca o
          nota de subsol, nu ca locul unde se vorbeste. `min-h` tine panoul
          utilizabil si pe ecrane joase, unde 68vh ar insemna cateva randuri. */}
      <div className="mt-4 flex h-[68vh] min-h-[440px] flex-col gap-3 overflow-y-auto rounded-card bg-surface p-4 shadow-sm">
        {mesaje.length === 0 ? (
          <p className="my-8 text-center text-[15px] text-ink-faint">
            Niciun mesaj încă. Scrie primul.
          </p>
        ) : (
          mesaje.map((mesaj) => {
            const zi = etichetaZi(mesaj.creatLa);
            const zisNou = zi !== ziAnterioara;
            ziAnterioara = zi;

            // Anunturile de bani nu sunt replici intr-o discutie: nu au parte
            // (stanga/dreapta) si nu iau forma de bula. Centrate si colorate, ca
            // sa se vada dintr-o privire incotro s-a dus soldul comun: verde
            // cand intra, rosu cand iese.
            if (mesaj.tip !== "text") {
              const iese = mesaj.tip === "plata";
              const Sageata = iese ? ArrowUpRight : ArrowDownLeft;

              return (
                <div key={mesaj.id} className="flex flex-col gap-3">
                  {zisNou ? (
                    <p className="text-center text-[12.5px] text-ink-faint">{zi}</p>
                  ) : null}

                  <div className="flex justify-center">
                    <div
                      className={cn(
                        "flex max-w-[92%] items-center gap-2 rounded-card px-4 py-2.5",
                        iese ? "bg-danger/10" : "bg-success/10",
                      )}
                    >
                      <Sageata
                        size={16}
                        strokeWidth={2}
                        aria-hidden
                        className={cn(
                          "shrink-0",
                          iese ? "text-danger" : "text-success",
                        )}
                      />
                      <p
                        className={cn(
                          "text-[13px] font-medium leading-[18px]",
                          iese ? "text-danger" : "text-success",
                        )}
                      >
                        {mesaj.continut}{" "}
                        <span
                          className={cn(
                            "tabular font-normal",
                            iese ? "text-danger/70" : "text-success/70",
                          )}
                        >
                          · {ora(mesaj.creatLa)}
                        </span>
                      </p>
                    </div>
                  </div>
                </div>
              );
            }

            return (
              <div key={mesaj.id} className="flex flex-col gap-3">
                {zisNou ? (
                  <p className="text-center text-[12.5px] text-ink-faint">{zi}</p>
                ) : null}

                <div
                  className={cn(
                    "flex items-end gap-2",
                    mesaj.alMeu ? "flex-row-reverse" : "flex-row",
                  )}
                >
                  <span className="h-8 w-8 shrink-0">
                    <AvatarProfil
                      url={mesaj.autor?.avatarUrl ?? null}
                      nume={mesaj.autor?.nume ?? "Fost membru"}
                      marimeIcoana={14}
                    />
                  </span>

                  <div
                    className={cn(
                      "max-w-[78%] rounded-card px-4 py-2.5",
                      mesaj.alMeu
                        ? "rounded-br-md bg-primary-600 text-white"
                        : "rounded-bl-md bg-muted text-ink",
                    )}
                  >
                    {/* Numele apare la fiecare mesaj, si la ale mele: intr-un
                        grup de mai multi oameni, cine a scris conteaza mai mult
                        decat economia de un rand. */}
                    <p
                      className={cn(
                        "text-[12.5px] font-medium",
                        mesaj.alMeu ? "text-primary-100" : "text-primary-700",
                      )}
                    >
                      {mesaj.autor?.nume ?? "Fost membru"}
                    </p>

                    <p className="whitespace-pre-wrap break-words text-[15px] leading-[22px]">
                      {mesaj.continut}
                    </p>

                    <p
                      className={cn(
                        "tabular mt-1 text-[11px] leading-4",
                        mesaj.alMeu ? "text-primary-100" : "text-ink-faint",
                      )}
                    >
                      {ora(mesaj.creatLa)}
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
        <div className="mt-3">
          <Banda ton="eroare">{eroare}</Banda>
        </div>
      ) : null}

      <form
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          trimite();
        }}
        className="mt-3 flex items-end gap-2"
      >
        <label htmlFor="mesaj-grup" className="sr-only">
          Mesaj nou
        </label>

        <textarea
          id="mesaj-grup"
          rows={1}
          value={continut}
          onChange={(e) => setContinut(e.target.value)}
          onKeyDown={(e) => {
            // Enter trimite, Shift+Enter trece pe rand nou — ca in orice chat.
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              trimite();
            }
          }}
          maxLength={1000}
          placeholder="Scrie un mesaj…"
          className="max-h-32 min-h-[52px] flex-1 resize-none rounded-field border border-line bg-surface px-4 py-[15px] text-[15px] text-ink outline-none transition-[border-color,box-shadow] duration-150 ease-soft placeholder:text-ink-faint focus:border-primary-500 focus:ring-4 focus:ring-primary-500/12"
        />

        <button
          type="submit"
          aria-label="Trimite mesajul"
          disabled={seTrimite || !continut.trim()}
          className="flex h-[52px] w-[52px] shrink-0 items-center justify-center rounded-field bg-primary-600 text-white shadow-btn transition-[background-color,transform] duration-[180ms] ease-soft hover:bg-primary-700 active:scale-[0.98] disabled:cursor-not-allowed disabled:bg-primary-100 disabled:text-primary-300 disabled:shadow-none focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
        >
          <Send size={18} strokeWidth={1.75} aria-hidden />
        </button>
      </form>
    </section>
  );
}
