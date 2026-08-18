"use client";

import { Info, Landmark, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Drawer, DrawerClose, DrawerContent, DrawerTrigger } from "@/components/ui/drawer";

/**
 * Explicatiile si textele legale stau in drawere, nu in pagini separate
 * (DESIGN.md 8.1) — utilizatorul nu isi pierde datele completate.
 */

export function DeCeCnpDrawer() {
  return (
    <Drawer>
      <DrawerTrigger className="inline-flex items-center gap-1 rounded text-[12.5px] font-medium text-primary-600 transition-colors hover:text-primary-700 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25">
        <Info size={14} strokeWidth={1.75} aria-hidden />
        De ce cerem CNP-ul?
      </DrawerTrigger>

      <DrawerContent
        title="De ce cerem CNP-ul?"
        description="Verificarea identitatii este obligatorie la deschiderea unui cont bancar."
        footer={
          <DrawerClose asChild>
            <Button className="w-full">Am inteles</Button>
          </DrawerClose>
        }
      >
        <div className="flex flex-col gap-4 text-[15px] leading-[22px] text-ink-soft">
          <p>
            Legea privind prevenirea spalarii banilor ne obliga sa iti verificam
            identitatea inainte de a-ti deschide un cont curent. CNP-ul este
            elementul care te identifica unic.
          </p>

          <div className="flex gap-3 rounded-field bg-primary-50 p-4">
            <ShieldCheck size={20} strokeWidth={1.75} aria-hidden className="mt-0.5 shrink-0 text-primary-600" />
            <p className="text-[13px] leading-[19px] text-primary-900">
              Il stocam criptat, nu il afisam niciodata integral in aplicatie si
              nu il transmitem catre terti in scop de marketing.
            </p>
          </div>

          <p>
            Dupa inregistrare vei vedea doar ultimele trei cifre, in pagina de
            profil.
          </p>
        </div>
      </DrawerContent>
    </Drawer>
  );
}

export function TermeniDrawer() {
  return (
    <Drawer snapPoints={[0.6, 1]}>
      {/* Trigger-ul sta in interiorul unui <label>, deci oprim propagarea ca
          apasarea lui sa nu bifeze si checkbox-ul. */}
      <DrawerTrigger
        onClick={(e) => e.stopPropagation()}
        className="rounded font-semibold text-primary-600 underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
      >
        Termenii si Conditiile
      </DrawerTrigger>

      <DrawerContent
        title="Termeni si Conditii"
        description="Rezumatul conditiilor de deschidere si utilizare a contului Libra."
        footer={
          <DrawerClose asChild>
            <Button className="w-full">Inchide</Button>
          </DrawerClose>
        }
      >
        <div className="flex flex-col gap-5 text-[15px] leading-[22px] text-ink-soft">
          <section className="flex flex-col gap-2">
            <h3 className="flex items-center gap-2 text-base font-semibold text-ink">
              <Landmark size={18} strokeWidth={1.75} aria-hidden className="text-primary-600" />
              1. Contul curent
            </h3>
            <p>
              La inregistrare iti deschidem un cont curent in lei, cu IBAN
              romanesc, fara costuri de administrare in primele 12 luni.
            </p>
          </section>

          <section className="flex flex-col gap-2">
            <h3 className="text-base font-semibold text-ink">2. Datele tale</h3>
            <p>
              Prelucram numele, CNP-ul, telefonul si emailul strict pentru
              deschiderea si administrarea contului, conform GDPR. Iti poti
              solicita oricand stergerea datelor, in limitele impuse de lege.
            </p>
          </section>

          <section className="flex flex-col gap-2">
            <h3 className="text-base font-semibold text-ink">3. Securitate</h3>
            <p>
              Esti responsabil de pastrarea in siguranta a parolei. Orice
              tranzactie neautorizata trebuie raportata in maximum 13 luni de la
              data debitarii.
            </p>
          </section>

          <p className="text-[12.5px] text-ink-faint">
            Text demonstrativ pentru proiect — nu constituie un contract real.
          </p>
        </div>
      </DrawerContent>
    </Drawer>
  );
}
