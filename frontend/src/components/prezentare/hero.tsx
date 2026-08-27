"use client";

import Link from "next/link";
import { ArrowRight, ShieldCheck } from "lucide-react";
import BlurText from "@/components/reactbits/BlurText";
import ShinyText from "@/components/reactbits/ShinyText";
import ClickSpark from "@/components/reactbits/ClickSpark";
import Magnet from "@/components/reactbits/Magnet";
import TiltedCard from "@/components/reactbits/TiltedCard";
import { useMiscareRedusa } from "@/hooks/use-miscare-redusa";
import { RamaTelefon } from "./rama-telefon";
import { CAPTURI } from "./capturi";

const TITLU = "Banca ta, în buzunar.";

export function Hero() {
  const miscareRedusa = useMiscareRedusa();

  const continut = (
    <div className="relative z-10 mx-auto flex w-full max-w-6xl flex-col items-center gap-12 px-5 py-16 sm:px-8 lg:flex-row lg:items-center lg:justify-between lg:py-24">
      <div className="flex max-w-[560px] flex-col items-center text-center lg:items-start lg:text-left">
        <span className="inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-3 py-1.5 text-[12.5px] font-medium">
          <ShieldCheck size={16} strokeWidth={1.75} aria-hidden className="text-primary-100" />
          {miscareRedusa ? (
            <span className="text-primary-100">Cont curent cu IBAN românesc</span>
          ) : (
            <ShinyText
              text="Cont curent cu IBAN românesc"
              color="var(--color-primary-100)"
              shineColor="#ffffff"
              speed={4}
            />
          )}
        </span>

        {miscareRedusa ? (
          <h1 className="mt-5 text-[34px] font-bold leading-[40px] tracking-[-0.02em] text-white sm:text-[44px] sm:leading-[50px]">
            {TITLU}
          </h1>
        ) : (
          <BlurText
            text={TITLU}
            animateBy="words"
            direction="top"
            delay={90}
            stepDuration={0.24}
            className="mt-5 justify-center text-[34px] font-bold leading-[40px] tracking-[-0.02em] text-white sm:text-[44px] sm:leading-[50px] lg:justify-start"
          />
        )}

        <p className="mt-4 max-w-[46ch] text-[16px] leading-[24px] text-primary-100">
          Deschizi contul în câteva minute, trimiți bani instant, ceri un credit și
          întrebi asistentul unde ți s-au dus banii. Totul dintr-un singur ecran.
        </p>

        <div className="mt-8 flex flex-col items-center gap-3 sm:flex-row">
          <Magnet padding={80} disabled={miscareRedusa} magnetStrength={6}>
            <Link
              href="/register"
              className="inline-flex h-[52px] items-center justify-center gap-2 rounded-field bg-white px-7 text-[15px] font-semibold text-primary-700 shadow-lg transition-transform hover:brightness-95 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-white/40 active:scale-[0.98]"
            >
              Deschide un cont
              <ArrowRight size={18} strokeWidth={1.75} aria-hidden />
            </Link>
          </Magnet>

          <Link
            href="/login"
            className="inline-flex h-[52px] items-center justify-center rounded-field border border-white/25 px-7 text-[15px] font-semibold text-white transition-colors hover:bg-white/10 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-white/40"
          >
            Am deja cont
          </Link>
        </div>

        <p className="mt-5 text-[12.5px] leading-[18px] text-primary-200">
          Aplicație demonstrativă. Conturile și banii sunt de test.
        </p>
      </div>

      <div className="w-full max-w-[300px] shrink-0">
        {miscareRedusa ? (
          <RamaTelefon captura={CAPTURI.dashboard} priority />
        ) : (
          <TiltedCard
            containerHeight="auto"
            containerWidth="100%"
            rotateAmplitude={9}
            scaleOnHover={1.03}
            showTooltip={false}
          >
            <RamaTelefon captura={CAPTURI.dashboard} priority />
          </TiltedCard>
        )}
      </div>
    </div>
  );

  return (
    <section className="hero-gradient relative isolate overflow-hidden">
      {/* Cele doua cercuri albe, difuze, din DESIGN.md 2.4. */}
      <span
        aria-hidden
        className="pointer-events-none absolute -left-32 -top-40 h-[420px] w-[420px] rounded-full bg-white/[0.08] blur-3xl"
      />
      <span
        aria-hidden
        className="pointer-events-none absolute -bottom-48 -right-24 h-[460px] w-[460px] rounded-full bg-white/[0.08] blur-3xl"
      />

      {miscareRedusa ? (
        continut
      ) : (
        <ClickSpark sparkColor="#ffffff" sparkSize={8} sparkRadius={18} duration={320}>
          {continut}
        </ClickSpark>
      )}
    </section>
  );
}
