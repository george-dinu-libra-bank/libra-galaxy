"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ScanFace, TrendingUp, Users } from "lucide-react";
import { cn } from "@/lib/utils";

const SECTIUNI = [
  { href: "/admin", eticheta: "Verificări identitate", icoana: ScanFace },
  { href: "/admin/tranzactii", eticheta: "Tranzacții suspecte", icoana: TrendingUp },
  { href: "/admin/conturi", eticheta: "Toate conturile", icoana: Users },
];

export function NavAdmin() {
  const pathname = usePathname();

  return (
    <nav className="flex gap-1 border-b border-line" aria-label="Secțiuni administrare">
      {SECTIUNI.map(({ href, eticheta, icoana: Icoana }) => {
        // "/admin" ar fi prefix pentru tot; se compara exact, in afara de
        // sectiunile care au si pagini de detaliu sub ele.
        const activ =
          href === "/admin"
            ? pathname === "/admin" || pathname.startsWith("/admin/verificari")
            : pathname.startsWith(href);

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
