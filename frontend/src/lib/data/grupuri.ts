import { createClient } from "@/lib/supabase/server";

export type GrupSumar = {
  id: number;
  nume: string;
  sold: number;
  creatLa: string;
  /** Cati oameni sunt in grup, inclusiv utilizatorul curent. */
  membri: number;
};

export type Grup = {
  id: number;
  nume: string;
  sold: number;
  tokenAcces: string;
  creatLa: string;
  idCreator: string;
};

export type MembruGrup = {
  idUser: string;
  nume: string;
  avatarUrl: string | null;
  creatLa: string;
};

/**
 * „text" e scris de un om; „incasare" si „plata" sunt generate de
 * public.core_banking_groups cand cineva pune bani in grup
 * (0010_mesaje_incasare.sql), respectiv cand scoate din el
 * (0012_mesaje_plata.sql).
 */
export type TipMesaj = "text" | "incasare" | "plata";

export type MesajGrup = {
  id: number;
  continut: string;
  idUser: string;
  creatLa: string;
  tip: TipMesaj;
  /** Autorul, luat din lista de membri; null daca a iesit intre timp din grup. */
  autor: MembruGrup | null;
  alMeu: boolean;
};

export type InvitatieGrup = {
  id: number;
  idGrup: number;
  numeGrup: string;
  numeInvitator: string;
  creatLa: string;
};

/** Cate mesaje se aduc intr-o conversatie; restul raman in istoricul tabelei. */
const MESAJE_MAX = 100;

/**
 * Grupurile in care e utilizatorul curent, cel mai recent intrat primul.
 *
 * Politicile din 0008_grupuri.sql fac filtrarea: fara ele, `select` pe groups
 * n-ar returna nimic. Numarul de membri se numara separat, ca sa nu depinda
 * lista de un `count` inglobat pe care RLS l-ar taia oricum la grupurile
 * proprii.
 */
export async function obtineGrupurileMele(): Promise<GrupSumar[]> {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) return [];

  const { data, error } = await supabase
    .from("groups_participants")
    .select("id_group, creat_la, groups ( id, nume, sold, creat_la )")
    .eq("id_user", user.id)
    .order("creat_la", { ascending: false });

  if (error) throw error;

  const randuri = data ?? [];
  const idGrupuri = randuri.map((rand) => rand.id_group as number);

  // Un singur query pentru toti participantii grupurilor mele; numaratoarea se
  // face aici, in memorie.
  const membriPeGrup = new Map<number, number>();

  if (idGrupuri.length) {
    const { data: participanti, error: eroareMembri } = await supabase
      .from("groups_participants")
      .select("id_group")
      .in("id_group", idGrupuri);

    if (eroareMembri) throw eroareMembri;

    for (const participant of participanti ?? []) {
      const id = participant.id_group as number;
      membriPeGrup.set(id, (membriPeGrup.get(id) ?? 0) + 1);
    }
  }

  return randuri.flatMap((rand) => {
    // PostgREST intoarce relatia „la unu" ca obiect, dar tipul generat o vede
    // si ca lista — normalizam, ca la contraparte in lib/data/tranzactii.ts.
    const relatie = rand.groups as GrupBrut | GrupBrut[] | null;
    const grup = Array.isArray(relatie) ? relatie[0] : relatie;

    if (!grup) return [];

    return [
      {
        id: grup.id,
        nume: grup.nume,
        sold: Number(grup.sold),
        creatLa: grup.creat_la,
        membri: membriPeGrup.get(grup.id) ?? 1,
      },
    ];
  });
}

type GrupBrut = { id: number; nume: string; sold: number | string; creat_la: string };

/** Un grup dupa id. Null daca nu exista sau daca utilizatorul nu e in el (RLS). */
export async function obtineGrup(id: number): Promise<Grup | null> {
  const supabase = await createClient();

  const { data, error } = await supabase
    .from("groups")
    .select("id, nume, sold, token_acces, creat_la, id_creator")
    .eq("id", id)
    .maybeSingle();

  if (error) throw error;
  if (!data) return null;

  return {
    id: data.id as number,
    nume: data.nume as string,
    sold: Number(data.sold),
    tokenAcces: data.token_acces as string,
    creatLa: data.creat_la as string,
    idCreator: data.id_creator as string,
  };
}

/**
 * Membrii unui grup, cu nume si poza.
 *
 * Trece prin `public.membri_grup` pentru ca politica de pe profiles lasa pe
 * fiecare sa-si vada doar propriul rand — functia deschide exact numele si
 * avatarul colegilor de grup, nimic altceva (0008_grupuri.sql).
 */
export async function obtineMembriiGrupului(idGrup: number): Promise<MembruGrup[]> {
  const supabase = await createClient();

  const { data, error } = await supabase.rpc("membri_grup", { p_id_group: idGrup });

  if (error) throw error;

  return (data ?? []).map((membru: Record<string, unknown>) => ({
    idUser: membru.id_user as string,
    nume: membru.nume as string,
    avatarUrl: (membru.avatar_url as string | null) ?? null,
    creatLa: membru.creat_la as string,
  }));
}

/**
 * Invitatiile primite, in asteptare — trece prin `public.invitatiile_mele`
 * (SECURITY DEFINER), la fel ca `membri_grup`: nu esti inca membru al
 * grupului la care esti invitat, deci politica normala de pe `groups` nu
 * ti-ar lasa sa vezi numele lui (0044_invitatii_grup.sql).
 */
export async function obtineInvitatiileMele(): Promise<InvitatieGrup[]> {
  const supabase = await createClient();

  const { data, error } = await supabase.rpc("invitatiile_mele");

  if (error) throw error;

  return (data ?? []).map((invitatie: Record<string, unknown>) => ({
    id: invitatie.id as number,
    idGrup: invitatie.id_group as number,
    numeGrup: invitatie.nume_grup as string,
    numeInvitator: invitatie.nume_invitator as string,
    creatLa: invitatie.creat_la as string,
  }));
}

/**
 * Ultimele mesaje din grup, in ordine cronologica (cel mai vechi sus, ca
 * intr-o conversatie). Autorii vin din lista de membri deja incarcata, ca sa
 * nu se mai ceara o data profilurile.
 */
export async function obtineMesajeleGrupului(
  idGrup: number,
  membri: MembruGrup[],
): Promise<MesajGrup[]> {
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  // Cele mai noi MESAJE_MAX, apoi intoarse: asa se taie coada veche, nu cea noua.
  const { data, error } = await supabase
    .from("group_messages")
    .select("id, continut, id_user, creat_la, type")
    .eq("id_group", idGrup)
    .order("creat_la", { ascending: false })
    .limit(MESAJE_MAX);

  if (error) throw error;

  const dupaId = new Map(membri.map((membru) => [membru.idUser, membru]));

  return (data ?? []).reverse().map((mesaj) => ({
    id: mesaj.id as number,
    continut: mesaj.continut as string,
    idUser: mesaj.id_user as string,
    creatLa: mesaj.creat_la as string,
    tip: (mesaj.type as TipMesaj) ?? "text",
    autor: dupaId.get(mesaj.id_user as string) ?? null,
    alMeu: mesaj.id_user === user?.id,
  }));
}
