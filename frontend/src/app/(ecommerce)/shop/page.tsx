import type { Metadata } from "next";
import { ProdusCard } from "@/components/shop/produs-card";
import { PRODUSE } from "@/lib/data/produse";

export const metadata: Metadata = {
  title: "Galaxy Shop · Libra",
};

export default function ShopPage() {
  return (
    <main className="mx-auto flex w-full max-w-2xl flex-col gap-5 px-5 py-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-[22px] font-semibold leading-7 text-ink">Galaxy Shop</h1>
        <p className="text-[13.5px] leading-[19px] text-ink-faint">
          O selecție restrânsă de gadget-uri. Plătești direct cu cardul.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3.5 sm:grid-cols-3">
        {PRODUSE.map((produs) => (
          <ProdusCard key={produs.slug} produs={produs} />
        ))}
      </div>
    </main>
  );
}
