"use client";

import { ChevronRight, Laptop, Lock, LogOut, ScanFace, ShieldCheck, Smartphone } from "lucide-react";
import { useEffect, useState, useTransition } from "react";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { Camp } from "@/components/ui/camp";
import { Comutator } from "@/components/ui/comutator";
import { Drawer, DrawerContent, DrawerTrigger } from "@/components/ui/drawer";
import { schimbaParola } from "@/lib/actions/auth";
import { deconecteazaCelelalteDispozitive } from "@/lib/actions/dispozitive";
import { seteazaBiometrie } from "@/lib/actions/profil";
import type { DispozitivAfisat } from "@/lib/data/dispozitive";
import { etichetaZi, formateazaOra } from "@/lib/utils";
import { validParola } from "@/lib/validare";

/**
 * Tot ce tine de securitatea contului, intr-un singur drawer deschis din
 * randul "Securitate": pornirea/oprirea login-ului biometric, schimbarea
 * parolei si dispozitivele conectate.
 *
 * Sunt trei lucruri diferite, dar toate raspund la aceeasi intrebare — "cine
 * poate intra pe contul meu" — si se citesc impreuna. Sectiunile isi tin
 * fiecare propriul buton, deci drawerul n-are footer: n-ar avea ce actiune
 * unica sa puna acolo.
 */

function Titlu({ copil }: { copil: string }) {
  return <h3 className="text-[13px] font-medium text-ink-faint">{copil}</h3>;
}

/* -------------------------------------------------------------------------- */
/* Login biometric                                                             */
/* -------------------------------------------------------------------------- */

function SectiuneBiometrie({ activataInitial, areSelfie }: { activataInitial: boolean; areSelfie: boolean }) {
  const [activata, setActivata] = useState(activataInitial);
  const [eroare, setEroare] = useState<string | null>(null);
  const [seSalveaza, startTransition] = useTransition();

  function comuta() {
    const noua = !activata;
    setEroare(null);
    // Optimist: comutatorul trebuie sa raspunda pe loc. Daca serverul refuza,
    // il dam inapoi si spunem de ce.
    setActivata(noua);

    startTransition(async () => {
      const rezultat = await seteazaBiometrie(noua);
      if (rezultat.eroare) {
        setActivata(!noua);
        setEroare(rezultat.eroare);
      }
    });
  }

  const pornit = activata && areSelfie;

  return (
    <section className="flex flex-col gap-2">
      <Titlu copil="Autentificare" />

      <div className="rounded-card bg-muted px-4 py-3.5">
        <div className="flex items-center gap-3">
          <ScanFace size={20} strokeWidth={1.75} aria-hidden className="text-ink-faint" />
          <span className="flex-1 text-[15px] text-ink">Login biometric</span>

          <Comutator
            activ={pornit}
            onChange={comuta}
            eticheta="Login biometric"
            dezactivat={!areSelfie || seSalveaza}
          />
        </div>

        <p className="mt-1.5 pl-8 text-[12.5px] leading-[18px] text-ink-faint">
          {areSelfie
            ? "Intri în cont cu fața, fără parolă. Oprit, îți rămâne doar parola."
            : "Disponibil după ce îți verificăm identitatea."}
        </p>
      </div>

      {eroare ? <Banda ton="eroare">{eroare}</Banda> : null}
    </section>
  );
}

/* -------------------------------------------------------------------------- */
/* Schimbarea parolei                                                          */
/* -------------------------------------------------------------------------- */

function SectiuneParola() {
  const [parolaActuala, setParolaActuala] = useState("");
  const [parolaNoua, setParolaNoua] = useState("");
  const [confirmare, setConfirmare] = useState("");
  const [rezultat, setRezultat] = useState<{ eroare?: string; mesaj?: string }>({});
  const [seTrimite, startTransition] = useTransition();

  const reusit = Boolean(rezultat.mesaj);

  function trimite() {
    // Potrivirea si puterea parolei se verifica intai aici: sunt greseli de
    // tastare, n-au nevoie de un drum pana la server. Serverul le valideaza
    // oricum din nou, cu acelasi validParola.
    if (parolaNoua !== confirmare) {
      setRezultat({ eroare: "Parolele nu se potrivesc." });
      return;
    }

    const eroareParola = validParola(parolaNoua);
    if (eroareParola) {
      setRezultat({ eroare: eroareParola });
      return;
    }

    startTransition(async () => {
      setRezultat(await schimbaParola({ parolaActuala, parolaNoua }));
    });
  }

  return (
    <section className="flex flex-col gap-2">
      <Titlu copil="Parolă" />

      <div className="flex flex-col gap-3 rounded-card bg-muted px-4 py-4">
        {rezultat.eroare ? <Banda ton="eroare">{rezultat.eroare}</Banda> : null}
        {rezultat.mesaj ? <Banda ton="succes">{rezultat.mesaj}</Banda> : null}

        <Camp
          eticheta="Parola actuală"
          icoana={Lock}
          parola
          autoComplete="current-password"
          value={parolaActuala}
          onChange={(e) => setParolaActuala(e.target.value)}
          disabled={reusit}
          ajutor="Ți-o cerem ca nimeni să nu poată prelua contul de pe un ecran lăsat deschis."
        />

        <Camp
          eticheta="Parola nouă"
          icoana={Lock}
          parola
          autoComplete="new-password"
          value={parolaNoua}
          onChange={(e) => setParolaNoua(e.target.value)}
          disabled={reusit}
          ajutor="Minim 8 caractere, cu litere mari, mici și o cifră."
        />

        <Camp
          eticheta="Confirmă parola nouă"
          icoana={Lock}
          parola
          autoComplete="new-password"
          value={confirmare}
          onChange={(e) => setConfirmare(e.target.value)}
          disabled={reusit}
        />

        <Button
          onClick={trimite}
          loading={seTrimite}
          disabled={reusit || !parolaActuala || !parolaNoua}
          className="w-full"
        >
          {reusit ? "Parolă schimbată" : "Schimbă parola"}
        </Button>
      </div>
    </section>
  );
}

/* -------------------------------------------------------------------------- */
/* Dispozitive conectate                                                       */
/* -------------------------------------------------------------------------- */

/**
 * Scrie "Conectat ...", niciodata "Activ acum" si nicio bulina verde:
 * `creat_la` chiar inseamna primul login de pe dispozitivul acela, pe cand
 * ultima activitate se actualizeaza doar la login si la deschiderea setarilor
 * (vezi migratia 0019). Pe ecranul unde omul vine sa vada daca nu e altcineva
 * pe contul lui, un numar care minte e mai rau decat lipsa lui.
 *
 * Nu exista buton de deconectare per dispozitiv — vezi comentariul din
 * lib/actions/dispozitive.ts: platforma nu poate face asta, iar un buton care
 * doar ar sterge randul ar lasa dispozitivul logat.
 */
function SectiuneDispozitive({ dispozitive }: { dispozitive: DispozitivAfisat[] }) {
  const [eroare, setEroare] = useState<string | null>(null);
  const [gata, setGata] = useState(false);
  const [seTrimite, startTransition] = useTransition();

  const altele = dispozitive.filter((dispozitiv) => !dispozitiv.esteAcesta).length;

  function deconecteazaCelelalte() {
    setEroare(null);
    startTransition(async () => {
      const rezultat = await deconecteazaCelelalteDispozitive();
      if (rezultat.eroare) setEroare(rezultat.eroare);
      else setGata(true);
    });
  }

  return (
    <section className="flex flex-col gap-2">
      <Titlu copil="Dispozitive conectate" />

      {eroare ? <Banda ton="eroare">{eroare}</Banda> : null}
      {gata ? <Banda ton="succes">Celelalte dispozitive au fost deconectate.</Banda> : null}

      {dispozitive.length === 0 ? (
        <p className="rounded-card bg-muted px-4 py-3.5 text-[13px] leading-[19px] text-ink-soft">
          Nu am înregistrat încă niciun dispozitiv.
        </p>
      ) : (
        <ul className="flex flex-col gap-2">
          {dispozitive.map((dispozitiv) => (
            <li key={dispozitiv.id} className="flex items-center gap-3 rounded-card bg-muted px-4 py-3">
              {dispozitiv.mobil ? (
                <Smartphone size={20} strokeWidth={1.75} aria-hidden className="text-ink-faint" />
              ) : (
                <Laptop size={20} strokeWidth={1.75} aria-hidden className="text-ink-faint" />
              )}

              <span className="min-w-0 flex-1">
                <span className="block truncate text-[15px] text-ink">{dispozitiv.eticheta}</span>
                <span className="block text-[12.5px] text-ink-faint">
                  Conectat {etichetaZi(dispozitiv.conectatLa).toLowerCase()}, la{" "}
                  {formateazaOra(dispozitiv.conectatLa)}
                </span>
              </span>

              {dispozitiv.esteAcesta ? (
                <span className="shrink-0 rounded-full bg-primary-50 px-2.5 py-1 text-[11px] font-medium text-primary-700">
                  Acest dispozitiv
                </span>
              ) : null}
            </li>
          ))}
        </ul>
      )}

      <Button
        varianta="secondary"
        className="w-full"
        onClick={deconecteazaCelelalte}
        loading={seTrimite}
        disabled={altele === 0 || gata}
        iconaStanga={!seTrimite ? <LogOut size={18} strokeWidth={1.75} aria-hidden /> : undefined}
      >
        {altele === 0 || gata ? "Nu mai există alte dispozitive" : "Deconectează celelalte dispozitive"}
      </Button>
    </section>
  );
}

/* -------------------------------------------------------------------------- */

export function SecuritateDrawer({
  biometrieActivata,
  areSelfieVerificat,
  dispozitive,
}: {
  biometrieActivata: boolean;
  areSelfieVerificat: boolean;
  dispozitive: DispozitivAfisat[];
}) {
  const [deschis, setDeschis] = useState(false);
  // Cheie de remontare: la fiecare deschidere sectiunile pornesc curate, fara
  // parole ramase in campuri sau mesaje de la data trecuta.
  const [generatie, setGeneratie] = useState(0);

  useEffect(() => {
    if (deschis) setGeneratie((n) => n + 1);
  }, [deschis]);

  return (
    <Drawer open={deschis} onOpenChange={setDeschis}>
      <DrawerTrigger className="flex w-full items-center gap-3 rounded-card bg-surface px-4 py-3.5 text-left shadow-sm transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25">
        <ShieldCheck size={20} strokeWidth={1.75} aria-hidden className="text-ink-faint" />
        <span className="flex-1 text-[15px] text-ink">Securitate</span>
        <ChevronRight size={18} strokeWidth={1.75} aria-hidden className="text-ink-faint" />
      </DrawerTrigger>

      <DrawerContent
        title="Securitate"
        description="Cum intri în cont și de pe ce dispozitive s-a intrat."
      >
        <div key={generatie} className="flex flex-col gap-6">
          <SectiuneBiometrie activataInitial={biometrieActivata} areSelfie={areSelfieVerificat} />
          <SectiuneParola />
          <SectiuneDispozitive dispozitive={dispozitive} />
        </div>
      </DrawerContent>
    </Drawer>
  );
}
