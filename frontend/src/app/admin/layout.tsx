import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";
import { ShieldCheck } from "lucide-react";
import { NavAdmin } from "@/components/admin/nav-admin";
import { cereAdmin } from "@/lib/admin";

export const metadata: Metadata = {
  title: "Administrare · Galaxy Bank",
};

/**
 * Cadrul zonei de administrare.
 *
 * Garda e aici, pe server, si se reia pe fiecare pagina prin `cereAdmin`.
 * Ascunderea unui ecran nu e o bariera: rutele backendului sunt verificate
 * separat, fiindca pot fi chemate direct.
 *
 * Zona nu are navigarea de jos a aplicatiei: e alt fel de lucru, facut de alt
 * fel de om, si nu vrem sa para inca un ecran de client.
 */
export default async function AdminLayout({ children }: { children: ReactNode }) {
  const admin = await cereAdmin();

  return (
    <div className="min-h-dvh bg-bg">
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex w-full max-w-5xl items-center justify-between px-6 py-4">
          <Link href="/admin" className="flex items-center gap-3">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary-600 text-white">
              <ShieldCheck size={18} strokeWidth={1.75} aria-hidden />
            </span>
            <span>
              <span className="block text-[15px] font-semibold leading-5 text-ink">
                Administrare
              </span>
              <span className="block text-[12.5px] leading-4 text-ink-faint">Galaxy Bank</span>
            </span>
          </Link>

          <div className="flex items-center gap-4">
            <span className="hidden text-[13px] text-ink-faint sm:block">{admin.email}</span>
            <Link
              href="/dashboard"
              className="rounded-field px-3 py-2 text-[13px] font-semibold text-primary-600 transition-colors hover:bg-primary-50"
            >
              Înapoi în aplicație
            </Link>
          </div>
        </div>
      </header>

      <div className="mx-auto w-full max-w-5xl px-6">
        <NavAdmin />
      </div>

      <main className="mx-auto w-full max-w-5xl px-6 py-8">{children}</main>
    </div>
  );
}
