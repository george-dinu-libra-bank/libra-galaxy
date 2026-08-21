"use server";

import { apelBackend, type Citare, type FisierGenerat, type NivelIncredere } from "@/lib/data/asistent";

export type RezultatMesaj = {
  conversatieId: string;
  mesajId: string;
  text: string;
  citari: Citare[];
  nivelIncredere: NivelIncredere;
  agentId: string;
  fisierGenerat?: FisierGenerat | null;
  audioBase64?: string;
  eroare?: string;
};

export type RezultatAtasament = {
  id: string;
  tip: "pdf" | "imagine";
  nume: string;
  eroare?: string;
};

function laCitare(citare: { document_id: string; section: string | null; score: number }): Citare {
  return { documentId: citare.document_id, sectiune: citare.section, scor: citare.score };
}

/** Sterge o conversatie (si mesajele/atasamentele ei, prin cascade in baza de date). */
export async function stergeConversatie(conversatieId: string): Promise<{ eroare?: string }> {
  const { eroare } = await apelBackend(`/assistant/conversations/${conversatieId}`, { method: "DELETE" });
  return eroare ? { eroare } : {};
}

/** Trimite un mesaj text catre asistent, cu atasamente optionale deja incarcate. */
export async function trimiteMesaj(
  conversatieId: string | null,
  text: string,
  atasamentIds: string[] = [],
): Promise<RezultatMesaj> {
  const trimis = text.trim();
  if (!trimis) {
    return {
      conversatieId: conversatieId ?? "", mesajId: "", text: "", citari: [], nivelIncredere: null, agentId: "",
      eroare: "Scrie ceva mai intai.",
    };
  }

  const { date, eroare } = await apelBackend<{
    conversation_id: string;
    message_id: string;
    text: string;
    citations: { document_id: string; section: string | null; score: number }[];
    confidence: NivelIncredere;
    agent_id: string;
    file: { url: string; filename: string; kind: string } | null;
  }>("/assistant/messages", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ conversation_id: conversatieId, text: trimis, attachment_ids: atasamentIds }),
  });

  if (eroare || !date) {
    return {
      conversatieId: conversatieId ?? "", mesajId: "", text: "", citari: [], nivelIncredere: null, agentId: "",
      eroare: eroare ?? "Eroare necunoscuta.",
    };
  }

  return {
    conversatieId: date.conversation_id,
    mesajId: date.message_id,
    text: date.text,
    citari: date.citations.map(laCitare),
    nivelIncredere: date.confidence,
    agentId: date.agent_id,
    fisierGenerat: date.file ? { url: date.file.url, nume: date.file.filename } : null,
  };
}

/** Incarca un PDF sau o poza, inainte de a fi atasat(a) unui mesaj. */
export async function incarcaAtasament(formData: FormData): Promise<RezultatAtasament> {
  const { date, eroare } = await apelBackend<{ id: string; kind: "pdf" | "imagine"; filename: string }>(
    "/assistant/attachments",
    { method: "POST", body: formData },
  );

  if (eroare || !date) {
    return { id: "", tip: "pdf", nume: "", eroare: eroare ?? "Nu am putut incarca fisierul." };
  }

  return { id: date.id, tip: date.kind, nume: date.filename };
}

/** Trimite o inregistrare audio: backend-ul o transcrie, o proceseaza si sintetizeaza raspunsul. */
export async function trimiteMesajVocal(
  conversatieId: string | null,
  formData: FormData,
): Promise<RezultatMesaj> {
  const cale = conversatieId
    ? `/assistant/voice-messages?conversation_id=${encodeURIComponent(conversatieId)}`
    : "/assistant/voice-messages";

  const { date, eroare } = await apelBackend<{
    conversation_id: string;
    message_id: string;
    text: string;
    citations: { document_id: string; section: string | null; score: number }[];
    confidence: NivelIncredere;
    agent_id: string;
    audio_base64: string | null;
  }>(cale, { method: "POST", body: formData });

  if (eroare || !date) {
    return {
      conversatieId: conversatieId ?? "", mesajId: "", text: "", citari: [], nivelIncredere: null, agentId: "",
      eroare: eroare ?? "Eroare necunoscuta.",
    };
  }

  return {
    conversatieId: date.conversation_id,
    mesajId: date.message_id,
    text: date.text,
    citari: date.citations.map(laCitare),
    nivelIncredere: date.confidence,
    agentId: date.agent_id,
    audioBase64: date.audio_base64 ?? undefined,
  };
}
