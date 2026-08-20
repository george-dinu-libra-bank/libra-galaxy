"use client";

import { useRouter } from "next/navigation";
import { Check, Copy, Plus } from "lucide-react";
import { useState, useTransition } from "react";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { Camp } from "@/components/ui/camp";
import { Drawer, DrawerContent, DrawerTrigger } from "@/components/ui/drawer";
import { creeazaGrup } from "@/lib/actions/grupuri";

/** Sugestii uzuale, ca sa nu ramana campul gol la prima deschidere. */
const SUGESTII = ["Colegi", "Familie", "Vacanță", "Chirie"];

type GrupNou = { id: number; nume: string; token: string };

/**
 * Crearea unui grup nou. Codul de acces se genereaza in baza de date; dupa
 * creare drawerul arata codul si linkul de invitatie, ca sa poata fi trimise
 * imediat celorlalti.
 */
export function CreeazaGrupDrawer() {
  const router = useRouter();
  const [deschis, setDeschis] = useState(false);
  const [nume, setNume] = useState("");
  const [creat, setCreat] = useState<GrupNou | null>(null);
  const [copiat, setCopiat] = useState(false);
  const [eroare, setEroare] = useState<string | null>(null);
  const [seTrimite, startTransition] = useTransition();

  function trimite() {
    setEroare(null);

    startTransition(async () => {
      const rezultat = await creeazaGrup(nume);

      if (rezultat.eroare || !rezultat.id || !rezultat.token) {
        setEroare(rezultat.eroare ?? "Nu am putut crea grupul. Încearcă din nou.");
        return;
      }

      setCreat({ id: rezultat.id, nume: rezultat.nume ?? nume, token: rezultat.token });
      router.refresh();
    });
  }

  async function copiazaLink() {
    if (!creat) return;

    try {
      await navigator.clipboard.writeText(
        `${window.location.origin}/grupuri?token=${creat.token}`,
      );
      setCopiat(true);
      setTimeout(() => setCopiat(false), 2000);
    } catch {
      setEroare("Nu am putut copia linkul. Selectează codul manual.");
    }
  }

  return (
    <Drawer
      open={deschis}
      onOpenChange={(valoare) => {
        setDeschis(valoare);

        if (!valoare) {
          // Inchiderea reseteaza tot: urmatoarea deschidere porneste curata.
          setNume("");
          setCreat(null);
          setEroare(null);
        }
      }}
    >
      <DrawerTrigger
        aria-label="Creează un grup nou"
        className="flex h-9 items-center gap-1.5 rounded-full bg-primary-600 px-3 text-[13px] font-semibold text-white shadow-btn transition-colors hover:bg-primary-700 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
      >
        <Plus size={16} strokeWidth={2} aria-hidden />
        Grup nou
      </DrawerTrigger>

      <DrawerContent
        title={creat ? "Grupul e gata" : "Creează un grup"}
        description={
          creat
            ? "Trimite codul celor pe care vrei să îi ai în grup."
            : "Primești un cod de invitație pe care îl poți trimite mai departe."
        }
        footer={
          creat ? (
            <Button className="w-full" onClick={() => router.push(`/grupuri/${creat.id}`)}>
              Deschide grupul
            </Button>
          ) : (
            <Button className="w-full" loading={seTrimite} onClick={trimite}>
              Creează grupul
            </Button>
          )
        }
      >
        <div className="flex flex-col gap-4">
          {eroare ? <Banda ton="eroare">{eroare}</Banda> : null}

          {creat ? (
            <>
              <p className="text-[15px] leading-[22px] text-ink-soft">
                <span className="font-semibold text-ink">{creat.nume}</span> a fost creat.
                Oricine are codul de mai jos poate intra.
              </p>

              <div className="rounded-card bg-primary-50 px-4 py-5 text-center">
                <p className="text-[12.5px] text-primary-700">Cod de acces</p>
                <p className="tabular mt-1 text-[22px] font-bold tracking-[0.12em] text-primary-900">
                  {creat.token}
                </p>
              </div>

              <Button
                varianta="secondary"
                className="w-full"
                onClick={copiazaLink}
                iconaStanga={
                  copiat ? (
                    <Check size={18} strokeWidth={1.75} aria-hidden />
                  ) : (
                    <Copy size={18} strokeWidth={1.75} aria-hidden />
                  )
                }
              >
                {copiat ? "Link copiat" : "Copiază linkul de invitație"}
              </Button>
            </>
          ) : (
            <>
              <Camp
                eticheta="Numele grupului"
                placeholder="Ex. Colegi de apartament"
                value={nume}
                onChange={(e) => setNume(e.target.value)}
                maxLength={60}
                ajutor="Îl văd toți cei care intră în grup."
              />

              <div className="flex flex-wrap gap-2">
                {SUGESTII.map((sugestie) => (
                  <button
                    key={sugestie}
                    type="button"
                    onClick={() => setNume(sugestie)}
                    className="rounded-full border border-line bg-surface px-3 py-1.5 text-[13px] text-ink-soft transition-colors hover:border-primary-300 hover:bg-primary-50 hover:text-primary-700 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
                  >
                    {sugestie}
                  </button>
                ))}
              </div>
            </>
          )}
        </div>
      </DrawerContent>
    </Drawer>
  );
}
