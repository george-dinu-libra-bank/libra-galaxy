"use client";

import Link from "next/link";
import { Fingerprint, Lock, Mail } from "lucide-react";
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
  const [arataCamera, setArataCamera] = useState(false);
  const [seTrimite, startTransition] = useTransition();

  function deschideBiometrie() {
    const eroareEmail = validEmail(email);
    setErori((p) => ({ ...p, email: eroareEmail }));
    setEroareGlobala(null);

    if (eroareEmail) {
      setEroareGlobala("Introdu emailul contului inainte de a folosi biometria.");
      return;
    }

    setArataCamera(true);
  }

  function laCaptura(fisier: File) {
    setEroareGlobala(null);

    startTransition(async () => {
      const rezultat = await autentificaFata({ email, imagineLive: fisier, redirectTo });

      if (rezultat?.eroare) {
        setEroareGlobala(rezultat.eroare);
        setArataCamera(false);
      }
    });
  }

  if (arataCamera) {
    return (
      <div className="flex flex-col gap-5">
        {eroareGlobala ? <Banda ton="eroare">{eroareGlobala}</Banda> : null}
        <FaceLoginCapture
          onCaptura={laCaptura}
          onRenunta={() => setArataCamera(false)}
          seTrimite={seTrimite}
        />
      </div>
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
        onClick={deschideBiometrie}
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
