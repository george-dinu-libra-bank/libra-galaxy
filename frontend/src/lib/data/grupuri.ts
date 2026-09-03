import { createClient } from "@/lib/supabase/server";
import {
  emblemaGrupValida,
  fundalGrupValid,
  temaGrupValida,
  type EmblemaGrup,
  type FundalGrup,
  type TemaGrup,
} from "@/lib/tema-grup";

export type GrupSumar = {
  id: number;
  nume: string;
  sold: number;
  creatLa: string;
  /** Cati oameni sunt in grup, inclusiv utilizatorul curent. */
  membri: number;
  /** Daca utilizatorul curent are voie sa scoata bani din soldul comun. */
  poateCheltui: boolean;
  /** Aspectul ales de membri (0054_tema_grup.sql), nu o preferinta personala. */
  tema: TemaGrup;
  emblema: EmblemaGrup;
};

export type Grup = {
  id: number;
  nume: string;
  sold: number;
  tokenAcces: string;
  creatLa: string;
  idCreator: string;
  /** Daca miscarile de bani ale unui membru se vad si de ceilalti. */
  tranzactiiVizibile: boolean;
  /** Aspectul ales de membri (0054_tema_grup.sql), nu o preferinta personala. */
  tema: TemaGrup;
  emblema: EmblemaGrup;
  /**
   * Modelul de fundal al paginii. Nu apare in `GrupSumar`: e un tapet pe tot
   * ecranul, deci n-are ce cauta pe un rand din lista.
   */
  fundal: FundalGrup;
};

export type MembruGrup = {
  idUser: string;
  nume: string;
  avatarUrl: string | null;
  creatLa: string;
};

/**
 * Un membru impreuna cu drepturile lui asupra pungii comune
 * (0053_drepturi_grup.sql). O vad toti membrii, nu doar creatorul: intr-un sold
 * comun e corect sa stii pe ce reguli esti, fara sa incerci o plata ca sa afli.
 */
export type MembruCuDrepturi = MembruGrup & {
  esteCreator: boolean;
  poateCheltui: boolean;
  /** Plafonul lunar in RON; null inseamna fara plafon, nu zero. */
  limitaLunara: number | null;
  /** Cat a scos din grup de la 1 ale lunii. */
  cheltuitLuna: number;
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
    .select(
      "id_group, creat_la, poate_cheltui, groups ( id, nume, sold, creat_la, tema, emblema )",
    )
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
        // Randul propriu de participant, deci dreptul utilizatorului curent.
        // Ecranul de transfer se foloseste de el ca sa nu ofere ca sursa un
        // grup din care omul oricum n-ar putea plati (0053_drepturi_grup.sql).
        poateCheltui: (rand.poate_cheltui as boolean | null) ?? true,
        tema: temaGrupValida(grup.tema),
        emblema: emblemaGrupValida(grup.emblema),
      },
    ];
  });
}

type GrupBrut = {
  id: number;
  nume: string;
  sold: number | string;
  creat_la: string;
  tema: string | null;
  emblema: string | null;
};

/** Un grup dupa id. Null daca nu exista sau daca utilizatorul nu e in el (RLS). */
export async function obtineGrup(id: number): Promise<Grup | null> {
  const supabase = await createClient();

  const { data, error } = await supabase
    .from("groups")
    .select(
      "id, nume, sold, token_acces, creat_la, id_creator, tranzactii_vizibile, tema, emblema, fundal",
    )
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
    tranzactiiVizibile: (data.tranzactii_vizibile as boolean | null) ?? true,
    tema: temaGrupValida(data.tema as string | null),
    emblema: emblemaGrupValida(data.emblema as string | null),
    fundal: fundalGrupValid(data.fundal as string | null),
  };
}

/**
 * Membrii grupului impreuna cu drepturile lor asupra soldului comun.
 *
 * Trece prin `public.drepturi_membri_grup` (SECURITY DEFINER), din acelasi
 * motiv ca `membri_grup`: politica de pe profiles lasa pe fiecare sa-si vada
 * doar propriul rand (0053_drepturi_grup.sql).
 */
export async function obtineDrepturileMembrilor(
  idGrup: number,
): Promise<MembruCuDrepturi[]> {
  const supabase = await createClient();

  const { data, error } = await supabase.rpc("drepturi_membri_grup", {
    p_id_group: idGrup,
  });

  if (error) throw error;

  return (data ?? []).map((membru: Record<string, unknown>) => ({
    idUser: membru.id_user as string,
    nume: membru.nume as string,
    avatarUrl: (membru.avatar_url as string | null) ?? null,
    creatLa: membru.creat_la as string,
    esteCreator: membru.este_creator as boolean,
    poateCheltui: membru.poate_cheltui as boolean,
    limitaLunara:
      membru.limita_lunara == null ? null : Number(membru.limita_lunara),
    cheltuitLuna: Number(membru.cheltuit_luna ?? 0),
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
