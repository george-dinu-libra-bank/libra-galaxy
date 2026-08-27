"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Landmark, ScanFace, ShieldAlert, SpellCheck, TrendingUp, Users } from "lucide-react";
import { cn } from "@/lib/utils";

const SECTIUNI = [
  { href: "/admin", eticheta: "Verificări identitate", icoana: ScanFace },
  // Doua lucruri diferite, cu nume care se cereau despartite: aici sunt CONTURI
  // scoase in evidenta de statistica, iar in „Tranzacții suspecte" sunt plati
  // individuale oprite de scanerul de cuvinte (0036).
  { href: "/admin/tranzactii", eticheta: "Conturi semnalate", icoana: TrendingUp },
  { href: "/admin/tranzactii-suspecte", eticheta: "Tranzacții suspecte", icoana: ShieldAlert },
  { href: "/admin/securitate", eticheta: "Securitate", icoana: SpellCheck },
  { href: "/admin/credite", eticheta: "Credite", icoana: Landmark },
  { href: "/admin/conturi", eticheta: "Toate conturile", icoana: Users },
];

export function NavAdmin() {
  const pathname = usePathname();

  return (
    <nav
      className="flex gap-1 overflow-x-auto border-b border-line"
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
              "-mb-px flex items-center gap-2 border-b-2 px-4 py-3 text-[14px] font-medium transition-colors",
              activ
                ? "border-primary-600 text-primary-700"
                : "border-transparent text-ink-faint hover:text-ink-soft",
            )}
          >
            <Icoana size={17} strokeWidth={1.75} aria-hidden />
            {eticheta}
          </Link>
        );
      })}
    </nav>
  );
}
