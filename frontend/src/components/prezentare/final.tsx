import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { Logo } from "@/components/ui/logo";
import StarBorder from "@/components/reactbits/StarBorder";

const LINKURI = [
  { href: "/register", text: "Deschide un cont" },
  { href: "/login", text: "Autentificare" },
  { href: "/shop", text: "Galaxy Shop" },
];

export function Final() {
  return (
    <footer className="mx-auto w-full max-w-6xl px-5 pb-16 pt-4 sm:px-8">
      <StarBorder
        as="div"
        className="block w-full"
        speed="7s"
        thickness={2}
        innerClassName="flex flex-col items-center gap-6 px-6 py-12 text-center sm:px-10"
      >
        <Logo size={56} />

        <div>
          <h2 className="text-[26px] font-bold leading-8 tracking-[-0.02em] text-ink">
            Deschide-ți contul în câteva minute
          </h2>
          <p className="mx-auto mt-3 max-w-[46ch] text-[15px] leading-[22px] text-ink-soft">
            Nu-ți trebuie decât un email și buletinul. Restul se întâmplă în aplicație.
          </p>
        </div>

        <Link
          href="/register"
          className="inline-flex h-[52px] items-center justify-center gap-2 rounded-field bg-primary-600 px-7 text-[15px] font-semibold text-white shadow-btn transition-colors hover:bg-primary-700 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25 active:scale-[0.98]"
        >
          Deschide un cont
          <ArrowRight size={18} strokeWidth={1.75} aria-hidden />
        </Link>
      </StarBorder>

      <nav
        className="mt-8 flex flex-wrap items-center justify-center gap-x-2 gap-y-1"
        aria-label="Linkuri utile"
      >
        {LINKURI.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className="flex h-11 items-center rounded-field px-3 text-[13.5px] text-ink-soft transition-colors hover:bg-primary-50 hover:text-primary-700 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
          >
            {link.text}
          </Link>
        ))}
      </nav>

      <p className="mt-2 text-center text-[12.5px] leading-[18px] text-ink-faint">
        Galaxy Bank — aplicație demonstrativă. Nu este o instituție financiară reală și nu
        administrează bani adevărați.
      </p>
    </footer>
  );
}
