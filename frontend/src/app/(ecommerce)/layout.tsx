import type { ReactNode } from "react";
import { ShopHeader } from "@/components/shop/shop-header";

/**
 * Cadrul magazinului (grup de rute separat de (app)): fara verificare de
 * sesiune, fara bara de jos — e o vitrina publica, nu partea bancara.
 */
export default function EcommerceLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-dvh">
      <ShopHeader />
      {children}
    </div>
  );
}
