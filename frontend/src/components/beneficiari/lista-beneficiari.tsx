"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Check, Copy, Plus, Send, Star, Trash2, User } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Camp } from "@/components/ui/camp";
import { Drawer, DrawerContent, DrawerTrigger } from "@/components/ui/drawer";
import { ibanEsteValid } from "@/lib/iban";
import type { Beneficiar } from "@/lib/mock-data";
import { cn, formateazaIban } from "@/lib/utils";

function initiale(nume: string) {
  return nume
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((parte) => parte[0]?.toUpperCase())
    .join("");
}

export function ListaBeneficiari({ beneficiari: initiali }: { beneficiari: Beneficiar[] }) {
  const [beneficiari, setBeneficiari] = useState(initiali);
  const [selectatId, setSelectatId] = useState<string | null>(null);
  const [pas, setPas] = useState<"detalii" | "sterge">("detalii");

  const selectat = beneficiari.find((b) => b.id === selectatId) ?? null;

  function sterge(id: string) {
    setBeneficiari((prev) => prev.filter((b) => b.id !== id));
    setSelectatId(null);
  }

  return (
    <div className="mx-auto w-full max-w-[440px] px-6 pb-6 pt-8 sm:max-w-2xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-[-0.02em] text-ink">Beneficiari</h1>
          <p className="mt-1 text-[15px] text-ink-soft">Conturile catre care trimiti frecvent bani.</p>
        </div>
        <AdaugaBeneficiarDrawer onAdaugat={(b) => setBeneficiari((prev) => [b, ...prev])} />
      </div>

      <div className="mt-6 flex flex-col gap-2">
        {beneficiari.map((b) => (
          <button
            key={b.id}
            type="button"
            onClick={() => {
              setSelectatId(b.id);
              setPas("detalii");
            }}
            className="flex w-full items-center gap-3 rounded-card border border-line bg-surface px-4 py-3 text-left shadow-sm transition-colors hover:bg-muted"
          >
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary-100 text-[13px] font-semibold text-primary-700">
              {initiale(b.nume)}
            </span>
            <span className="min-w-0 flex-1">
              <span className="flex items-center gap-1.5">
                <span className="truncate text-[15px] text-ink">{b.nume}</span>
                {b.favorit ? (
                  <Star size={13} strokeWidth={1.75} aria-hidden className="shrink-0 fill-warning text-warning" />
                ) : null}
              </span>
              <span className="tabular block truncate text-[12.5px] text-ink-faint">
                {formateazaIban(b.iban)}
              </span>
            </span>
          </button>
        ))}

        {beneficiari.length === 0 ? (
          <p className="mt-8 text-center text-[15px] text-ink-faint">
            Nu ai niciun beneficiar salvat.
          </p>
        ) : null}
      </div>

      <Drawer
        open={selectat !== null}
        onOpenChange={(deschis) => {
          if (!deschis) setSelectatId(null);
        }}
      >
        {selectat ? (
          <DetaliuBeneficiarContinut beneficiar={selectat} pas={pas} setPas={setPas} onSterge={sterge} />
        ) : (
          <DrawerContent title="" description="">
            {null}
          </DrawerContent>
        )}
      </Drawer>
    </div>
  );
}

function DetaliuBeneficiarContinut({
  beneficiar,
  pas,
  setPas,
  onSterge,
}: {
  beneficiar: Beneficiar;
  pas: "detalii" | "sterge";
  setPas: (pas: "detalii" | "sterge") => void;
  onSterge: (id: string) => void;
}) {
  const router = useRouter();
  const [copiat, setCopiat] = useState(false);

  async function copiaza() {
    await navigator.clipboard.writeText(beneficiar.iban);
    setCopiat(true);
    setTimeout(() => setCopiat(false), 2000);
  }

  if (pas === "sterge") {
    return (
      <DrawerContent
        title="Șterge beneficiarul"
        description={`Sigur vrei sa stergi ${beneficiar.nume} din lista de beneficiari?`}
        footer={
          <div className="flex gap-3">
            <Button varianta="ghost" className="flex-1" onClick={() => setPas("detalii")}>
              Renunță
            </Button>
            <Button varianta="danger" className="flex-1" onClick={() => onSterge(beneficiar.id)}>
              Șterge
            </Button>
          </div>
        }
      >
        <p className="text-[15px] leading-[22px] text-ink-soft">
          Nu vei mai putea trimite bani rapid catre acest cont din lista de beneficiari.
          Poti sa il adaugi din nou oricand.
        </p>
      </DrawerContent>
    );
  }

  return (
    <DrawerContent
      title={beneficiar.nume}
      description={beneficiar.banca}
      footer={
        <Button
          className="w-full"
          iconaStanga={<Send size={18} strokeWidth={1.75} aria-hidden />}
          onClick={() => router.push(`/transfer?beneficiar=${beneficiar.id}`)}
        >
          Trimite bani
        </Button>
      }
    >
      <div className="flex flex-col gap-4">
        <div className="rounded-field bg-primary-50 p-4">
          <p className="text-[13px] text-primary-700">IBAN</p>
          <p className="tabular mt-1 text-[15px] font-semibold tracking-[0.02em] text-primary-900">
            {formateazaIban(beneficiar.iban)}
          </p>
          <Button
            varianta="secondary"
            marime="sm"
            onClick={copiaza}
            iconaStanga={
              copiat ? (
                <Check size={16} strokeWidth={1.75} aria-hidden className="animate-pop" />
              ) : (
                <Copy size={16} strokeWidth={1.75} aria-hidden />
              )
            }
            className="mt-3"
          >
            {copiat ? "Copiat" : "Copiaza IBAN"}
          </Button>
        </div>

        <button
          type="button"
          onClick={() => setPas("sterge")}
          className="flex items-center justify-center gap-2 rounded-field py-3 text-[13px] font-semibold text-danger transition-colors hover:bg-danger/8"
        >
          <Trash2 size={16} strokeWidth={1.75} aria-hidden />
          Șterge beneficiarul
        </button>
      </div>
    </DrawerContent>
  );
}

function AdaugaBeneficiarDrawer({ onAdaugat }: { onAdaugat: (b: Beneficiar) => void }) {
  const [deschis, setDeschis] = useState(false);
  const [nume, setNume] = useState("");
  const [iban, setIban] = useState("");
  const [eroareNume, setEroareNume] = useState<string | null>(null);
  const [eroareIban, setEroareIban] = useState<string | null>(null);

  function reseteaza() {
    setNume("");
    setIban("");
    setEroareNume(null);
    setEroareIban(null);
  }

  function adauga() {
    setEroareNume(null);
    setEroareIban(null);

    if (nume.trim().length < 3) {
      setEroareNume("Introdu numele beneficiarului");
      return;
    }
    const ibanCurat = iban.replace(/\s+/g, "").toUpperCase();
    if (!ibanEsteValid(ibanCurat)) {
      setEroareIban("IBAN invalid");
      return;
    }
    onAdaugat({
      id: `nou-${Date.now()}`,
      nume: nume.trim(),
      iban: ibanCurat,
      banca: "Cont extern",
      favorit: false,
    });
    setDeschis(false);
    reseteaza();
  }

  return (
    <Drawer
      open={deschis}
      onOpenChange={(v) => {
        setDeschis(v);
        if (!v) reseteaza();
      }}
    >
      <DrawerTrigger
        aria-label="Adaugă beneficiar"
        className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-primary-600 text-white shadow-btn transition-colors hover:bg-primary-700 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
      >
        <Plus size={20} strokeWidth={1.75} aria-hidden />
      </DrawerTrigger>

      <DrawerContent
        title="Beneficiar nou"
        description="Adaugă un cont catre care sa trimiti bani rapid."
        footer={
          <Button className="w-full" onClick={adauga}>
            Adaugă beneficiarul
          </Button>
        }
      >
        <div className="flex flex-col gap-4">
          <Camp
            eticheta="Nume beneficiar"
            icoana={User}
            value={nume}
            onChange={(e) => setNume(e.target.value)}
            placeholder="Ex. Andrei Popescu"
            autoComplete="off"
            eroare={eroareNume}
          />
          <Camp
            eticheta="IBAN"
            value={iban}
            onChange={(e) => setIban(e.target.value.toUpperCase())}
            placeholder="RO49 AAAA 1B31 0075 9384 0000"
            autoComplete="off"
            eroare={eroareIban}
          />
        </div>
      </DrawerContent>
    </Drawer>
  );
}
