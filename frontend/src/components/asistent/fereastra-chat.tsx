"use client";

import { useRouter } from "next/navigation";
import { FileText, Image as ImageIcon, Loader2, Mic, Paperclip, Send, Square, Volume2, VolumeX, X } from "lucide-react";
import { useEffect, useRef, useState, useTransition, type FormEvent } from "react";
import { BulaMesaj } from "@/components/asistent/bula-mesaj";
import { Banda } from "@/components/ui/banda";
import { incarcaAtasament, trimiteMesaj, trimiteMesajVocal } from "@/lib/actions/asistent";
import type { MesajAsistent } from "@/lib/data/asistent";
import { cn } from "@/lib/utils";

const TIPURI_ACCEPTATE = ".pdf,.png,.jpg,.jpeg,.webp";

type Atasament = { id: string; nume: string; tip: "pdf" | "imagine" };

function audioDinBase64(base64: string): string {
  const octeti = atob(base64);
  const bytes = new Uint8Array(octeti.length);
  for (let i = 0; i < octeti.length; i++) bytes[i] = octeti.charCodeAt(i);
  return URL.createObjectURL(new Blob([bytes], { type: "audio/mpeg" }));
}

export function FereastraChat({
  conversatieIdInitial,
  mesajeInitiale,
  intrebareInitiala = "",
}: {
  conversatieIdInitial: string | null;
  mesajeInitiale: MesajAsistent[];
  /**
   * Text pus in casuta la deschidere, venit din `?intrebare=` — de exemplu
   * cand omul apasa "Intreaba asistentul" pe o notificare de blocare. Se
   * pre-completeaza si atat: trimiterea ramane a lui.
   */
  intrebareInitiala?: string;
}) {
  const router = useRouter();
  const [continut, setContinut] = useState(intrebareInitiala);
  const [atasament, setAtasament] = useState<Atasament | null>(null);
  const [mesajOptimist, setMesajOptimist] = useState<MesajAsistent | null>(null);
  const [seIncarcaFisier, setSeIncarcaFisier] = useState(false);
  // Alegerea utilizatorului: cand e activ, raspunsurile la mesaje scrise vin
  // si citite cu voce (sinteza vocala), nu doar cele trimise ca inregistrare.
  const [citesteCuVoce, setCitesteCuVoce] = useState(false);
  const [seInregistreaza, setSeInregistreaza] = useState(false);
  const [seTrimiteVocal, setSeTrimiteVocal] = useState(false);
  const [eroare, setEroare] = useState<string | null>(null);
  const [seTrimite, startTransition] = useTransition();

  const sfarsit = useRef<HTMLDivElement>(null);
  const inputFisier = useRef<HTMLInputElement>(null);
  const audioRedare = useRef<HTMLAudioElement>(null);
  const recorder = useRef<MediaRecorder | null>(null);
  const bucatiAudio = useRef<Blob[]>([]);
  const inputMesaj = useRef<HTMLTextAreaElement>(null);

  const mesajeAfisate = mesajOptimist ? [...mesajeInitiale, mesajOptimist] : mesajeInitiale;

  useEffect(() => {
    sfarsit.current?.scrollIntoView({ block: "end" });
  }, [mesajeAfisate.length]);

  // Cand se schimba conversatia — "Conversație nouă" sau alegerea uneia
  // existente din drawer — campul de scris trebuie sa fie deja activ, ca
  // utilizatorul sa poata scrie direct, fara sa mai dea click in el.
  useEffect(() => {
    inputMesaj.current?.focus();
  }, [conversatieIdInitial]);

  function dupaTrimitere(conversatieId: string, esteConversatieNoua: boolean) {
    setMesajOptimist(null);
    if (esteConversatieNoua) router.push(`/asistent?c=${conversatieId}`);
    else router.refresh();
  }

  function trimite() {
    const text = continut.trim();
    if (!text && !atasament) return;

    const atasamentTrimis = atasament;

    // Golim campul si aratam bula proprie imediat, inainte de raspunsul
    // serverului — altfel textul ramanea in caseta de scris pana venea
    // raspunsul, ca si cum mesajul n-ar fi plecat de fapt.
    setEroare(null);
    setContinut("");
    setAtasament(null);
    setMesajOptimist({
      id: `optimist-${Date.now()}`,
      rol: "user",
      // Un atasament trimis fara text n-ar arata nimic in bula proprie —
      // numele fisierului tine loc de continut pana vine raspunsul.
      text: text || (atasamentTrimis ? `📎 ${atasamentTrimis.nume}` : ""),
      citari: [],
      nivelIncredere: null,
      canal: "text",
      creatLa: new Date().toISOString(),
      fisierGenerat: null,
      actiuneRapida: null,
    });

    startTransition(async () => {
      const rezultat = await trimiteMesaj(
        conversatieIdInitial, text, atasamentTrimis ? [atasamentTrimis.id] : [], citesteCuVoce,
      );

      if (rezultat.eroare) {
        setEroare(rezultat.eroare);
        setMesajOptimist(null);
        setContinut(text);
        setAtasament(atasamentTrimis);
        return;
      }

      if (rezultat.audioBase64 && audioRedare.current) {
        audioRedare.current.src = audioDinBase64(rezultat.audioBase64);
        void audioRedare.current.play().catch(() => {});
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

  async function porneseInregistrarea() {
    setEroare(null);

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      // Azure Speech (REST, recunoastere scurta) intoarce "Success" cu text gol
      // pentru formate necunoscute, fara eroare — verificat live cu MP3. ogg/opus
      // e formatul documentat ca acceptat; webm e fallback-ul cand browserul
      // (ex. Chrome) nu stie sa inregistreze in ogg.
      const tipPreferat = ["audio/ogg;codecs=opus", "audio/webm;codecs=opus", "audio/webm"].find((tip) =>
        MediaRecorder.isTypeSupported(tip),
      );
      const instanta = new MediaRecorder(stream, tipPreferat ? { mimeType: tipPreferat } : undefined);
      bucatiAudio.current = [];

      instanta.ondataavailable = (event) => {
        if (event.data.size > 0) bucatiAudio.current.push(event.data);
      };

      instanta.onstop = () => {
        stream.getTracks().forEach((track) => track.stop());
        // Tipul real raportat de recorder — nu unul presupus — ca backend-ul sa
        // trimita catre Azure Content-Type-ul care corespunde bytilor reali.
        trimiteInregistrarea(new Blob(bucatiAudio.current, { type: instanta.mimeType }));
      };

      recorder.current = instanta;
      instanta.start();
      setSeInregistreaza(true);
    } catch {
      setEroare("Nu am acces la microfon. Verifică permisiunile browserului.");
    }
  }

  function opresteInregistrarea() {
    recorder.current?.stop();
    setSeInregistreaza(false);
  }

  function trimiteInregistrarea(blob: Blob) {
    setSeTrimiteVocal(true);

    const extensie = blob.type.includes("ogg") ? "ogg" : "webm";
    const formData = new FormData();
    formData.append("audio", blob, `mesaj.${extensie}`);

    startTransition(async () => {
      const rezultat = await trimiteMesajVocal(conversatieIdInitial, formData);
      setSeTrimiteVocal(false);

      if (rezultat.eroare) {
        setEroare(rezultat.eroare);
        return;
      }

      if (rezultat.audioBase64 && audioRedare.current) {
        audioRedare.current.src = audioDinBase64(rezultat.audioBase64);
        void audioRedare.current.play().catch(() => {});
      }

      dupaTrimitere(rezultat.conversatieId, rezultat.conversatieId !== conversatieIdInitial);
    });
  }

  const seProceseaza = seTrimite || seTrimiteVocal;

  return (
    <section className="mt-6 flex flex-1 flex-col">
      <div className="flex h-[62vh] min-h-[400px] flex-col gap-4 overflow-y-auto rounded-card bg-surface p-4 shadow-sm">
        {mesajeAfisate.length === 0 ? (
          <p className="my-8 text-center text-[15px] text-ink-faint">
            Întreabă-mă despre conturi, cheltuieli sau produsele Galaxy Bank.
          </p>
        ) : (
          mesajeAfisate.map((mesaj) => (
            <BulaMesaj
              key={mesaj.id}
              rol={mesaj.rol}
              text={mesaj.text}
              nivelIncredere={mesaj.nivelIncredere}
              canal={mesaj.canal}
              creatLa={mesaj.creatLa}
              fisierGenerat={mesaj.fisierGenerat}
              actiuneRapida={mesaj.actiuneRapida}
            />
          ))
        )}

        {seProceseaza ? (
          <div className="flex items-center gap-2 self-start rounded-card bg-muted px-4 py-2.5 text-[13px] text-ink-faint">
            <Loader2 size={14} strokeWidth={1.75} className="animate-spin" aria-hidden />
            Asistentul gândește…
          </div>
        ) : null}

        <div ref={sfarsit} />
      </div>

      <audio ref={audioRedare} className="hidden" />

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

        <button
          type="button"
          onClick={() => setCitesteCuVoce((valoare) => !valoare)}
          aria-pressed={citesteCuVoce}
          aria-label={citesteCuVoce ? "Oprește citirea răspunsurilor cu voce" : "Citește răspunsurile cu voce"}
          title={citesteCuVoce ? "Răspunsurile sunt citite cu voce" : "Citește răspunsurile cu voce"}
          className={cn(
            "flex h-[52px] w-[52px] shrink-0 items-center justify-center rounded-field border transition-colors",
            citesteCuVoce
              ? "border-primary-500 bg-primary-50 text-primary-700"
              : "border-line bg-surface text-ink-faint hover:bg-primary-50 hover:text-primary-700",
          )}
        >
          {citesteCuVoce ? (
            <Volume2 size={18} strokeWidth={1.75} aria-hidden />
          ) : (
            <VolumeX size={18} strokeWidth={1.75} aria-hidden />
          )}
        </button>

        <label htmlFor="mesaj-asistent" className="sr-only">
          Mesaj nou
        </label>

        <textarea
          id="mesaj-asistent"
          ref={inputMesaj}
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

        {continut.trim() || atasament ? (
          <button
            type="submit"
            aria-label="Trimite mesajul"
            disabled={seProceseaza}
            className="flex h-[52px] w-[52px] shrink-0 items-center justify-center rounded-field bg-primary-600 text-white shadow-btn transition-[background-color,transform] duration-[180ms] ease-soft hover:bg-primary-700 active:scale-[0.98] disabled:cursor-not-allowed disabled:bg-primary-100 disabled:text-primary-300 disabled:shadow-none"
          >
            <Send size={18} strokeWidth={1.75} aria-hidden />
          </button>
        ) : (
          <button
            type="button"
            onClick={seInregistreaza ? opresteInregistrarea : porneseInregistrarea}
            disabled={seTrimiteVocal || seIncarcaFisier}
            aria-label={seInregistreaza ? "Oprește înregistrarea" : "Mesaj vocal"}
            title={seInregistreaza ? "Oprește înregistrarea" : "Mesaj vocal"}
            className={cn(
              "flex h-[52px] w-[52px] shrink-0 items-center justify-center rounded-field shadow-btn transition-[background-color,transform] duration-[180ms] ease-soft active:scale-[0.98] disabled:cursor-not-allowed disabled:shadow-none",
              seInregistreaza
                ? "animate-pulse bg-danger text-white hover:bg-danger/90"
                : "bg-primary-600 text-white hover:bg-primary-700 disabled:bg-primary-100 disabled:text-primary-300",
            )}
          >
            {seTrimiteVocal ? (
              <Loader2 size={18} strokeWidth={1.75} className="animate-spin" aria-hidden />
            ) : seInregistreaza ? (
              <Square size={18} strokeWidth={1.75} aria-hidden />
            ) : (
              <Mic size={18} strokeWidth={1.75} aria-hidden />
            )}
          </button>
        )}
      </form>
    </section>
  );
}
