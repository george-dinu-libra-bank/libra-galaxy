import type { Metadata } from "next";
import { redirect } from "next/navigation";
import {
  ArrowLeftRight,
  Bell,
  CreditCard,
  Landmark,
  PiggyBank,
  Receipt,
  Smartphone,
} from "lucide-react";
import { DetaliiContDrawer } from "@/components/dashboard/detalii-cont-drawer";
import { createClient } from "@/lib/supabase/server";
import { formateazaIban } from "@/lib/utils";

export const metadata: Metadata = {
  title: "Contul meu · Libra",
};

const ACTIUNI = [
  { eticheta: "Transfer", icoana: ArrowLeftRight },
  { eticheta: "Card nou", icoana: CreditCard },
  { eticheta: "Plateste factura", icoana: Receipt },
  { eticheta: "Reincarcare", icoana: Smartphone },
  { eticheta: "Economii", icoana: PiggyBank },
  { eticheta: "Conturi", icoana: Landmark },
];

export default async function DashboardPage() {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) redirect("/login");

  const { data: profil } = await supabase
    .from("profiles")
    .select("nume, cnp, telefon, email, iban_cont, creat_la")
    .eq("id", user.id)
    .single();

  const prenume = profil?.nume?.split(" ").at(-1) ?? "";

  return (
    <div className="min-h-dvh bg-bg">
      <div className="mx-auto w-full max-w-[440px] px-6 pb-12 pt-8 sm:max-w-2xl">
        <header className="flex items-center justify-between">
          <div>
            <p className="text-[13px] text-ink-faint">Salut,</p>
            <h1 className="text-xl font-bold tracking-[-0.02em] text-ink">
              {prenume || "client Libra"}
            </h1>
          </div>

          <span className="flex h-11 w-11 items-center justify-center rounded-full bg-surface text-ink-soft shadow-sm">
            <Bell size={20} strokeWidth={1.75} aria-hidden />
          </span>
        </header>

        {profil ? (
          <>
            <section className="hero-gradient mt-6 animate-fade-up rounded-card p-6 text-white shadow-lg">
              <p className="text-[13px] text-primary-100">Cont curent</p>
              <p className="tabular mt-1 text-[15px] tracking-[0.02em]">
                {formateazaIban(profil.iban_cont)}
              </p>
              <p className="tabular mt-6 text-[32px] font-bold leading-[38px]">
                0,00 RON
              </p>
              <p className="mt-1 text-[13px] text-primary-100">
                Disponibil · alimenteaza contul ca sa incepi
              </p>
            </section>

            <div className="mt-4">
              <DetaliiContDrawer profil={profil} />
            </div>
          </>
        ) : (
          <section className="mt-6 rounded-card bg-surface p-6 shadow-sm">
            <p className="text-[15px] leading-[22px] text-ink-soft">
              Profilul nu a fost gasit. Ruleaza migrarea din{" "}
              <code className="tabular rounded bg-muted px-1.5 py-0.5 text-[13px]">
                supabase/migrations/0001_profiles.sql
              </code>{" "}
              si inregistreaza-te din nou.
            </p>
          </section>
        )}

        <h2 className="mt-8 text-lg font-semibold text-ink">Actiuni rapide</h2>

        <div className="mt-4 grid grid-cols-3 gap-3">
          {ACTIUNI.map(({ eticheta, icoana: Icoana }) => (
            <button
              key={eticheta}
              type="button"
              className="flex aspect-square flex-col items-center justify-center gap-2 rounded-[18px] bg-surface p-2 shadow-sm transition-[transform,box-shadow] duration-[180ms] ease-soft hover:shadow-md active:scale-[0.98] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
            >
              <Icoana size={22} strokeWidth={1.75} aria-hidden className="text-primary-600" />
              <span className="text-center text-xs leading-4 text-ink-soft">
                {eticheta}
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
