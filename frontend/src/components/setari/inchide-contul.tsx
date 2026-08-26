"use client";

import { Trash2 } from "lucide-react";
import { useState, useTransition } from "react";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { Camp } from "@/components/ui/camp";
import { Drawer, DrawerContent, DrawerTrigger } from "@/components/ui/drawer";
import {
  cereStergereaContului,
  retrageCerereaDeStergere,
  type StareStergere,
} from "@/lib/actions/stergere-cont";

/**
 * Inchiderea relatiei cu banca — in Setari, nu pe dashboard.
 *
 * Prima varianta o pusese intr-un meniu de trei puncte in antetul
 * dashboardului. Doua lucruri nu mergeau acolo: o cerere depusa devenea
 * invizibila (trebuia sa-ti amintesti sa redeschizi meniul ca s-o vezi sau s-o
 * retragi), iar datele personale ajungeau in doua ecrane deodata, unul cu
 * editare si unul fara. Aici stau deja CNP-ul, telefonul, securitatea si
 * deconectarea — tot ce tine de relatia cu banca, nu de bani.
 *
 * Cererea nu sterge nimic. O decide un om; vezi 0036_cereri_stergere_cont.sql.
 */
export function InchideContul({ stare }: { stare: StareStergere | null }) {
  const [deschis, setDeschis] = useState(false);

  return (
    <>
      <h2 className="mb-2 mt-8 text-[13px] font-medium text-ink-faint">Închiderea contului</h2>

      <Drawer open={deschis} onOpenChange={setDeschis}>
        <DrawerTrigger className="flex w-full items-center gap-3 rounded-card bg-surface px-4 py-3.5 text-left shadow-sm transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25">
          <Trash2 size={20} strokeWidth={1.75} aria-hidden className="shrink-0 text-danger" />
          <span className="min-w-0 flex-1">
            <span className="block text-[15px] text-danger">Închide contul</span>
            <span className="block text-[12.5px] leading-[17px] text-ink-faint">
              {stare?.cerere
                ? "Cererea ta e în analiză"
                : "Trimiți o cerere; decide un coleg"}
            </span>
          </span>
        </DrawerTrigger>

        <DrawerContent
          title="Închiderea contului"
          description="Cererea ajunge la un coleg, care o analizează."
        >
          <Continut stare={stare} onGata={() => setDeschis(false)} />
        </DrawerContent>
      </Drawer>
    </>
  );
}

function Continut({ stare, onGata }: { stare: StareStergere | null; onGata: () => void }) {
  const [motiv, setMotiv] = useState("");
  const [eroare, setEroare] = useState<string | null>(null);
  const [seTrimite, startTransition] = useTransition();

  if (stare === null) {
    return <Banda ton="eroare">Nu am putut verifica starea contului. Încearcă din nou.</Banda>;
  }

  if (stare.cerere) {
    return (
      <div className="flex flex-col gap-4">
        <Banda ton="info">
          Cererea ta de închidere e în analiză. Îți răspundem în mesajele din aplicație.
        </Banda>
        {eroare ? <Banda ton="eroare">{eroare}</Banda> : null}
        <Button
          varianta="secondary"
          loading={seTrimite}
          onClick={() =>
            startTransition(async () => {
              setEroare(null);
              const rezultat = await retrageCerereaDeStergere(stare.cerere!.id);
              if (rezultat.eroare) setEroare(rezultat.eroare);
              else onGata();
            })
          }
        >
          M-am răzgândit, retrage cererea
        </Button>
      </div>
    );
  }

  // Ce il tine legat de banca — spus INAINTE sa apese, nu dupa. Un buton care
  // se lasa apasat si abia apoi refuza e mai prost decat unul care explica.
  if (!stare.poate_cere) {
    return (
      <div className="flex flex-col gap-3">
        <p className="text-[15px] leading-[22px] text-ink">Contul nu se poate închide încă:</p>
        <ul className="flex flex-col gap-2">
          {stare.motive_blocare.map((motivBlocare) => (
            <li
              key={motivBlocare}
              className="rounded-field bg-muted px-4 py-3 text-[13.5px] leading-[19px] text-ink-soft"
            >
              {motivBlocare}
            </li>
          ))}
        </ul>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-[15px] leading-[22px] text-ink-soft">
        Contul nu se închide pe loc. Trimiți o cerere, iar un coleg o analizează și îți
        răspunde. Până atunci poți folosi contul normal, și te poți răzgândi oricând.
      </p>

      <Camp
        eticheta="De ce pleci? (opțional)"
        value={motiv}
        onChange={(e) => setMotiv(e.target.value)}
        maxLength={500}
        placeholder="Ne ajută să ne dăm seama ce am greșit"
      />

      {eroare ? <Banda ton="eroare">{eroare}</Banda> : null}

      <Button
        varianta="danger"
        loading={seTrimite}
        iconaStanga={!seTrimite ? <Trash2 size={18} strokeWidth={1.75} aria-hidden /> : undefined}
        onClick={() =>
          startTransition(async () => {
            setEroare(null);
            const rezultat = await cereStergereaContului(motiv);
            if (rezultat.eroare) setEroare(rezultat.eroare);
            else onGata();
          })
        }
      >
        Trimite cererea de închidere
      </Button>
    </div>
  );
}
