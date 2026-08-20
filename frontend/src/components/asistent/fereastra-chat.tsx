"use client";

import { useRouter } from "next/navigation";
import { FileText, Image as ImageIcon, Loader2, Mic, Paperclip, Send, X } from "lucide-react";
import { useEffect, useRef, useState, useTransition, type FormEvent } from "react";
import { BulaMesaj } from "@/components/asistent/bula-mesaj";
import { Banda } from "@/components/ui/banda";
import { incarcaAtasament, trimiteMesaj } from "@/lib/actions/asistent";
import type { MesajAsistent } from "@/lib/data/asistent";

const TIPURI_ACCEPTATE = ".pdf,.png,.jpg,.jpeg,.webp";

type Atasament = { id: string; nume: string; tip: "pdf" | "imagine" };

// ---------------------------------------------------------------------------
// Mesajul vocal e dezactivat temporar (migrația de voce nu s-a aplicat încă).
// Butonul de microfon rămâne vizibil, dar dezactivat — nu înregistrează nimic.
// Ca să repornești funcția: decomentează blocul de mai jos, importă din nou
// `trimiteMesajVocal` (lib/actions/asistent) și `Square` din lucide-react,
// repune `seInregistreaza`/`seTrimiteVocal` în `seProceseaza`, și înlocuiește
// butonul static de mai jos cu varianta care comută pornit/oprit.
// ---------------------------------------------------------------------------
// import { trimiteMesajVocal } from "@/lib/actions/asistent";
// import { Square } from "lucide-react";
//
// function audioDinBase64(base64: string): string {
//   const octeti = atob(base64);
//   const bytes = new Uint8Array(octeti.length);
//   for (let i = 0; i < octeti.length; i++) bytes[i] = octeti.charCodeAt(i);
//   return URL.createObjectURL(new Blob([bytes], { type: "audio/mpeg" }));
// }

export function FereastraChat({
  conversatieIdInitial,
  mesajeInitiale,
}: {
  conversatieIdInitial: string | null;
  mesajeInitiale: MesajAsistent[];
}) {
  const router = useRouter();
  const [continut, setContinut] = useState("");
  const [atasament, setAtasament] = useState<Atasament | null>(null);
  const [seIncarcaFisier, setSeIncarcaFisier] = useState(false);
  // const [seInregistreaza, setSeInregistreaza] = useState(false);
  // const [seTrimiteVocal, setSeTrimiteVocal] = useState(false);
  const [eroare, setEroare] = useState<string | null>(null);
  const [seTrimite, startTransition] = useTransition();

  const sfarsit = useRef<HTMLDivElement>(null);
  const inputFisier = useRef<HTMLInputElement>(null);
  // const audioRedare = useRef<HTMLAudioElement>(null);
  // const recorder = useRef<MediaRecorder | null>(null);
  // const bucatiAudio = useRef<Blob[]>([]);

  useEffect(() => {
    sfarsit.current?.scrollIntoView({ block: "end" });
  }, [mesajeInitiale.length]);

  function dupaTrimitere(conversatieId: string, esteConversatieNoua: boolean) {
    setContinut("");
    setAtasament(null);
    if (esteConversatieNoua) router.push(`/asistent?c=${conversatieId}`);
    else router.refresh();
  }

  function trimite() {
    const text = continut.trim();
    if (!text) return;

    setEroare(null);

    startTransition(async () => {
      const rezultat = await trimiteMesaj(conversatieIdInitial, text, atasament ? [atasament.id] : []);

      if (rezultat.eroare) {
        setEroare(rezultat.eroare);
        return;
      }

      dupaTrimitere(rezultat.conversatieId, rezultat.conversatieId !== conversatieIdInitial);
    });
  }

  async function alegeFisier(event: React.ChangeEvent<HTMLInputElement>) {
    const fisier = event.target.files?.[0];
    event.target.value = "";
    if (!fisier) return;

    setEroare(null);
    setSeIncarcaFisier(true);

    const formData = new FormData();
    formData.append("file", fisier);

    const rezultat = await incarcaAtasament(formData);
    setSeIncarcaFisier(false);

    if (rezultat.eroare) {
      setEroare(rezultat.eroare);
      return;
    }

    setAtasament({ id: rezultat.id, nume: rezultat.nume, tip: rezultat.tip });
  }

  // async function porneseInregistrarea() {
  //   setEroare(null);
  //
  //   try {
  //     const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  //     // Azure Speech (REST, recunoastere scurta) intoarce "Success" cu text gol
  //     // pentru formate necunoscute, fara eroare — verificat live cu MP3. ogg/opus
  //     // e formatul documentat ca acceptat; webm e fallback-ul cand browserul
  //     // (ex. Chrome) nu stie sa inregistreze in ogg.
  //     const tipPreferat = ["audio/ogg;codecs=opus", "audio/webm;codecs=opus", "audio/webm"].find((tip) =>
  //       MediaRecorder.isTypeSupported(tip),
  //     );
  //     const instanta = new MediaRecorder(stream, tipPreferat ? { mimeType: tipPreferat } : undefined);
  //     bucatiAudio.current = [];
  //
  //     instanta.ondataavailable = (event) => {
  //       if (event.data.size > 0) bucatiAudio.current.push(event.data);
  //     };
  //
  //     instanta.onstop = () => {
  //       stream.getTracks().forEach((track) => track.stop());
  //       // Tipul real raportat de recorder — nu unul presupus — ca backend-ul sa
  //       // trimita catre Azure Content-Type-ul care corespunde bytilor reali.
  //       trimiteInregistrarea(new Blob(bucatiAudio.current, { type: instanta.mimeType }));
  //     };
  //
  //     recorder.current = instanta;
  //     instanta.start();
  //     setSeInregistreaza(true);
  //   } catch {
  //     setEroare("Nu am acces la microfon. Verifică permisiunile browserului.");
  //   }
  // }
  //
  // function opresteInregistrarea() {
  //   recorder.current?.stop();
  //   setSeInregistreaza(false);
  // }
  //
  // function trimiteInregistrarea(blob: Blob) {
  //   setSeTrimiteVocal(true);
  //
  //   const extensie = blob.type.includes("ogg") ? "ogg" : "webm";
  //   const formData = new FormData();
  //   formData.append("audio", blob, `mesaj.${extensie}`);
  //
  //   startTransition(async () => {
  //     const rezultat = await trimiteMesajVocal(conversatieIdInitial, formData);
  //     setSeTrimiteVocal(false);
  //
  //     if (rezultat.eroare) {
  //       setEroare(rezultat.eroare);
  //       return;
  //     }
  //
  //     if (rezultat.audioBase64 && audioRedare.current) {
  //       audioRedare.current.src = audioDinBase64(rezultat.audioBase64);
  //       void audioRedare.current.play().catch(() => {});
  //     }
  //
  //     dupaTrimitere(rezultat.conversatieId, rezultat.conversatieId !== conversatieIdInitial);
  //   });
  // }

  const seProceseaza = seTrimite; // || seTrimiteVocal — repus cand se reactiveaza vocea

  return (
    <section className="mt-6 flex flex-1 flex-col">
      <div className="flex h-[62vh] min-h-[400px] flex-col gap-4 overflow-y-auto rounded-card bg-surface p-4 shadow-sm">
        {mesajeInitiale.length === 0 ? (
          <p className="my-8 text-center text-[15px] text-ink-faint">
            Întreabă-mă despre conturi, cheltuieli sau produsele Galaxy Bank.
          </p>
        ) : (
          mesajeInitiale.map((mesaj) => (
            <BulaMesaj
              key={mesaj.id}
              rol={mesaj.rol}
              text={mesaj.text}
              nivelIncredere={mesaj.nivelIncredere}
              canal={mesaj.canal}
              creatLa={mesaj.creatLa}
            />
          ))
        )}

        {seProceseaza ? (
          <div className="flex items-center gap-2 self-start rounded-card bg-muted px-4 py-2.5 text-[13px] text-ink-faint">
            <Loader2 size={14} strokeWidth={1.75} className="animate-spin" aria-hidden />
            Asistentul scrie…
          </div>
        ) : null}

        <div ref={sfarsit} />
      </div>

      {/* <audio ref={audioRedare} className="hidden" /> */}

      {eroare ? (
        <div className="mt-3">
          <Banda ton="eroare">{eroare}</Banda>
        </div>
      ) : null}

      {atasament ? (
        <div className="mt-3 flex items-center gap-2 rounded-field border border-line bg-surface px-3 py-2">
          {atasament.tip === "pdf" ? (
            <FileText size={16} strokeWidth={1.75} aria-hidden className="shrink-0 text-primary-600" />
          ) : (
            <ImageIcon size={16} strokeWidth={1.75} aria-hidden className="shrink-0 text-primary-600" />
          )}
          <span className="flex-1 truncate text-[13px] text-ink-soft">{atasament.nume}</span>
          <button
            type="button"
            onClick={() => setAtasament(null)}
            aria-label="Elimină atașamentul"
            className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-ink-faint hover:bg-primary-50 hover:text-primary-700"
          >
            <X size={14} strokeWidth={1.75} aria-hidden />
          </button>
        </div>
      ) : null}

      <form
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          trimite();
        }}
        className="mt-3 flex items-end gap-2"
      >
        <input
          ref={inputFisier}
          type="file"
          accept={TIPURI_ACCEPTATE}
          className="hidden"
          onChange={alegeFisier}
        />

        <button
          type="button"
          onClick={() => inputFisier.current?.click()}
          disabled={seIncarcaFisier || seProceseaza}
          aria-label="Atașează PDF sau poză"
          className="flex h-[52px] w-[52px] shrink-0 items-center justify-center rounded-field border border-line bg-surface text-ink-faint transition-colors hover:bg-primary-50 hover:text-primary-700 disabled:opacity-50"
        >
          {seIncarcaFisier ? (
            <Loader2 size={18} strokeWidth={1.75} className="animate-spin" aria-hidden />
          ) : (
            <Paperclip size={18} strokeWidth={1.75} aria-hidden />
          )}
        </button>

        <label htmlFor="mesaj-asistent" className="sr-only">
          Mesaj nou
        </label>

        <textarea
          id="mesaj-asistent"
          rows={1}
          value={continut}
          onChange={(e) => setContinut(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              trimite();
            }
          }}
          maxLength={4000}
          placeholder="Scrie o întrebare…"
          disabled={seProceseaza}
          className="max-h-32 min-h-[52px] flex-1 resize-none rounded-field border border-line bg-surface px-4 py-[15px] text-[15px] text-ink outline-none transition-[border-color,box-shadow] duration-150 ease-soft placeholder:text-ink-faint focus:border-primary-500 focus:ring-4 focus:ring-primary-500/12 disabled:opacity-60"
        />

        {continut.trim() ? (
          <button
            type="submit"
            aria-label="Trimite mesajul"
            disabled={seProceseaza}
            className="flex h-[52px] w-[52px] shrink-0 items-center justify-center rounded-field bg-primary-600 text-white shadow-btn transition-[background-color,transform] duration-[180ms] ease-soft hover:bg-primary-700 active:scale-[0.98] disabled:cursor-not-allowed disabled:bg-primary-100 disabled:text-primary-300 disabled:shadow-none"
          >
            <Send size={18} strokeWidth={1.75} aria-hidden />
          </button>
        ) : (
          // Vocea e dezactivata temporar: butonul exista, dar nu porneste nimic
          // (vezi comentariul de deasupra importurilor pentru cum se reactiveaza).
          <button
            type="button"
            disabled
            aria-label="Mesaj vocal (în curând)"
            title="Mesajul vocal vine în curând"
            className="flex h-[52px] w-[52px] shrink-0 items-center justify-center rounded-field bg-primary-100 text-primary-300 shadow-none disabled:cursor-not-allowed"
          >
            <Mic size={18} strokeWidth={1.75} aria-hidden />
          </button>
        )}
      </form>
    </section>
  );
}
