"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { Check, FileUp, MessageSquareWarning, X } from "lucide-react";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { Camp } from "@/components/ui/camp";
import { Drawer, DrawerContent } from "@/components/ui/drawer";
import { decideCerereCredit } from "@/lib/actions/admin-credite";
import { lei, type ActiuneAnalist } from "@/lib/tipuri-admin";

/**
 * Ce face analistul cu un dosar aflat in lucru.
 *
 * Patru iesiri, nu doua. Cele care inchid discutia (aproba/respinge) trec
 * printr-o confirmare: de o parte si de alta a butonului stau banii cuiva, iar
 * o apasare din greseala nu trebuie sa fie de ajuns. Cele care o tin deschisa
 * cer un mesaj — el e tot ce vede clientul, deci fara el n-ar sti ce sa faca.
 *
 * Formularea din drawer spune explicit ce urmeaza, fiindca lucrul cel mai usor
 * de inteles gresit e ca „aproba" ar da banii. Nu da: genereaza oferta, iar
 * clientul o semneaza el.
 */

type Configuratie = {
  titlu: string;
  confirmare: string;
  etichetaCamp: string;
  ajutorCamp: string;
  mesajObligatoriu: boolean;
  varianta: "primary" | "danger";
};

const CONFIGURATII: Record<ActiuneAnalist, Configuratie> = {
  aproba: {
    titlu: "Aprobi cererea?",
    confirmare: "Da, trimite oferta",
    etichetaCamp: "Motivarea deciziei (opțional)",
    ajutorCamp: "Ajunge în explicația pe care o citește clientul, alături de punctajul automat.",
    mesajObligatoriu: false,
    varianta: "primary",
  },
  respinge: {
    titlu: "Respingi cererea?",
    confirmare: "Da, respinge",
    etichetaCamp: "Motivarea deciziei (opțional)",
    ajutorCamp: "Ajunge în explicația pe care o citește clientul, alături de punctajul automat.",
    mesajObligatoriu: false,
    varianta: "danger",
  },
  cere_documente: {
    titlu: "Ceri documente?",
    confirmare: "Trimite cererea de acte",
    etichetaCamp: "Ce trebuie să încarce clientul",
    ajutorCamp: "Clientul vede exact acest text, cu un buton de încărcare sub el.",
    mesajObligatoriu: true,
    varianta: "primary",
  },
  notifica: {
    titlu: "Trimiți un mesaj clientului?",
    confirmare: "Trimite mesajul",
    etichetaCamp: "Mesajul pentru client",
    ajutorCamp: "Dosarul rămâne unde e — mesajul doar îl anunță că ceva nu se leagă.",
    mesajObligatoriu: true,
    varianta: "primary",
  },
};

export function DeciziaCererii({
  idCerere,
  nume,
  suma,
  luni,
}: {
  idCerere: string;
  nume: string;
  suma: string;
  luni: number;
}) {
  const router = useRouter();
  const [actiune, setActiune] = useState<ActiuneAnalist | null>(null);
  const [nota, setNota] = useState("");
  const [eroare, setEroare] = useState<string | null>(null);
  const [seTrimite, startTransition] = useTransition();

  const config = actiune ? CONFIGURATII[actiune] : null;

  function descriere(alegere: ActiuneAnalist): string {
    switch (alegere) {
      case "aproba":
        return `${nume} va primi o ofertă de ${lei(suma)} RON pe ${luni} luni, valabilă 7 zile.`;
      case "respinge":
        return `${nume} află că cererea nu a fost aprobată și poate depune alta oricând.`;
      case "cere_documente":
        return `${nume} vede mesajul în aplicație și poate încărca actele. Dosarul iese din coada ta până le trimite.`;
      case "notifica":
        return `${nume} vede mesajul în aplicație. Dosarul rămâne exact unde e acum.`;
    }
  }

  function inchide() {
    setActiune(null);
    setNota("");
    setEroare(null);
  }

  function confirma() {
    if (!actiune || !config) return;

    if (config.mesajObligatoriu && !nota.trim()) {
      setEroare("Scrie un mesaj pentru client.");
      return;
    }

    setEroare(null);
    startTransition(async () => {
      const rezultat = await decideCerereCredit(idCerere, actiune, nota);
      if (rezultat.eroare) {
        setEroare(rezultat.eroare);
        return;
      }

      // Aproba/respinge inchid dosarul, deci intoarcerea in lista e utila.
      // Celelalte doua il lasa deschis: analistul ramane pe el.
      if (actiune === "aproba" || actiune === "respinge") {
        inchide();
        router.push("/admin/credite");
      } else {
        inchide();
      }
      router.refresh();
    });
  }

  return (
    <section className="rounded-card border border-line bg-surface p-5">
      <h2 className="text-[15px] font-semibold text-ink">Decizia ta</h2>
      <p className="mt-1 text-[13px] leading-[19px] text-ink-faint">
        Aprobarea nu acordă creditul — generează oferta, pe care clientul o semnează din
        aplicație. Dacă mai ai nevoie de ceva, cere acte sau scrie-i, fără să închizi dosarul.
      </p>

      {eroare && actiune === null ? (
        <div className="mt-4">
          <Banda ton="eroare">{eroare}</Banda>
        </div>
      ) : null}

      <div className="mt-4 flex flex-col gap-3 sm:flex-row">
        <Button
          className="flex-1"
          iconaStanga={<Check size={18} strokeWidth={1.75} aria-hidden />}
          onClick={() => setActiune("aproba")}
        >
          Aprobă cererea
        </Button>
        <Button
          varianta="danger"
          className="flex-1"
          iconaStanga={<X size={18} strokeWidth={1.75} aria-hidden />}
          onClick={() => setActiune("respinge")}
        >
          Respinge
        </Button>
      </div>

      <div className="mt-3 flex flex-col gap-3 sm:flex-row">
        <Button
          varianta="secondary"
          className="flex-1"
          iconaStanga={<FileUp size={18} strokeWidth={1.75} aria-hidden />}
          onClick={() => setActiune("cere_documente")}
        >
          Cere documente
        </Button>
        <Button
          varianta="secondary"
          className="flex-1"
          iconaStanga={<MessageSquareWarning size={18} strokeWidth={1.75} aria-hidden />}
          onClick={() => setActiune("notifica")}
        >
          Notifică clientul
        </Button>
      </div>

      <Drawer
        open={actiune !== null}
        onOpenChange={(deschis) => {
          if (!deschis && !seTrimite) inchide();
        }}
        dismissible={!seTrimite}
      >
        <DrawerContent
          title={config?.titlu ?? ""}
          description={actiune ? descriere(actiune) : ""}
          cuInchidere={!seTrimite}
          footer={
            <Button
              varianta={config?.varianta ?? "primary"}
              className="w-full"
              loading={seTrimite}
              onClick={confirma}
            >
              {config?.confirmare ?? ""}
            </Button>
          }
        >
          {eroare ? (
            <div className="mb-4">
              <Banda ton="eroare">{eroare}</Banda>
            </div>
          ) : null}

          <Camp
            eticheta={config?.etichetaCamp ?? ""}
            value={nota}
            onChange={(eveniment) => setNota(eveniment.target.value)}
            maxLength={500}
            ajutor={config?.ajutorCamp}
            autoComplete="off"
          />
        </DrawerContent>
      </Drawer>
    </section>
  );
}
