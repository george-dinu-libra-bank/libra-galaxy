"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Inbox,
  Landmark,
  MessagesSquare,
  ScanFace,
  ShieldAlert,
  SpellCheck,
  TrendingUp,
  Users,
} from "lucide-react";
import { cn } from "@/lib/utils";

const SECTIUNI = [
  { href: "/admin", eticheta: "Identitate", icoana: ScanFace },
  // Doua lucruri diferite, care se confundau cat timp amandoua se numeau
  // „tranzactii". Aici sunt CONTURI scoase in evidenta de model, unde banii au
  // plecat deja si te uiti retrospectiv. In „Transferuri oprite" sunt plati
  // individuale blocate de scanerul de cuvinte (0043), cu banii stand pe loc
  // pana apasa cineva ceva — de aceea numele spune ce s-a intamplat cu ele,
  // nu cat de suspecte par.
  { href: "/admin/tranzactii", eticheta: "Conturi semnalate", icoana: TrendingUp },
  { href: "/admin/tranzactii-suspecte", eticheta: "Transferuri oprite", icoana: ShieldAlert },
  // Firele deschise de banca, pornite din raportul unui cont semnalat.
  { href: "/admin/investigatii", eticheta: "Investigații", icoana: MessagesSquare },
  { href: "/admin/securitate", eticheta: "Securitate", icoana: SpellCheck },
  { href: "/admin/credite", eticheta: "Credite", icoana: Landmark },
  { href: "/admin/conturi", eticheta: "Clienți", icoana: Users },
  { href: "/admin/sesizari", eticheta: "Sesizări", icoana: Inbox },
];

export function NavAdmin() {
  const pathname = usePathname();

  return (
    <nav
      // `flex-wrap`, nu derulare orizontală: cu opt secțiuni, fâșia depășea
      // marginea pe ecrane obișnuite și tăia ultima filă în două, făcând-o să
      // pară inexistentă. Când nu încap pe un rând, trec pe următorul — nimic
      // nu rămâne ascuns după margine, oricât de îngustă e fereastra.
      className="flex flex-wrap gap-x-0.5 border-b border-line"
      aria-label="Secțiuni administrare"
    >
      {SECTIUNI.map(({ href, eticheta, icoana: Icoana }) => {
        // "/admin" ar fi prefix pentru tot; se compara exact, in afara de
        // sectiunile care au si pagini de detaliu sub ele.
        //
        // Prefixul se opreste la granita de segment: fara "/", "/admin/tranzactii"
        // s-ar aprinde si pe "/admin/tranzactii-suspecte", care e alta sectiune.
        const activ =
          href === "/admin"
            ? pathname === "/admin" || pathname.startsWith("/admin/verificari")
            : pathname === href || pathname.startsWith(`${href}/`);

        return (
          <Link
            key={href}
            href={href}
            aria-current={activ ? "page" : undefined}
            className={cn(
              // `whitespace-nowrap` e ce ține rândul uniform: fără el, o
              // etichetă din două cuvinte se rupea pe două linii iar „Credite"
              // rămânea pe una, și fiecare filă avea altă înălțime.
              "-mb-px flex shrink-0 items-center gap-1.5 whitespace-nowrap border-b-2 px-3 py-2.5",
              "text-[13px] font-medium transition-colors",
              activ
                ? "border-primary-600 text-primary-700"
                : "border-transparent text-ink-faint hover:text-ink-soft",
            )}
          >
            <Icoana size={15} strokeWidth={1.75} aria-hidden className="shrink-0" />
            {eticheta}
          </Link>
        );
      })}
    </nav>
  );
}
