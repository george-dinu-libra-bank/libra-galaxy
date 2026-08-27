import { cereAdmin } from "@/lib/admin";
import { obtineCuvinteSalvate, type ListaCuvinte } from "@/lib/data/admin-securitate";
import { Banda } from "@/components/ui/banda";
import { EditorCuvinteSensibile } from "@/components/admin/editor-cuvinte-sensibile";

export const dynamic = "force-dynamic";

export default async function PaginaSecuritate() {
  await cereAdmin();

  let lista: ListaCuvinte = { cuvinte: [], actualizatLa: null };
  let eroare: string | null = null;

  try {
    lista = await obtineCuvinteSalvate();
  } catch (exc) {
    console.error("ERROR PaginaSecuritate:", exc);
    eroare =
      "Nu am putut încărca lista de cuvinte. Verifică dacă migrația 0043 a fost aplicată.";
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-[26px] font-bold leading-8 tracking-[-0.02em] text-ink">
          Securitate
        </h1>
        <p className="mt-1.5 max-w-2xl text-[15px] leading-[22px] text-ink-soft">
          Cuvintele de aici sunt căutate în descrierea fiecărui transfer, înainte ca banii
          să plece. Când unul se potrivește, suma este reținută, transferul ajunge în{" "}
          <strong className="font-semibold">Tranzacții suspecte</strong>, iar beneficiarul
          nu primește nimic până când nu decizi tu.
        </p>
      </div>

      <Banda ton="info">
        Potrivirea nu e literală: se ignoră diacriticele și literele mari, iar cifrele puse
        în locul literelor („sp4lare") și greșelile mici de scriere („drogurii") sunt tot
        prinse. Cu cât un cuvânt e mai scurt, cu atât potrivirea e mai strictă.
      </Banda>

      {eroare ? <Banda ton="eroare">{eroare}</Banda> : null}

      {!eroare ? (
        <EditorCuvinteSensibile
          cuvinteInitiale={lista.cuvinte}
          actualizatLa={lista.actualizatLa}
        />
      ) : null}
    </div>
  );
}
