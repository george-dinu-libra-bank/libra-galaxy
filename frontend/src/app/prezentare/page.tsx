import type { Metadata } from "next";
import { cookies } from "next/headers";
import { BaraSus } from "@/components/prezentare/bara-sus";
import { Hero } from "@/components/prezentare/hero";
import { Cifre } from "@/components/prezentare/cifre";
import { Functii } from "@/components/prezentare/functii";
import { Pasi } from "@/components/prezentare/pasi";
import { Asistent } from "@/components/prezentare/asistent";
import { Securitate } from "@/components/prezentare/securitate";
import { Stack } from "@/components/prezentare/stack";
import { Final } from "@/components/prezentare/final";
import { TEMA_COOKIE, temaDinCookie } from "@/lib/tema";

export const metadata: Metadata = {
  title: "Galaxy Bank · Banca ta, în buzunar",
  description:
    "Cont curent cu IBAN românesc, transferuri instant, carduri, credite, grupuri cu sold comun și un asistent care îți explică unde ți s-au dus banii.",
};

/**
 * Landing-ul public. Sta in afara grupului `(app)`, deci fara bara de navigatie
 * a aplicatiei, si e trecut in `RUTE_PUBLICE` (lib/supabase/middleware.ts) ca sa
 * fie vizibil fara cont.
 */
export default async function PrezentarePage() {
  const tema = temaDinCookie((await cookies()).get(TEMA_COOKIE)?.value);

  return (
    <>
      <BaraSus tema={tema} />
      <main>
        <Hero />
        <Cifre />
        <Functii />
        <Pasi />
        <Asistent />
        <Securitate />
        <Stack />
        <Final />
      </main>
    </>
  );
}
