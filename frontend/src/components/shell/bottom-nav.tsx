"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  ArrowLeftRight,
  CreditCard,
  History,
  Home,
  Settings,
  Sparkles,
  Users,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";

type Item = { href: string; eticheta: string; icoana: LucideIcon };

// Transferul sta la mijloc (al patrulea din sapte), ca butonul rotund sa cada
// exact in centrul barii.
const ITEMI: Item[] = [
  { href: "/dashboard", eticheta: "Acasă", icoana: Home },
  { href: "/istoric", eticheta: "Istoric", icoana: History },
  { href: "/grupuri", eticheta: "Grupuri", icoana: Users },
  { href: "/transfer", eticheta: "Transfer", icoana: ArrowLeftRight },
  { href: "/asistent", eticheta: "Asistent", icoana: Sparkles },
  { href: "/carduri", eticheta: "Carduri", icoana: CreditCard },
  { href: "/setari", eticheta: "Setări", icoana: Settings },
];

/** Navigatia principala a ecranelor autentificate. Vezi DESIGN.md 5 si 8.1. */
export function BottomNav() {
  const pathname = usePathname();

  return (
    <nav
      aria-label="Navigare principala"
      className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-surface pb-[env(safe-area-inset-bottom)]"
    >
      {/* Sapte destinatii incap pe 360 px doar cu marginile stranse si eticheta
          la 10 px; de la sm in sus revine la 11 px, ca in DESIGN.md 8.1. */}
      <div className="mx-auto flex w-full max-w-[440px] items-end justify-between px-1 sm:max-w-2xl sm:px-6">
        {ITEMI.map(({ href, eticheta, icoana: Icoana }) => {
          const activ = pathname === href || pathname.startsWith(`${href}/`);

          if (href === "/transfer") {
            return (
              <Link
                key={href}
                href={href}
                aria-label={eticheta}
                aria-current={activ ? "page" : undefined}
                className="-mt-5 flex flex-1 flex-col items-center gap-1 pb-2 pt-1"
              >
                <span className="flex h-12 w-12 items-center justify-center rounded-full bg-primary-600 text-white shadow-btn transition-transform duration-150 ease-soft active:scale-[0.96]">
                  <Icoana size={22} strokeWidth={1.75} aria-hidden />
                </span>
                <span
                  className={cn(
                    "whitespace-nowrap text-[10px] font-medium leading-4 sm:text-[11px]",
                    activ ? "text-primary-600" : "text-ink-faint",
                  )}
                >
                  {eticheta}
                </span>
              </Link>
            );
          }

          return (
            <Link
              key={href}
              href={href}
              aria-label={eticheta}
              aria-current={activ ? "page" : undefined}
              className="flex flex-1 flex-col items-center gap-1 py-2.5 focus-visible:outline-none"
            >
              <Icoana
                size={22}
                strokeWidth={1.75}
                aria-hidden
                className={activ ? "text-primary-600" : "text-ink-faint"}
              />
              <span
                className={cn(
                  "whitespace-nowrap text-[10px] font-medium leading-4 sm:text-[11px]",
                  activ ? "text-primary-600" : "text-ink-faint",
                )}
              >
                {eticheta}
              </span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
