import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { ArrowLeftRight, Banknote, Bell, ChevronRight, CreditCard, Users } from "lucide-react";
import { AvatarUtilizator } from "@/components/dashboard/avatar-utilizator";
import { DetaliiContDrawer } from "@/components/dashboard/detalii-cont-drawer";
import { ListaConturi } from "@/components/dashboard/lista-conturi";
import { SchimbValutarDrawer } from "@/components/dashboard/schimb-valutar-drawer";
import { SoldAnimat } from "@/components/dashboard/sold-animat";
import { UltimeleTranzactii } from "@/components/dashboard/ultimele-tranzactii";
import { VerificaIdentitateBanner } from "@/components/dashboard/verifica-identitate-banner";
import { Banda } from "@/components/ui/banda";
import { obtineConturiUtilizator, totalSold } from "@/lib/data/conturi";
import { obtineCursuri } from "@/lib/data/curs-valutar";
import { obtineTranzactiiUtilizator } from "@/lib/data/tranzactii";
import { createClient } from "@/lib/supabase/server";

export const metadata: Metadata = {
  title: "Contul meu · Galaxy Bank",
};

// Istoricul a iesit de aici in favoarea schimbului valutar: e la un tap distanta
// in bara de jos, pe cand schimbul n-avea niciun drum catre el.
const ACTIUNI = [
  { eticheta: "Transfer", href: "/transfer", icoana: ArrowLeftRight },
  { eticheta: "Carduri", href: "/carduri", icoana: CreditCard },
  { eticheta: "Beneficiari", href: "/beneficiari", icoana: Users },
];

/** Stilul unei dale din grila — impartit intre linkuri si declansatorul de drawer. */
const DALA =
  "flex aspect-square flex-col items-center justify-center gap-2 rounded-[18px] bg-surface p-2 shadow-sm transition-[transform,box-shadow] duration-[180ms] ease-soft hover:shadow-md active:scale-[0.98] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25";

/** Cate miscari incap in rezumatul de pe dashboard; restul stau in /istoric. */
const TRANZACTII_REZUMAT = 5;

export default async function DashboardPage() {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) redirect("/login");

  const { data: profil } = await supabase
    .from("profiles")
    .select("nume, cnp, telefon, email, iban_cont, creat_la, avatar_url, verification_status")
    .eq("id", user.id)
    .single();

  const prenume = profil?.nume?.split(" ").at(-1) ?? "";
  const conturi = await obtineConturiUtilizator();
  const tranzactii = await obtineTranzactiiUtilizator(TRANZACTII_REZUMAT);
  const cursuri = await obtineCursuri();

  // Totalul se aduna aici, pe server — cifra ajunge gata calculata in HTML.
  // Conturile pot fi in valute diferite, deci se aduc intai la RON.
  const total = totalSold(conturi, cursuri);

  return (
    <div className="mx-auto w-full max-w-[440px] px-6 pb-6 pt-8 sm:max-w-2xl">
      <header className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-[13px] text-ink-faint">Salut,</p>
          <h1 className="truncate text-xl font-bold tracking-[-0.02em] text-ink">
            {prenume || "client Galaxy Bank"}
          </h1>

          <p className="mt-3 text-[13px] text-ink-faint">
            Total în {conturi.length === 1 ? "cont" : `${conturi.length} conturi`}
          </p>
          <SoldAnimat
            sold={total}
            className="tabular text-[30px] font-bold leading-[36px] text-ink"
          />
        </div>

        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-surface text-ink-soft shadow-sm">
          <Bell size={20} strokeWidth={1.75} aria-hidden />
        </span>

        <AvatarUtilizator
          avatarUrl={profil?.avatar_url ?? null}
          nume={profil?.nume ?? "client Galaxy Bank"}
        />
      </header>

      {profil ? (
        <>
          {profil.verification_status === "pending_review" ? (
            <div className="mt-4">
              <Banda ton="info">
                Verificarea identitatii este in curs de revizuire manuala. Unele
                actiuni pot fi limitate pana la finalizare.
              </Banda>
            </div>
          ) : profil.verification_status === "pending" ? (
            <div className="mt-4">
              <VerificaIdentitateBanner />
            </div>
          ) : null}

          <ListaConturi conturi={conturi} />

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

      <Link
        href="/credite"
        className="mt-6 flex items-center gap-3 rounded-card bg-surface p-5 shadow-sm transition-[transform,box-shadow] duration-[180ms] ease-soft hover:shadow-md active:scale-[0.99] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
      >
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-primary-50 text-primary-600">
          <Banknote size={20} strokeWidth={1.75} aria-hidden />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-[15px] font-medium text-ink">Credite</span>
          <span className="block text-[13px] text-ink-faint">
            Simuleaza o rata sau vezi creditele tale
          </span>
        </span>
        <ChevronRight size={20} strokeWidth={1.75} aria-hidden className="shrink-0 text-ink-faint" />
      </Link>

      <h2 className="mt-8 text-lg font-semibold text-ink">Actiuni rapide</h2>

      <div className="mt-4 grid grid-cols-4 gap-3">
        {ACTIUNI.map(({ eticheta, href, icoana: Icoana }) => (
          <Link key={eticheta} href={href} className={DALA}>
            <Icoana size={22} strokeWidth={1.75} aria-hidden className="text-primary-600" />
            <span className="text-center text-xs leading-4 text-ink-soft">
              {eticheta}
            </span>
          </Link>
        ))}

        {/* Singura dala care nu duce nicaieri: deschide un drawer peste ecran. */}
        <SchimbValutarDrawer conturi={conturi} cursuri={cursuri} className={DALA} />
      </div>

      <UltimeleTranzactii tranzactii={tranzactii} />
    </div>
  );
}
