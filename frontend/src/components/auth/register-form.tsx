"use client";

import Link from "next/link";
import { IdCard, Lock, Mail, Phone, User } from "lucide-react";
import { useMemo, useState, useTransition } from "react";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { Camp } from "@/components/ui/camp";
import { Checkbox } from "@/components/ui/checkbox";
import { inregistreaza } from "@/lib/actions/auth";
import {
  putereParola,
  validCnp,
  validEmail,
  validNume,
  validParola,
  validTelefon,
} from "@/lib/validare";
import { cn } from "@/lib/utils";
import { BuletinCapture } from "./buletin-capture";
import { SelfieCapture } from "./selfie-capture";
import { DeCeCnpDrawer, TermeniDrawer } from "./info-drawere";

type Campuri = {
  nume: string;
  cnp: string;
  telefon: string;
  email: string;
  parola: string;
};

const INITIAL: Campuri = { nume: "", cnp: "", telefon: "", email: "", parola: "" };

const VALIDATORI: Record<keyof Campuri, (v: string) => string | null> = {
  nume: validNume,
  cnp: validCnp,
  telefon: validTelefon,
  email: validEmail,
  parola: validParola,
};

const ETICHETE_PUTERE = ["Prea slaba", "Slaba", "Acceptabila", "Buna", "Puternica"];

type Pas = "buletin" | "selfie" | "date";

export function RegisterForm() {
  const [pas, setPas] = useState<Pas>("buletin");
  const [pozaBuletin, setPozaBuletin] = useState<File | null>(null);
  const [pozaSelfie, setPozaSelfie] = useState<File | null>(null);

  const [valori, setValori] = useState<Campuri>(INITIAL);
  const [erori, setErori] = useState<Partial<Record<keyof Campuri, string | null>>>({});
  const [atinse, setAtinse] = useState<Partial<Record<keyof Campuri, boolean>>>({});
  const [acord, setAcord] = useState(false);
  const [eroareAcord, setEroareAcord] = useState<string | null>(null);
  const [eroareGlobala, setEroareGlobala] = useState<string | null>(null);
  const [mesaj, setMesaj] = useState<string | null>(null);
  const [seTrimite, startTransition] = useTransition();

  const putere = useMemo(() => putereParola(valori.parola), [valori.parola]);

  function seteaza(camp: keyof Campuri, valoare: string) {
    setValori((p) => ({ ...p, [camp]: valoare }));

    // Dupa prima eroare, campul se revalideaza live (DESIGN.md 9).
    if (erori[camp]) setErori((p) => ({ ...p, [camp]: VALIDATORI[camp](valoare) }));
  }

  function laBlur(camp: keyof Campuri) {
    setAtinse((p) => ({ ...p, [camp]: true }));
    setErori((p) => ({ ...p, [camp]: VALIDATORI[camp](valori[camp]) }));
  }

  function laFinalizareBuletin(fisier: File, cnp: string) {
    setPozaBuletin(fisier);
    setValori((p) => ({ ...p, cnp }));
    setPas("selfie");
  }

  function saraBuletinul() {
    setPozaBuletin(null);
    setPas("selfie");
  }

  function laFinalizareSelfie(fisier: File) {
    setPozaSelfie(fisier);
    setPas("date");
  }

  function trimite(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setEroareGlobala(null);

    const eroriNoi = Object.fromEntries(
      (Object.keys(VALIDATORI) as (keyof Campuri)[]).map((camp) => [
        camp,
        VALIDATORI[camp](valori[camp]),
      ]),
    ) as Partial<Record<keyof Campuri, string | null>>;

    setErori(eroriNoi);
    setAtinse({ nume: true, cnp: true, telefon: true, email: true, parola: true });

    const eroareTermeni = acord ? null : "Trebuie sa accepti termenii si conditiile.";
    setEroareAcord(eroareTermeni);

    if (!pozaSelfie) {
      setEroareGlobala("Lipseste selfie-ul.");
      return;
    }

    if (Object.values(eroriNoi).some(Boolean) || eroareTermeni) {
      setEroareGlobala("Mai sunt campuri de corectat.");
      return;
    }

    startTransition(async () => {
      const rezultat = await inregistreaza({
        ...valori,
        buletin: pozaBuletin,
        selfie: pozaSelfie,
      });

      if (rezultat?.eroare) setEroareGlobala(rezultat.eroare);
      if (rezultat?.mesaj) setMesaj(rezultat.mesaj);
    });
  }

  if (mesaj) {
    return (
      <div className="flex flex-col gap-5">
        <Banda ton="succes">{mesaj}</Banda>
        <p className="text-[15px] leading-[22px] text-ink-soft">
          Dupa confirmare te poti autentifica cu emailul si parola alese.
        </p>
        <Link
          href="/login"
          className="inline-flex h-[52px] w-full items-center justify-center rounded-field bg-primary-600 text-[15px] font-semibold text-white shadow-btn transition-colors hover:bg-primary-700 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
        >
          Mergi la autentificare
        </Link>
      </div>
    );
  }

  if (pas === "buletin") {
    return <BuletinCapture onFinalizat={laFinalizareBuletin} onSarit={saraBuletinul} />;
  }

  if (pas === "selfie") {
    return <SelfieCapture onFinalizat={laFinalizareSelfie} />;
  }

  return (
    <form onSubmit={trimite} noValidate className="flex flex-col gap-5">
      {eroareGlobala ? <Banda ton="eroare">{eroareGlobala}</Banda> : null}

      <div className="stagger flex flex-col gap-4">
        <div style={{ "--i": 0 } as React.CSSProperties}>
          <Camp
            eticheta="Nume si prenume"
            icoana={User}
            autoComplete="name"
            placeholder="Popescu Andrei"
            value={valori.nume}
            onChange={(e) => seteaza("nume", e.target.value)}
            onBlur={() => laBlur("nume")}
            eroare={erori.nume}
            validat={Boolean(atinse.nume && !erori.nume && valori.nume)}
          />
        </div>

        <div style={{ "--i": 1 } as React.CSSProperties}>
          <Camp
            eticheta="CNP"
            icoana={IdCard}
            inputMode="numeric"
            maxLength={13}
            autoComplete="off"
            placeholder="13 cifre"
            className="tabular tracking-[0.04em]"
            value={valori.cnp}
            onChange={(e) => seteaza("cnp", e.target.value.replace(/\D/g, ""))}
            onBlur={() => laBlur("cnp")}
            eroare={erori.cnp}
            validat={Boolean(atinse.cnp && !erori.cnp && valori.cnp)}
            ajutor={
              pozaBuletin
                ? "Citit automat din poza buletinului — verifica sa fie corect."
                : "Introdu-l manual — poți trimite și poza buletinului mai târziu."
            }
          />
          <div className="mt-1.5">
            <DeCeCnpDrawer />
          </div>
        </div>

        <div style={{ "--i": 2 } as React.CSSProperties}>
          <Camp
            eticheta="Telefon"
            icoana={Phone}
            type="tel"
            inputMode="tel"
            autoComplete="tel"
            placeholder="07xx xxx xxx"
            className="tabular"
            value={valori.telefon}
            onChange={(e) => seteaza("telefon", e.target.value)}
            onBlur={() => laBlur("telefon")}
            eroare={erori.telefon}
            validat={Boolean(atinse.telefon && !erori.telefon && valori.telefon)}
          />
        </div>

        <div style={{ "--i": 3 } as React.CSSProperties}>
          <Camp
            eticheta="Email"
            icoana={Mail}
            type="email"
            inputMode="email"
            autoComplete="email"
            placeholder="nume@exemplu.ro"
            value={valori.email}
            onChange={(e) => seteaza("email", e.target.value)}
            onBlur={() => laBlur("email")}
            eroare={erori.email}
            validat={Boolean(atinse.email && !erori.email && valori.email)}
          />
        </div>

        <div style={{ "--i": 4 } as React.CSSProperties}>
          <Camp
            eticheta="Parola"
            icoana={Lock}
            parola
            autoComplete="new-password"
            placeholder="Minim 8 caractere"
            value={valori.parola}
            onChange={(e) => seteaza("parola", e.target.value)}
            onBlur={() => laBlur("parola")}
            eroare={erori.parola}
            ajutor="Cel putin 8 caractere, o litera mare si o cifra."
          />

          {valori.parola ? (
            <div className="mt-2 flex items-center gap-2">
              <div className="flex flex-1 gap-1" aria-hidden>
                {[0, 1, 2, 3].map((i) => (
                  <span
                    key={i}
                    className={cn(
                      "h-1 flex-1 rounded-full transition-colors duration-[180ms]",
                      i < putere
                        ? putere <= 1
                          ? "bg-danger"
                          : putere === 2
                            ? "bg-warning"
                            : "bg-success"
                        : "bg-line",
                    )}
                  />
                ))}
              </div>
              <span className="text-[12.5px] text-ink-faint">
                {ETICHETE_PUTERE[putere]}
              </span>
            </div>
          ) : null}
        </div>
      </div>

      <Checkbox checked={acord} onCheckedChange={(v) => { setAcord(v); if (v) setEroareAcord(null); }} eroare={eroareAcord}>
        Prin crearea contului accept <TermeniDrawer /> si politica de
        confidentialitate Libra.
      </Checkbox>

      <Button type="submit" loading={seTrimite} className="w-full">
        {seTrimite ? "Se creeaza contul…" : "Deschide contul"}
      </Button>

      <p className="text-center text-[13px] text-ink-soft">
        Ai deja cont?{" "}
        <Link
          href="/login"
          className="rounded font-semibold text-primary-600 hover:text-primary-700 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
        >
          Autentifica-te
        </Link>
      </p>
    </form>
  );
}
