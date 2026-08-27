"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { Send } from "lucide-react";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { Camp } from "@/components/ui/camp";
import { trimiteSesizare } from "@/lib/actions/suport";

const MIN_REZUMAT = 10;

/**
 * Scrierea unei sesizari, direct.
 *
 * Exista pentru ca sesizarea nu trebuie sa depinda de bunavointa unui model:
 * asistentul poate pregati textul, dar cine vrea sa scrie singur trebuie sa
 * poata, fara sa treaca prin nicio conversatie.
 */
export function FormularSesizare({
  subiectInitial = "",
  rezumatInitial = "",
  areDejaDeschisa,
}: {
  subiectInitial?: string;
  rezumatInitial?: string;
  areDejaDeschisa: boolean;
}) {
  const router = useRouter();
  const [subiect, setSubiect] = useState(subiectInitial);
  const [rezumat, setRezumat] = useState(rezumatInitial);
  const [eroare, setEroare] = useState<string | null>(null);
  const [seTrimite, startTransition] = useTransition();

  const incomplet = subiect.trim().length < 3 || rezumat.trim().length < MIN_REZUMAT;

  function trimite() {
    if (incomplet) return;
    setEroare(null);
    startTransition(async () => {
      const rezultat = await trimiteSesizare(subiect, rezumat);
      if (rezultat.eroare) {
        setEroare(rezultat.eroare);
        return;
      }
      setSubiect("");
      setRezumat("");
      router.refresh();
    });
  }

  if (areDejaDeschisa) {
    return (
      <Banda ton="info">
        Ai deja o sesizare în lucru. Așteaptă răspunsul înainte de a trimite alta — altfel
        cazul tău ajunge la doi colegi deodată.
      </Banda>
    );
  }

  return (
    <section className="rounded-card border border-line bg-surface p-5">
      <h2 className="text-[15px] font-semibold text-ink">Scrie băncii</h2>
      <p className="mt-1 text-[13px] leading-[19px] text-ink-faint">
        Pentru situații urgente — card pierdut sau tranzacții pe care nu le recunoști — sună la{" "}
        <strong className="font-semibold text-ink">0800 970 501</strong>. E mai rapid.
      </p>

      {eroare ? (
        <div className="mt-4">
          <Banda ton="eroare">{eroare}</Banda>
        </div>
      ) : null}

      <div className="mt-4 flex flex-col gap-3">
        <Camp
          eticheta="Subiect"
          value={subiect}
          onChange={(e) => setSubiect(e.target.value)}
          placeholder="Ex. Contul meu e blocat"
          maxLength={200}
          autoComplete="off"
        />
        <Camp
          eticheta="Ce s-a întâmplat"
          value={rezumat}
          onChange={(e) => setRezumat(e.target.value)}
          placeholder="Descrie situația și ce ai nevoie."
          maxLength={4000}
          ajutor="Ajunge la un coleg din bancă. Primești răspunsul ca notificare."
          autoComplete="off"
        />
      </div>

      <Button
        className="mt-4 w-full sm:w-auto"
        loading={seTrimite}
        disabled={incomplet}
        iconaStanga={<Send size={18} strokeWidth={1.75} aria-hidden />}
        onClick={trimite}
      >
        Trimite sesizarea
      </Button>
    </section>
  );
}
