"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState, useTransition } from "react";
import { Plus, Search, X } from "lucide-react";
import { Banda } from "@/components/ui/banda";
import { Button } from "@/components/ui/button";
import { Camp } from "@/components/ui/camp";
import { salveazaCuvinteSensibile } from "@/lib/actions/admin-securitate";

/**
 * Lista de cuvinte dupa care se scaneaza descrierile transferurilor.
 *
 * Cuvintele se tin ca etichete, nu ca text liber intr-o caseta: asa se vede din
 * prima cate sunt si care sunt, iar stergerea unuia gresit nu cere editare de
 * text. Se poate lipi si o lista intreaga — separatorii (virgula, punct si
 * virgula, linie noua) sunt taiati la adaugare.
 *
 * Nimic nu se salveaza singur: lista pleaca spre baza doar la apasarea butonului,
 * fiindca un cuvant scapat din greseala ar opri transferuri reale.
 */
export function EditorCuvinteSensibile({
  cuvinteInitiale,
  actualizatLa,
}: {
  cuvinteInitiale: string[];
  actualizatLa: string | null;
}) {
  const router = useRouter();
  const [cuvinte, setCuvinte] = useState<string[]>(cuvinteInitiale);
  const [nou, setNou] = useState("");
  const [cautare, setCautare] = useState("");
  const [eroare, setEroare] = useState<string | null>(null);
  const [salvat, setSalvat] = useState(false);
  const [seSalveaza, startTransition] = useTransition();

  const modificat = useMemo(
    () =>
      cuvinte.length !== cuvinteInitiale.length ||
      cuvinte.some((cuvant, i) => cuvant !== cuvinteInitiale[i]),
    [cuvinte, cuvinteInitiale],
  );

  const afisate = useMemo(() => {
    const q = cautare.trim().toLowerCase();
    return q ? cuvinte.filter((cuvant) => cuvant.toLowerCase().includes(q)) : cuvinte;
  }, [cuvinte, cautare]);

  function adauga() {
    const bucati = nou
      .split(/[\n,;]+/)
      .map((bucata) => bucata.trim().replace(/\s+/g, " "))
      .filter(Boolean);

    if (bucati.length === 0) return;

    setSalvat(false);
    setEroare(null);
    setCuvinte((precedente) => {
      const vazute = new Set(precedente.map((c) => c.toLowerCase()));
      const adaugate = bucati.filter((c) => {
        if (vazute.has(c.toLowerCase())) return false;
        vazute.add(c.toLowerCase());
        return true;
      });
      return [...precedente, ...adaugate];
    });
    setNou("");
  }

  function sterge(cuvant: string) {
    setSalvat(false);
    setCuvinte((precedente) => precedente.filter((c) => c !== cuvant));
  }

  function salveaza() {
    setEroare(null);
    setSalvat(false);

    startTransition(async () => {
      // Actiunea primeste text si il desparte ea insasi, cu aceleasi reguli ca
      // aici — un singur loc decide ce e un cuvant valid.
      const rezultat = await salveazaCuvinteSensibile(cuvinte.join("\n"));

      if (rezultat.eroare) {
        setEroare(rezultat.eroare);
        return;
      }

      if (rezultat.cuvinte) setCuvinte(rezultat.cuvinte);
      setSalvat(true);
      router.refresh();
    });
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="rounded-card border border-line bg-surface p-5 shadow-sm">
        <div className="grid gap-3 sm:grid-cols-[1fr_auto] sm:items-end">
          <Camp
            eticheta="Adaugă un cuvânt sau o expresie"
            placeholder="Ex. spălare de bani"
            value={nou}
            onChange={(e) => setNou(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                adauga();
              }
            }}
            maxLength={60}
            autoComplete="off"
            ajutor="Enter adaugă. Poți lipi și o listă întreagă, despărțită prin virgule."
          />
          <Button
            varianta="secondary"
            className="h-[52px] sm:mb-[26px]"
            iconaStanga={<Plus size={18} strokeWidth={1.75} aria-hidden />}
            onClick={adauga}
            disabled={nou.trim().length === 0}
          >
            Adaugă
          </Button>
        </div>
      </div>

      {eroare ? <Banda ton="eroare">{eroare}</Banda> : null}
      {salvat && !modificat ? (
        <Banda ton="succes">Lista a fost salvată și se aplică de la următorul transfer.</Banda>
      ) : null}

      <div className="rounded-card border border-line bg-surface p-5 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-[15px] font-semibold text-ink">
            {cuvinte.length} {cuvinte.length === 1 ? "cuvânt" : "cuvinte"} în listă
          </p>
          {actualizatLa ? (
            <p className="text-[12.5px] text-ink-faint">
              Ultima salvare:{" "}
              {new Date(actualizatLa).toLocaleString("ro-RO", {
                day: "numeric",
                month: "long",
                year: "numeric",
                hour: "2-digit",
                minute: "2-digit",
              })}
            </p>
          ) : null}
        </div>

        {cuvinte.length > 8 ? (
          <div className="mt-4">
            <Camp
              eticheta="Caută în listă"
              icoana={Search}
              value={cautare}
              onChange={(e) => setCautare(e.target.value)}
              placeholder="Filtrează cuvintele"
              autoComplete="off"
            />
          </div>
        ) : null}

        {cuvinte.length === 0 ? (
          <p className="mt-4 text-[13px] leading-[19px] text-ink-faint">
            Lista e goală, deci scanerul nu oprește niciun transfer.
          </p>
        ) : afisate.length === 0 ? (
          <p className="mt-4 text-[13px] text-ink-faint">Niciun cuvânt nu se potrivește căutării.</p>
        ) : (
          <ul className="mt-4 flex flex-wrap gap-2">
            {afisate.map((cuvant) => (
              <li key={cuvant}>
                <span className="flex items-center gap-1.5 rounded-full bg-primary-50 py-1.5 pl-3 pr-1.5 text-[13px] font-medium text-primary-700">
                  {cuvant}
                  <button
                    type="button"
                    onClick={() => sterge(cuvant)}
                    aria-label={`Șterge „${cuvant}"`}
                    className="flex h-6 w-6 items-center justify-center rounded-full text-primary-700/70 transition-colors hover:bg-primary-100 hover:text-primary-700 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-primary-500/25"
                  >
                    <X size={14} strokeWidth={2} aria-hidden />
                  </button>
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <Button onClick={salveaza} loading={seSalveaza} disabled={!modificat}>
          Salvează lista
        </Button>
        {modificat ? (
          <span className="text-[13px] text-ink-faint">
            Ai modificări nesalvate — scanerul folosește încă lista veche.
          </span>
        ) : null}
      </div>
    </div>
  );
}
