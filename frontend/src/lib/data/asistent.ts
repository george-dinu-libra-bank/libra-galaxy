import { createClient } from "@/lib/supabase/server";

export type Citare = {
  documentId: string;
  sectiune: string | null;
  scor: number;
};

/** Afisat in loc de sursa exacta — vezi agents/base.py:confidence_from_tool_results. */
export type NivelIncredere = "ridicat" | "mediu" | "scazut" | null;

export type MesajAsistent = {
  id: string;
  rol: "user" | "assistant";
  text: string;
  citari: Citare[];
  nivelIncredere: NivelIncredere;
  canal: "text" | "voce";
  creatLa: string;
};

export type ConversatieAsistent = {
  id: string;
  titlu: string;
  actualizatLa: string;
};

type PlicSucces<T> = { success: true; body: T };
type PlicEroare = { success: false; error: { code: string; message: string } };

const BACKEND_URL = process.env.BACKEND_API_URL ?? "http://localhost:8000";

/**
 * Apel catre FastAPI, cu tokenul Supabase al utilizatorului curent — backend-ul
 * nu e niciodata expus catre browser (ARCHITECTURE.md 4.2).
 */
export async function apelBackend<T>(
  cale: string,
  optiuni: RequestInit = {},
): Promise<{ date?: T; eroare?: string }> {
  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session) return { eroare: "Trebuie sa fii autentificat." };

  let raspuns: Response;
  try {
    raspuns = await fetch(`${BACKEND_URL}${cale}`, {
      ...optiuni,
      headers: {
        ...(optiuni.headers ?? {}),
        Authorization: `Bearer ${session.access_token}`,
        "Accept-Language": "ro",
      },
      cache: "no-store",
    });
  } catch {
    return { eroare: "Asistentul nu este disponibil momentan. Incearca din nou." };
  }

  const corp = (await raspuns.json().catch(() => null)) as PlicSucces<T> | PlicEroare | null;

  if (!corp || !corp.success) {
    return { eroare: corp?.error?.message ?? "A aparut o eroare neasteptata." };
  }

  return { date: corp.body };
}

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
  }));
}
