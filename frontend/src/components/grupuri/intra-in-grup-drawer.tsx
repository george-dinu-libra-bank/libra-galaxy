"use client";

import { useRouter } from "next/navigation";
import { KeyRound, Users } from "lucide-react";
import { useEffect, useState, useTransition } from "react";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { Camp } from "@/components/ui/camp";
import { Drawer, DrawerContent, DrawerTrigger } from "@/components/ui/drawer";
import { intraInGrup, previzualizeazaGrup } from "@/lib/actions/grupuri";

type Previziune = { id: number; nume: string; membri: number; suntDeja: boolean };

/**
 * Intrarea intr-un grup cu cod de acces.
 *
 * Codul poate fi tastat sau poate veni din link (`/grupuri?token=...`), caz in
 * care drawerul se deschide singur si cauta grupul imediat. Inainte de a intra
 * se arata numele grupului si cati membri are, ca sa se vada unde intri.
 */
export function IntraInGrupDrawer({ tokenInitial }: { tokenInitial?: string }) {
  const router = useRouter();
  const [deschis, setDeschis] = useState(Boolean(tokenInitial));
  const [token, setToken] = useState(tokenInitial ?? "");
  const [previziune, setPreviziune] = useState<Previziune | null>(null);
  const [eroare, setEroare] = useState<string | null>(null);
  const [seLucreaza, startTransition] = useTransition();

  // Cod venit din link: cautam grupul fara sa mai astepte utilizatorul un click.
  useEffect(() => {
    if (!tokenInitial) return;

    startTransition(async () => {
      const rezultat = await previzualizeazaGrup(tokenInitial);

      if (rezultat.eroare || !rezultat.id) {
        setEroare(rezultat.eroare ?? "Nu am putut găsi grupul.");
        return;
      }

      setPreviziune({
        id: rezultat.id,
        nume: rezultat.nume ?? "Grup",
        membri: rezultat.membri ?? 1,
        suntDeja: Boolean(rezultat.suntDeja),
      });
    });
  }, [tokenInitial]);

  function cauta() {
    setEroare(null);

    startTransition(async () => {
      const rezultat = await previzualizeazaGrup(token);

      if (rezultat.eroare || !rezultat.id) {
        setEroare(rezultat.eroare ?? "Nu am putut găsi grupul.");
        return;
      }

      setPreviziune({
        id: rezultat.id,
        nume: rezultat.nume ?? "Grup",
        membri: rezultat.membri ?? 1,
        suntDeja: Boolean(rezultat.suntDeja),
      });
    });
  }

  function intra() {
    setEroare(null);

    startTransition(async () => {
      const rezultat = await intraInGrup(token);

      if (rezultat.eroare || !rezultat.id) {
        setEroare(rezultat.eroare ?? "Nu am putut intra în grup.");
        return;
      }

      setDeschis(false);
      // `replace`, nu `push`: linkul cu token nu are ce cauta in istoricul
      // browserului dupa ce a fost folosit.
      router.replace(`/grupuri/${rezultat.id}`);
      router.refresh();
    });
  }

  return (
    <Drawer
      open={deschis}
      onOpenChange={(valoare) => {
        setDeschis(valoare);

        if (!valoare) {
          setEroare(null);

          // Codul din link a fost consumat: scoatem parametrul din URL, ca un
          // refresh sa nu redeschida drawerul.
          if (tokenInitial) router.replace("/grupuri");
        }
      }}
    >
      <DrawerTrigger
        aria-label="Intră într-un grup cu cod"
        className="flex h-9 items-center gap-1.5 rounded-full bg-primary-50 px-3 text-[13px] font-semibold text-primary-700 transition-colors hover:bg-primary-100 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
      >
        <KeyRound size={16} strokeWidth={2} aria-hidden />
        Am un cod
      </DrawerTrigger>

      <DrawerContent
        title="Intră într-un grup"
        description="Ai nevoie de codul de acces sau de linkul primit de la cineva din grup."
        footer={
          previziune ? (
            previziune.suntDeja ? (
              <Button
                className="w-full"
                onClick={() => {
                  setDeschis(false);
                  router.push(`/grupuri/${previziune.id}`);
                }}
              >
                Deschide grupul
              </Button>
            ) : (
              <Button className="w-full" loading={seLucreaza} onClick={intra}>
                Intră în grup
              </Button>
            )
          ) : (
            <Button className="w-full" loading={seLucreaza} onClick={cauta}>
              Caută grupul
            </Button>
          )
        }
      >
        <div className="flex flex-col gap-4">
          {eroare ? <Banda ton="eroare">{eroare}</Banda> : null}

          <Camp
            eticheta="Cod de acces"
            placeholder="Ex. K7M2QPX9RTBD"
            value={token}
            onChange={(e) => {
              setToken(e.target.value.toUpperCase());
              setPreviziune(null);
            }}
            maxLength={80}
            autoCapitalize="characters"
            autoCorrect="off"
            spellCheck={false}
            className="tabular tracking-[0.08em]"
            ajutor="12 caractere. Poți lipi și linkul întreg."
          />

          {previziune ? (
            <div className="animate-fade-up rounded-card bg-surface p-4 shadow-sm">
              <div className="flex items-center gap-3">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary-50">
                  <Users size={18} strokeWidth={1.75} aria-hidden className="text-primary-600" />
                </span>

                <div className="min-w-0 flex-1">
                  <p className="truncate text-[15px] font-semibold text-ink">
                    {previziune.nume}
                  </p>
                  <p className="text-[12.5px] text-ink-faint">
                    {previziune.membri === 1 ? "1 membru" : `${previziune.membri} membri`}
                    {previziune.suntDeja ? " · ești deja în el" : ""}
                  </p>
                </div>
              </div>
            </div>
          ) : null}
        </div>
      </DrawerContent>
    </Drawer>
  );
}
