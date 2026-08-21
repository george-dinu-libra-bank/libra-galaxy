"use client";

import Link from "next/link";
import { ChevronLeft, Fingerprint, Lock, Mail } from "lucide-react";
import { useState, useTransition } from "react";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { Camp } from "@/components/ui/camp";
import { autentifica, autentificaFata } from "@/lib/actions/auth";
import { validEmail } from "@/lib/validare";
import { FaceLoginCapture } from "./face-login-capture";
import { ResetareParolaDrawer } from "./resetare-parola-drawer";

export function LoginForm({ redirectTo }: { redirectTo?: string }) {
  const [email, setEmail] = useState("");
  const [parola, setParola] = useState("");
  const [erori, setErori] = useState<{ email?: string | null; parola?: string | null }>({});
  const [eroareGlobala, setEroareGlobala] = useState<string | null>(null);
  const [arataBiometrie, setArataBiometrie] = useState(false);
  const [emailBiometrie, setEmailBiometrie] = useState("");
  const [eroareEmailBiometrie, setEroareEmailBiometrie] = useState<string | null>(null);
  const [pozaBiometrie, setPozaBiometrie] = useState<File | null>(null);
  const [seTrimite, startTransition] = useTransition();

  function renuntaBiometrie() {
    setArataBiometrie(false);
    setEmailBiometrie("");
    setEroareEmailBiometrie(null);
    setPozaBiometrie(null);
    setEroareGlobala(null);
  }

  function confirmaBiometrie(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();

    const eroareEmail = validEmail(emailBiometrie);
    setEroareEmailBiometrie(eroareEmail);
    setEroareGlobala(null);

    if (eroareEmail) return;
    if (!pozaBiometrie) {
      setEroareGlobala("Fă o poză înainte de a continua.");
      return;
    }

    startTransition(async () => {
      const rezultat = await autentificaFata({
        email: emailBiometrie,
        imagineLive: pozaBiometrie,
        redirectTo,
      });

      if (rezultat?.eroare) setEroareGlobala(rezultat.eroare);
    });
  }

  if (arataBiometrie) {
    return (
      <form onSubmit={confirmaBiometrie} noValidate className="flex flex-col gap-5">
        <button
          type="button"
          onClick={renuntaBiometrie}
          disabled={seTrimite}
          className="inline-flex w-fit items-center gap-1.5 rounded text-[13px] font-semibold text-primary-600 hover:text-primary-700 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
        >
          <ChevronLeft size={16} strokeWidth={2} aria-hidden />
          Înapoi
        </button>

        <div>
          <h2 className="text-lg font-semibold text-ink">Confirmă cu fața</h2>
          <p className="mt-1 text-[13px] leading-[19px] text-ink-soft">
            Introdu emailul contului și fă o poză, într-un loc bine luminat.
          </p>
        </div>

        {eroareGlobala ? <Banda ton="eroare">{eroareGlobala}</Banda> : null}

        <Camp
          eticheta="Email"
          icoana={Mail}
          type="email"
          inputMode="email"
          autoComplete="email"
          placeholder="nume@exemplu.ro"
          autoFocus
          disabled={seTrimite}
          value={emailBiometrie}
          onChange={(e) => {
            setEmailBiometrie(e.target.value);
            if (eroareEmailBiometrie) setEroareEmailBiometrie(validEmail(e.target.value));
          }}
          onBlur={() => setEroareEmailBiometrie(validEmail(emailBiometrie))}
          eroare={eroareEmailBiometrie}
        />

        <FaceLoginCapture poza={pozaBiometrie} onSchimbat={setPozaBiometrie} disabled={seTrimite} />

        <Button
          type="submit"
          loading={seTrimite}
          disabled={!pozaBiometrie}
          className="w-full"
          iconaStanga={!seTrimite ? <Fingerprint size={18} strokeWidth={1.75} aria-hidden /> : undefined}
        >
          {seTrimite ? "Se verifica…" : "Autentificare"}
        </Button>
      </form>
    );
  }

  function trimite(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();

    const eroriNoi = {
      email: validEmail(email),
      parola: parola ? null : "Introdu parola.",
    };
    setErori(eroriNoi);
    setEroareGlobala(null);

    if (eroriNoi.email || eroriNoi.parola) return;

    startTransition(async () => {
      const rezultat = await autentifica({ email, parola, redirectTo });
      if (rezultat?.eroare) setEroareGlobala(rezultat.eroare);
    });
  }

  return (
    <form onSubmit={trimite} noValidate className="flex flex-col gap-5">
      {eroareGlobala ? <Banda ton="eroare">{eroareGlobala}</Banda> : null}

      <div className="stagger flex flex-col gap-4">
        <div style={{ "--i": 0 } as React.CSSProperties}>
          <Camp
            eticheta="Email"
            icoana={Mail}
            type="email"
            inputMode="email"
            autoComplete="email"
            placeholder="nume@exemplu.ro"
            value={email}
            onChange={(e) => {
              setEmail(e.target.value);
              if (erori.email) setErori((p) => ({ ...p, email: validEmail(e.target.value) }));
            }}
            onBlur={() => setErori((p) => ({ ...p, email: validEmail(email) }))}
            eroare={erori.email}
          />
        </div>

        <div style={{ "--i": 1 } as React.CSSProperties}>
          <Camp
            eticheta="Parola"
            icoana={Lock}
            parola
            autoComplete="current-password"
            placeholder="Parola ta"
            value={parola}
            onChange={(e) => {
              setParola(e.target.value);
              if (erori.parola) setErori((p) => ({ ...p, parola: null }));
            }}
            eroare={erori.parola}
          />
        </div>
      </div>

      <div className="-mt-1 flex justify-end">
        <ResetareParolaDrawer emailInitial={email} />
      </div>

      <Button type="submit" loading={seTrimite} className="w-full">
        {seTrimite ? "Se verifica…" : "Autentificare"}
      </Button>

      <div className="flex items-center gap-3">
        <span className="h-px flex-1 bg-line" />
        <span className="text-[12.5px] text-ink-faint">sau</span>
        <span className="h-px flex-1 bg-line" />
      </div>

      <Button
        type="button"
        varianta="secondary"
        className="w-full"
        iconaStanga={<Fingerprint size={18} strokeWidth={1.75} aria-hidden />}
        onClick={() => setArataBiometrie(true)}
      >
        Continua cu biometrie
      </Button>

      <p className="pt-1 text-center text-[13px] text-ink-soft">
        Nu ai cont?{" "}
        <Link
          href="/register"
          className="font-semibold text-primary-600 hover:text-primary-700 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25 rounded"
        >
          Deschide unul
        </Link>
      </p>
    </form>
  );
}
