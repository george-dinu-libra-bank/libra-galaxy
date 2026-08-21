"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { ScanFace } from "lucide-react";
import { SelfieCapture } from "@/components/auth/selfie-capture";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { Drawer, DrawerContent } from "@/components/ui/drawer";
import { restabilesteBiometrie } from "@/lib/actions/admin-verificari";

/**
 * Restabileste referinta biometrica a unui cont, cu o poza noua — pentru
 * cazul in care pozele din storage au disparut (sterse din greseala) si
 * login-ul biometric a ramas fara nimic de comparat.
 *
 * Poza intra direct ca reper 'verified': administratorul o atesta, nu mai
 * trece prin OCR/comparatie automata (vezi admin_identity_service.restabileste_biometrie).
 */
export function RestabilesteBiometrie({ userId, nume }: { userId: string; nume: string }) {
  const router = useRouter();
  const [deschis, setDeschis] = useState(false);
  const [eroare, setEroare] = useState<string | null>(null);
  const [, startTransition] = useTransition();

  function trimite(fisier: File) {
    setEroare(null);
    startTransition(async () => {
      const rezultat = await restabilesteBiometrie(userId, fisier);

      if (rezultat.eroare) {
        setEroare(rezultat.eroare);
        return;
      }

      setDeschis(false);
      router.refresh();
    });
  }

  return (
    <>
      <Button
        varianta="ghost"
        iconaStanga={<ScanFace size={16} strokeWidth={1.75} aria-hidden />}
        onClick={() => setDeschis(true)}
      >
        Restabilește biometria
      </Button>

      <Drawer
        open={deschis}
        onOpenChange={(deschis) => {
          if (!deschis) {
            setDeschis(false);
            setEroare(null);
          }
        }}
      >
        <DrawerContent
          title="Restabilește referința biometrică"
          description={`O poză nouă devine reperul pentru login-ul biometric al lui ${nume}.`}
        >
          {eroare ? (
            <div className="mb-3">
              <Banda ton="eroare">{eroare}</Banda>
            </div>
          ) : null}

          <SelfieCapture onFinalizat={trimite} />
        </DrawerContent>
      </Drawer>
    </>
  );
}
