import Link from "next/link";
import { ArrowRight, Landmark, ShieldCheck, Zap } from "lucide-react";

const AVANTAJE = [
  { icoana: Zap, titlu: "Transfer instant", text: "Trimiti bani in cateva secunde, oricand." },
  { icoana: ShieldCheck, titlu: "Cont sigur", text: "Autentificare cu Supabase si date criptate." },
  { icoana: Landmark, titlu: "IBAN romanesc", text: "Primesti IBAN-ul imediat dupa inregistrare." },
];

export default function Home() {
  return (
    <main className="min-h-dvh bg-bg">
      <div className="mx-auto flex min-h-dvh w-full max-w-[440px] flex-col justify-center gap-10 px-6 py-12 sm:max-w-xl">
        <div className="animate-fade-up">
          <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary-600 shadow-btn">
            <Landmark size={24} strokeWidth={1.75} className="text-white" aria-hidden />
          </span>

          <h1 className="mt-6 text-[32px] font-bold leading-[38px] tracking-[-0.02em] text-ink">
            Banca ta, in buzunar.
          </h1>
          <p className="mt-3 text-[15px] leading-[22px] text-ink-soft">
            Deschide un cont curent Libra in cateva minute si trimite bani
            instant catre orice cont din tara.
          </p>
        </div>

        <ul className="flex flex-col gap-3">
          {AVANTAJE.map(({ icoana: Icoana, titlu, text }) => (
            <li
              key={titlu}
              className="flex items-start gap-3 rounded-card bg-surface p-4 shadow-sm"
            >
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary-50">
                <Icoana size={20} strokeWidth={1.75} aria-hidden className="text-primary-600" />
              </span>
              <div>
                <p className="text-[15px] font-semibold text-ink">{titlu}</p>
                <p className="text-[13px] leading-[19px] text-ink-soft">{text}</p>
              </div>
            </li>
          ))}
        </ul>

        <div className="flex flex-col gap-3">
          <Link
            href="/register"
            className="inline-flex h-[52px] w-full items-center justify-center gap-2 rounded-field bg-primary-600 text-[15px] font-semibold text-white shadow-btn transition-colors hover:bg-primary-700 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
          >
            Deschide un cont
            <ArrowRight size={18} strokeWidth={1.75} aria-hidden />
          </Link>

          <Link
            href="/login"
            className="inline-flex h-[52px] w-full items-center justify-center rounded-field border border-primary-100 bg-primary-50 text-[15px] font-semibold text-primary-700 transition-colors hover:bg-primary-100 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
          >
            Am deja cont
          </Link>
        </div>
      </div>
    </main>
  );
}
