"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState, useTransition } from "react";
import { AdaugaCardDrawer } from "@/components/carduri/adauga-card-drawer";
import { CaruselCarduri } from "@/components/carduri/carusel-carduri";
import { PanouCard } from "@/components/carduri/panou-card";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { Drawer, DrawerContent } from "@/components/ui/drawer";
import {
  comutaBlocareCard,
  obtineDateSensibileCard,
  type DateSensibileCard,
} from "@/lib/actions/carduri";
import type { CardAfisat } from "@/lib/data/carduri";
import type { ContBancar } from "@/lib/data/conturi";
import { ETICHETE_STIL_CARD } from "@/lib/stil-card";

/**
 * Cat stau pe ecran numarul si CCV-ul inainte ca ele sa dispara si cardul sa se
 * intoarca singur la loc, in milisecunde.
 *
 * Un telefon lasat pe masa cu CCV-ul vizibil e exact ce incearca sa evite
 * confirmarea de dinainte de afisare. Confirmarea pazeste clipa in care apar
 * datele; ceasul asta pazeste tot restul timpului — si nu doar ascunde cifrele,
 * ci pune cardul inapoi pe fata, ca ecranul sa arate din nou ca inainte sa fi
 * cerut ceva.
 *
 * Un minut: cat sa apuci sa copiezi un numar intr-un formular, nu cat sa uiti
 * ecranul deschis.
 */
const DURATA_DEZVALUIRE = 60_000;

export function ListaCarduri({
  carduri,
  conturi,
  posesor,
}: {
  carduri: CardAfisat[];
  conturi: ContBancar[];
  /** Numele de pe card, din profil. */
  posesor?: string | null;
}) {
  const router = useRouter();
  const [activ, setActiv] = useState(0);
  const [intorsId, setIntorsId] = useState<string | null>(null);
  const [dateSensibile, setDateSensibile] = useState<DateSensibileCard | null>(null);
  const [confirmareDeschisa, setConfirmareDeschisa] = useState(false);
  const [eroare, setEroare] = useState<string | null>(null);
  const [seDezvaluie, startDezvaluire] = useTransition();
  const [seBlocheaza, startBlocare] = useTransition();

  const cardActiv = carduri[activ] ?? carduri[0] ?? null;

  /**
   * Cand alt card ajunge in centru, tot ce tinea de cel dinainte se inchide:
   * se intoarce pe fata si isi ascunde datele. Altfel numarul complet al unui
   * card ar ramane pe ecran in timp ce omul se uita la altul.
   */
  const laCardActiv = useCallback((index: number) => {
    setActiv(index);
    setIntorsId(null);
    setDateSensibile(null);
    setConfirmareDeschisa(false);
    setEroare(null);
  }, []);

  useEffect(() => {
    if (!dateSensibile) return;
    const ceas = setTimeout(() => {
      setDateSensibile(null);
      setIntorsId(null);
    }, DURATA_DEZVALUIRE);
    return () => clearTimeout(ceas);
  }, [dateSensibile]);

  /**
   * Apasarea cardului doar il intoarce, in ambele sensuri. Nu dezvaluie nimic.
   *
   * A fost, o vreme, si gestul care afisa datele: a doua apasare pe cardul
   * intors le scotea la vedere. Suna economic, dar lasa omul fara iesire —
   * odata cardul intors, ORICE apasare pe el ar fi afisat datele, deci nu mai
   * puteai sa-l intorci inapoi fara sa treci prin ele. Un gest care nu poate fi
   * anulat cu acelasi gest e o capcana, nu o scurtatura.
   *
   * Acum intoarcerea e reversibila si nu are consecinte, iar afisarea are drum
   * propriu: butonul din panou, cu confirmare (`ceriDezvaluirea`).
   */
  function intoarce(card: CardAfisat) {
    setIntorsId(intorsId === card.id ? null : card.id);
  }

  /**
   * Butonul de afisare din panou: intreaba intai.
   *
   * Cardul NU se intoarce acum. Se intoarce dupa confirmare, odata cu datele —
   * altfel omul ar vedea spatele gol cat tine intrebarea si ar crede ca aia e
   * tot ce primeste.
   */
  function ceriDezvaluirea() {
    if (!cardActiv) return;
    setEroare(null);
    setConfirmareDeschisa(true);
  }

  function confirmaAfisarea() {
    if (!cardActiv) return;
    setEroare(null);
    startDezvaluire(async () => {
      const rezultat = await obtineDateSensibileCard(cardActiv.id);
      if (rezultat.eroare || !rezultat.date) {
        setEroare(rezultat.eroare ?? "Nu am putut afișa datele cardului.");
        return;
      }
      // Intai datele, apoi intoarcerea: cardul se roteste cu ele deja pe el,
      // intr-o singura miscare, in loc sa se intoarca gol si sa se completeze
      // dupa aceea.
      setDateSensibile(rezultat.date);
      setIntorsId(cardActiv.id);
      setConfirmareDeschisa(false);
    });
  }

  function comutaBlocare() {
    if (!cardActiv) return;
    startBlocare(async () => {
      await comutaBlocareCard(cardActiv.id, !cardActiv.blocat);
      router.refresh();
    });
  }

  return (
    <div className="mx-auto w-full max-w-[440px] px-6 pb-6 pt-8 sm:max-w-2xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-[-0.02em] text-ink">Carduri</h1>
          <p className="mt-1 text-[15px] text-ink-soft">
            Apasă un card ca să-l întorci pe spate.
          </p>
        </div>
        {carduri.length > 0 ? <AdaugaCardDrawer compact conturi={conturi} /> : null}
      </div>

      {carduri.length === 0 || !cardActiv ? (
        <section className="mt-6 flex flex-col items-center gap-4 rounded-card border border-dashed border-line bg-surface p-6 text-center shadow-sm">
          <p className="text-[15px] leading-[22px] text-ink-soft">
            Nu ai niciun card încă. Adaugă unul ca să poți trimite și primi bani.
          </p>
          <AdaugaCardDrawer conturi={conturi} />
        </section>
      ) : (
        // Caruselul iese din captuseala paginii: cardurile de pe laturi trebuie
        // sa se vada pe jumatate iesite din cadru, altfel nu se intelege ca mai
        // sunt si altele. Comenzile si panoul de dedesubt isi pun la loc marginea.
        <div className="-mx-6 mt-4">
          <CaruselCarduri
            carduri={carduri}
            posesor={posesor}
            intorsId={intorsId}
            onIntoarce={intoarce}
            onActivChange={laCardActiv}
            dateSensibile={dateSensibile}
          />

          <PanouCard
            card={cardActiv}
            dateSensibile={dateSensibile}
            seDezvaluie={seDezvaluie}
            seBlocheaza={seBlocheaza}
            onDezvaluie={ceriDezvaluirea}
            onAscunde={() => setDateSensibile(null)}
            onComutaBlocare={comutaBlocare}
          />
        </div>
      )}

      <Drawer
        open={confirmareDeschisa}
        onOpenChange={(deschis) => {
          setConfirmareDeschisa(deschis);
          if (!deschis) setEroare(null);
        }}
      >
        <DrawerContent
          title="Afișezi datele sensibile?"
          description="Numărul complet și CCV-ul vor fi vizibile pe spatele cardului. Asigură-te că nu te vede nimeni."
          footer={
            <div className="flex flex-col gap-2">
              <Button className="w-full" loading={seDezvaluie} onClick={confirmaAfisarea}>
                Da, afișează datele
              </Button>
              <Button
                varianta="ghost"
                className="w-full"
                disabled={seDezvaluie}
                onClick={() => setConfirmareDeschisa(false)}
              >
                Renunță
              </Button>
            </div>
          }
        >
          <div className="flex flex-col gap-3">
            {eroare ? <Banda ton="eroare">{eroare}</Banda> : null}
            <p className="text-[15px] leading-[22px] text-ink-soft">
              Cardul {ETICHETE_STIL_CARD[cardActiv?.stil ?? "standard"]} —{" "}
              {cardActiv?.numarMascat ?? ""}. După un minut se ascund singure, iar cardul
              se întoarce la loc.
            </p>
          </div>
        </DrawerContent>
      </Drawer>
    </div>
  );
}
