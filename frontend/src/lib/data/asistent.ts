import { apelBackend } from "@/lib/data/backend";

// Reexportat pentru importurile existente: helperul a fost mutat in
// lib/data/backend.ts cand creditarea a devenit al doilea consumator.
export { apelBackend };

export type Citare = {
  documentId: string;
  sectiune: string | null;
  scor: number;
};

/** Afisat in loc de sursa exacta — vezi agents/base.py:confidence_from_tool_results. */
export type NivelIncredere = "ridicat" | "mediu" | "scazut" | null;

export type FisierGenerat = {
  url: string;
  nume: string;
};

export type MesajAsistent = {
  id: string;
  rol: "user" | "assistant";
  text: string;
  citari: Citare[];
  nivelIncredere: NivelIncredere;
  canal: "text" | "voce";
  creatLa: string;
  fisierGenerat: FisierGenerat | null;
};

export type ConversatieAsistent = {
  id: string;
  titlu: string;
  actualizatLa: string;
};

function laCitare(citare: { document_id: string; section: string | null; score: number }): Citare {
  return { documentId: citare.document_id, sectiune: citare.section, scor: citare.score };
}

export async function obtineConversatii(): Promise<ConversatieAsistent[]> {
  const { date } = await apelBackend<
    { id: string; title: string; updated_at: string }[]
  >("/assistant/conversations");

  return (date ?? []).map((c) => ({ id: c.id, titlu: c.title, actualizatLa: c.updated_at }));
}

export async function obtineMesaje(idConversatie: string): Promise<MesajAsistent[]> {
  const { date } = await apelBackend<
    {
      id: string;
      role: "user" | "assistant";
      text: string;
      citations: { document_id: string; section: string | null; score: number }[];
      confidence: NivelIncredere;
      channel: "text" | "voce";
      created_at: string;
      file: { url: string; filename: string; kind: string } | null;
    }[]
  >(`/assistant/conversations/${idConversatie}/messages`);

  return (date ?? []).map((m) => ({
    id: m.id,
    rol: m.role,
    text: m.text,
    citari: m.citations.map(laCitare),
    nivelIncredere: m.confidence,
    canal: m.channel,
    creatLa: m.created_at,
    fisierGenerat: m.file ? { url: m.file.url, nume: m.file.filename } : null,
  }));
}
