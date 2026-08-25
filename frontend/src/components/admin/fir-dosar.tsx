"use client";

import { ConversatieCerere } from "@/components/credite/conversatie-cerere";
import { raspundeInFir } from "@/lib/actions/admin-credite";
import type { MesajCerere } from "@/lib/tipuri-admin";

/**
 * Firul dosarului, pe partea analistului.
 *
 * Invelis subtire peste `ConversatieCerere` — componenta de fir e scrisa o
 * singura data si folosita de ambele parti, cu `parteaMea` ca unica diferenta.
 * Doua copii ar diverge la primul bug reparat in una din ele (REGULI.md #2),
 * iar aici bug-ul ar insemna ca un om nu-si vede raspunsul.
 *
 * Pe un dosar inchis firul se citeste, dar **nu** se mai scrie. Varianta
 * anterioara promitea asta in comentariu si randa totusi caseta in ambele
 * ramuri, cu un `trimite` care intorcea eroare: analistul scria mesajul intreg,
 * apasa trimite, si abia atunci afla ca nu se poate.
 */
export function FirDosar({
  idCerere,
  mesaje,
  inLucru,
}: {
  idCerere: string;
  mesaje: MesajCerere[];
  inLucru: boolean;
}) {
  if (!inLucru && mesaje.length === 0) return null;

  return (
    <section className="rounded-card border border-line bg-surface p-5">
      <h2 className="text-[15px] font-semibold text-ink">Discuția cu clientul</h2>
      <p className="mt-1 text-[13px] leading-[19px] text-ink-faint">
        {inLucru
          ? "Tot ce v-ați scris pe dosarul ăsta, plus documentele încărcate. Acțiunile de mai jos își pun și ele textul aici."
          : "Dosarul e închis, deci discuția pe el s-a încheiat. Firul rămâne ca dovadă a ce v-ați spus."}
      </p>

      <div className="mt-4">
        <ConversatieCerere
          mesaje={mesaje}
          parteaMea="analist"
          trimite={(text) => raspundeInFir(idCerere, text)}
          eticheta="Fir"
          doarCitire={!inLucru}
        />
      </div>
    </section>
  );
}
