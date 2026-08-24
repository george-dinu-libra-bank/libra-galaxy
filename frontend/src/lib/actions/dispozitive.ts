"use server";

import { revalidatePath } from "next/cache";
import { createAdminClient } from "@/lib/supabase/admin";
import { createClient } from "@/lib/supabase/server";

/**
 * Singura actiune din zona de dispozitive apelabila din browser. Restul
 * (inregistrarea dispozitivului la login, citirea listei) sta in
 * lib/data/dispozitive.ts, ca modul de server obisnuit — vezi comentariul de
 * acolo despre de ce nu e "use server".
 */

export type RezultatDispozitive = { eroare?: string };

/**
 * Inchide toate sesiunile contului in afara de cea curenta.
 *
 * NU exista buton de delogare per dispozitiv, si nu e o scapare:
 * GoTrueAdminApi din auth-js 2.109 expune doar `signOut(jwt, scope)`, adica
 * revocarea cere JWT-ul chiar al sesiunii pe care vrei s-o inchizi — pe care
 * serverul nu-l are. Un buton per rand ar putea doar sa stearga randul din
 * tabela noastra, lasand dispozitivul logat: o minciuna, exact pe ecranul unde
 * omul vine sa se asigure ca nu e cineva pe contul lui.
 */
export async function deconecteazaCelelalteDispozitive(): Promise<RezultatDispozitive> {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) return { eroare: "Trebuie sa fii autentificat." };

  const { data: revendicari } = await supabase.auth.getClaims();
  const idSesiune = revendicari?.claims?.session_id;

  // Intai revocarea la Supabase, si abia daca reuseste stergem randurile: in
  // ordinea inversa am ramane cu o lista goala si cu sesiuni inca vii pe alte
  // dispozitive — adica exact impresia gresita.
  //
  // scope 'others' lasa sesiunea curenta neatinsa si nu emite SIGNED_OUT, deci
  // utilizatorul ramane logat aici.
  const { error } = await supabase.auth.signOut({ scope: "others" });

  if (error) {
    console.error("[dispozitive/deconecteazaCelelalte] signOut", {
      status: error.status,
      code: error.code,
      message: error.message,
    });
    return { eroare: "Nu am putut deconecta celelalte dispozitive. Incearca din nou." };
  }

  const supabaseAdmin = await createAdminClient();
  let cerere = supabaseAdmin.from("dispozitive_conectate").delete().eq("id_user", user.id);

  // Se sterge tot in afara de randul sesiunii curente. `or(is.null, neq)`, nu
  // un simplu `neq`: pe o coloana nullable, `id_sesiune <> 'abc'` e NULL
  // pentru randurile fara sesiune, deci acelea ar SUPRAVIETUI stergerii — si
  // tocmai ele sunt cele pentru care nu putem garanta ca mai exista o sesiune
  // vie in spate. Echivalentul SQL corect e `is distinct from`.
  if (typeof idSesiune === "string") {
    cerere = cerere.or(`id_sesiune.is.null,id_sesiune.neq.${idSesiune}`);
  }

  const { error: eroareStergere } = await cerere;

  if (eroareStergere && eroareStergere.code !== "42P01" && eroareStergere.code !== "PGRST205") {
    console.error("[dispozitive/deconecteazaCelelalte] stergere", eroareStergere.message);
  }

  revalidatePath("/setari");
  return {};
}
