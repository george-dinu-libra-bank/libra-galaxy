import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ChevronLeft } from "lucide-react";
import { CumparaDrawer } from "@/components/shop/cumpara-drawer";
import { ProdusVizual } from "@/components/shop/produs-vizual";
import { obtineProdus, PRODUSE } from "@/lib/data/produse";
import { formateazaSuma } from "@/lib/utils";

export function generateStaticParams() {
  return PRODUSE.map((produs) => ({ slug: produs.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const produs = obtineProdus(slug);

  return { title: produs ? `${produs.nume} · Galaxy Shop` : "Galaxy Shop" };
}

export default async function ProdusPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const produs = obtineProdus(slug);

  if (!produs) notFound();

  // Pagina nu mai stie nimic despre sesiune: plata se face cu datele cardului, ca
  // la orice comerciant, iar banca gaseste singura posesorul si il intreaba pe el.
  return (
    <main className="mx-auto flex w-full max-w-2xl flex-col gap-6 px-5 py-6">
      <Link
        href="/shop"
        className="-ml-2 inline-flex h-10 w-fit items-center gap-1 rounded-xl px-2 text-[13px] font-medium text-ink-soft transition-colors hover:text-primary-700 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
      >
        <ChevronLeft size={18} strokeWidth={1.75} aria-hidden />
        Magazin
      </Link>

      <ProdusVizual produs={produs} marime="detaliu" alt={produs.nume} className="max-w-sm" />

      <div className="flex flex-col gap-2">
        <h1 className="text-[22px] font-semibold leading-7 text-ink">{produs.nume}</h1>
        <p className="tabular text-[20px] font-semibold text-primary-600">
          {formateazaSuma(produs.pret)}
        </p>
        <p className="text-[14.5px] leading-[21px] text-ink-soft">{produs.descriere}</p>
      </div>

      <CumparaDrawer slug={produs.slug} />
    </main>
  );
}
