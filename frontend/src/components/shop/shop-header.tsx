import Link from "next/link";
import { Rocket, ShoppingBag } from "lucide-react";

/** Antetul magazinului — separat de barul de navigare al aplicatiei bancare. */
export function ShopHeader() {
  return (
    <header className="sticky top-0 z-20 flex items-center justify-between border-b border-line bg-surface/90 px-5 py-4 backdrop-blur">
      <Link href="/shop" className="flex items-center gap-2">
        <span className="flex h-9 w-9 items-center justify-center rounded-field bg-primary-600 text-white">
          <Rocket size={18} strokeWidth={1.75} aria-hidden />
        </span>
        <span className="text-[16px] font-semibold text-ink">Galaxy Shop</span>
      </Link>

      <Link
        href="/dashboard"
        className="flex items-center gap-1.5 rounded-field px-3 py-2 text-[13px] font-medium text-ink-soft transition-colors hover:bg-muted hover:text-ink"
      >
        <ShoppingBag size={16} strokeWidth={1.75} aria-hidden />
        Contul meu
      </Link>
    </header>
  );
}
