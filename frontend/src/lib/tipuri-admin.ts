/**
 * Formele de date ale zonei de administrare, si etichetele lor.
 *
 * Fisierul e curat: fara acces la retea, fara `server-only`. Componentele de
 * client au nevoie de tipuri si de numele in cuvinte ale categoriilor, dar nu
 * de functiile care aduc datele — iar daca ar sta impreuna, importul unei
 * etichete ar trage dupa el tot modulul de server si build-ul ar cadea.
 */

// -----------------------------------------------------------------------------
// Verificari de identitate
// -----------------------------------------------------------------------------

/**
 * `distanta_fete` e o DISTANTA, nu o similaritate: mai mic inseamna mai
 * asemanator, iar potrivirea trece cand distanta <= prag.
 */
export type CazVerificare = {
  id: string;
  id_user: string;
  nume: string;
  email: string;
  cnp_declarat: string | null;
  cnp_extras: string | null;
  cnp_se_potriveste: boolean | null;
  distanta_fete: number | null;
  prag: number | null;
  sub_prag: boolean | null;
  status: string;
  creat_la: string;
  reviewed_by: string | null;
  reviewed_at: string | null;
  notes: string | null;
};

export type CazVerificareDetaliu = CazVerificare & {
  url_buletin: string | null;
  url_selfie: string | null;
  secunde_valabilitate: number;
};

/** Cont ramas pe verification_status='pending' — nicio dovada trimisa inca. */
export type ContNeinceput = {
  id: string;
  nume: string;
  email: string;
  creat_la: string;
};

/** Un cont, asa cum apare in lista completa a administratorului. */
export type ProfilAdmin = {
  id: string;
  nume: string;
  email: string;
  verification_status: string;
  creat_la: string;
};

// -----------------------------------------------------------------------------
// Tranzactii semnalate
// -----------------------------------------------------------------------------

export type ContSemnalat = {
  id_utilizator: string;
  nume: string;
  email: string;
  numar_semnalari: number;
  scor_maxim: number;
  /** Cat de urgent merita contul o privire: cea mai grava constatare, plus
   *  cate sunt si cati bani inseamna. Dupa asta se ordoneaza lista. */
  gravitate: number;
  suma_totala: number;
  tipuri: string[];
};

export type Constatare = {
  id_tranzactie: string;
  data: string;
  suma: number;
  valuta: string;
  comerciant: string;
  tip: string;
  explicatie: string;
  scor: number;
};

export type Raport = {
  id_utilizator: string;
  nume: string;
  email: string;
  iban: string;
  zile: number;
  generat_la: string;
  total_tranzactii: number;
  numar_semnalari: number;
  suma_semnalata: number;
  scor_maxim: number;
  pe_tip: Record<string, number>;
  sinteza: string | null;
  constatari: Constatare[];
};

/** Etichetele tipurilor, in cuvintele in care le-ar spune un om. */
export const ETICHETE_TIP: Record<string, string> = {
  suma_neobisnuita: "Sumă neobișnuită",
  plata_dublata: "Plată dublată",
  comerciant_nou: "Comerciant nou, sumă mare",
  rafala_de_plati: "Rafală de plăți",
  tipar_neobisnuit: "Tipar neobișnuit",
};

export function etichetaTip(tip: string): string {
  return ETICHETE_TIP[tip] ?? tip;
}

/**
 * Pragurile de gravitate, intr-un singur loc: lista, raportul si PDF-ul trebuie
 * sa spuna acelasi lucru despre acelasi scor.
 */
export function tonScor(scor: number): "grav" | "atentie" | "usor" {
  // Severitate 1-100, nu scorul brut de altadata. Pragurile sunt aceleasi cu
  // cele din raportul PDF (rapoarte/pdf_raport.py: _culoare_scor), ca aceeasi
  // constatare sa nu apara portocalie pe ecran si rosie in document.
  if (scor >= 70) return "grav";
  if (scor >= 45) return "atentie";
  return "usor";
}

// ---- Creditare ------------------------------------------------------------
//
// Sumele sosesc ca STRING, nu ca number: backendul le tine in `Decimal`, iar
// pydantic le serializeaza ca text tocmai ca sa nu treaca printr-un float pe
// drum. Se convertesc cu `Number()` la afisare, niciodata mai devreme.

export type StatusCerere =
  | "ciorna"
  | "in_analiza"
  | "oferta"
  | "analiza_manuala"
  | "asteapta_documente"
  | "respinsa"
  | "acceptata"
  | "anulata"
  | "expirata";

/**
 * Ce poate face analistul cu un dosar aflat in lucru.
 *
 * Doua inchid discutia, doua o tin deschisa: `cere_documente` muta mingea la
 * client, `notifica` doar il anunta fara sa schimbe starea dosarului.
 */
export type ActiuneAnalist = "aproba" | "respinge" | "cere_documente" | "notifica";

/** Un factor al scorecard-ului, sau un motiv de respingere pe criterii hard. */
export type MotivSauFactor = {
  cod: string;
  text?: string;
  puncte?: number;
  maxim?: number;
  explicatie?: string;
};

/** Numarul de semnale AI din ultima rulare — pentru badge-ul din lista de cereri. */
export type SemnaleRezumat = {
  grave: number;
  atentie: number;
  informativ: number;
};

export type CerereCredit = {
  id: string;
  nume: string;
  status: StatusCerere;
  suma_ceruta: string;
  luni: number;
  creat_la: string;
  scor: number | null;
  dti: string | null;
  rata_lunara: string | null;
  dae: string | null;
  explicatie: string | null;
  oferta_expira_la: string | null;
  venit_folosit: string | null;
  obligatii_folosite: string | null;
  motive: MotivSauFactor[];
  /** null cand pipeline-ul AI consultativ n-a rulat inca pentru cererea asta. */
  semnale: SemnaleRezumat | null;
  /** Cate mesaje ale clientului n-a deschis inca banca. Pe rutele clientului
   * acelasi camp inseamna invers — vezi CerereResponse din schemas/credit.py. */
  mesaje_necitite: number;
};

export type VerificareVenit = {
  sursa: "tranzactii" | "adeverinta" | "declarat" | "birou_credit";
  venit_constatat: string | null;
  obligatii_constatate: string | null;
  incredere: string | null;
  detalii: Record<string, unknown>;
  creat_la: string;
};

export type DocumentCerere = {
  id: string;
  tip: string;
  status: "incarcat" | "procesat" | "ilizibil" | "confirmat";
  content_type: string | null;
  marime_octeti: number | null;
  /** Ce a citit masina. Ramane neatins si dupa ce analistul corecteaza. */
  extras: {
    venit_net?: string | null;
    angajator?: string | null;
    vechime_luni?: number | null;
    incredere?: number;
    text?: string;
  };
  /** Ce a hotarat omul. Separat de `extras` dinadins — cand difera, se vede. */
  venit_confirmat: string | null;
  confirmat_la: string | null;
  /** Cand a fost sters fisierul dupa retentie. Randul ramane, documentul nu. */
  sters_la: string | null;
  creat_la: string;
  /** Link semnat, cu durata scurta. Lipseste dupa stergere. */
  url: string | null;
};

// -----------------------------------------------------------------------------
// Pipeline AI de credite — strict consultativ (app/credit/ai/, backend)
// -----------------------------------------------------------------------------

export type SeveritateSemnal = "grav" | "atentie" | "informativ";

/** Parerea etapei de brief — niciodata o decizie, vezi credit_ai_rulari.recomandare. */
export type Recomandare = "aproba" | "respinge" | "cere_document" | "fara_recomandare";

/** Un lucru pe care analistul ar trebui sa-l vada, nu o decizie — vezi
 * app/credit/ai/etape/coerenta.py. */
export type SemnalAi = {
  cod: string;
  severitate: SeveritateSemnal;
  titlu: string;
  detaliu: Record<string, unknown>;
  sursa: "coerenta" | "documente" | "brief";
};

export type EtapaAi = {
  etapa: "documente" | "coerenta" | "brief" | "explicatie";
  status: "reusit" | "esuat" | "sarit";
  versiune_prompt: string | null;
  deployment: string | null;
  rezultat: Record<string, unknown>;
  incredere: number | null;
  latenta_ms: number | null;
  cod_eroare: string | null;
  creat_la: string;
};

export type RulareAi = {
  id: string;
  status: "in_curs" | "finalizat" | "esuat";
  declansator: string;
  versiune_pipeline: string;
  recomandare: Recomandare | null;
  incredere: number | null;
  latenta_ms: number | null;
  cost_estimat_usd: number | null;
  creat_la: string;
  finalizat_la: string | null;
};

/** Panoul din dosarul cererii — ultima rulare, etapele ei, semnalele ei. */
export type DosarAi = {
  rulare: RulareAi;
  etape: EtapaAi[];
  semnale: SemnalAi[];
};

export type RezumatZilnicEtapa = {
  zi: string;
  etapa: string;
  reusite: number;
  esuate: number;
  sarite: number;
  latenta_medie_ms: number | null;
  latenta_p95_ms: number | null;
  tokeni_intrare: number;
  tokeni_iesire: number;
};

export type RataAcord = {
  total_comparabile: number;
  de_acord: number;
  rata: number | null;
};

/** Documentatie executabila — acelasi obiect din app/credit/ai/contracte.py. */
export type EtapaSpec = {
  id: string;
  scop: string;
  responsabilitati: string[];
  interzis: string[];
  are_nevoie_de_model: boolean;
  versiune_prompt: string | null;
  /** Promptul trimis efectiv modelului, citit din prompturi.py. */
  prompt_sistem: string | null;
};

export type ObservabilitateAi = {
  rezumat_zilnic: RezumatZilnicEtapa[];
  rata_acord: RataAcord;
  cost_estimat_usd_30_zile: number;
  etape: EtapaSpec[];
};

/** Un mesaj din firul dosarului — vezi migratia 0020. */
export type MesajCerere = {
  id: string;
  autor: "client" | "analist" | "sistem";
  text: string;
  id_document: string | null;
  creat_la: string;
};

/** O tranzitie din viata cererii. Se aduna de mult in `credit_evenimente`; pana
 * acum n-o citea nicio ruta, deci nu o vedea nici clientul, nici analistul. */
export type EvenimentCerere = {
  id: string;
  tip: string;
  actor: string;
  detalii: Record<string, unknown> | null;
  creat_la: string;
};

export type DosarCredit = {
  cerere: CerereCredit;
  verificari: VerificareVenit[];
  documente: DocumentCerere[];
  mesaje: MesajCerere[];
  evenimente: EvenimentCerere[];
  /** null cand pipeline-ul AI n-a rulat inca (Foundry cazut, sau catch-up-ul
   * lazy nu s-a declansat inca) — strict consultativ, niciodata blocant. */
  ai: DosarAi | null;
};

export type CreditAcordat = {
  id: string;
  nume: string;
  principal: string;
  dobanda_anuala: string;
  luni: number;
  rata_lunara: string;
  dae: string | null;
  sold_ramas: string;
  data_acordarii: string;
  status: string;
  inchis_la: string | null;
};

export const ETICHETE_STATUS: Record<StatusCerere, string> = {
  ciorna: "Ciornă",
  in_analiza: "În analiză",
  oferta: "Ofertă emisă",
  analiza_manuala: "Așteaptă decizie",
  asteapta_documente: "Așteaptă acte",
  respinsa: "Respinsă",
  acceptata: "Acceptată",
  anulata: "Anulată",
  expirata: "Expirată",
};

/** Codurile din app/credit/ai/etape/coerenta.py, in cuvinte pentru analist. */
export const ETICHETE_SEMNAL: Record<string, string> = {
  document_reutilizat: "Document reutilizat la altă cerere",
  venit_declarat_umflat: "Venit declarat peste ce arată încasările",
  angajator_nepotrivit: "Angajator fără legătură cu platitorul",
  document_vs_tranzactii: "Adeverința diferă de încasările din cont",
  incasari_pregatitoare: "Încasare atipică, chiar înainte de cerere",
  venit_neregulat: "Încasări neregulate de la o lună la alta",
  document_ilizibil: "Document ilizibil pentru citire automată",
};

export function etichetaSemnal(cod: string): string {
  return ETICHETE_SEMNAL[cod] ?? cod;
}

export const ETICHETE_SURSA: Record<VerificareVenit["sursa"], string> = {
  tranzactii: "Încasări în cont",
  adeverinta: "Adeverință de venit",
  declarat: "Declarat de client",
  birou_credit: "Expuneri la alte bănci",
};

/**
 * Tonul unui status, pentru culoarea etichetei.
 *
 * `analiza_manuala` e „atentie", nu „rau": nu s-a hotarat nimic inca, doar ca
 * hotararea o ia un om. O eticheta rosie ar face un dosar in lucru sa para deja
 * pierdut, si ar impinge analistul spre respingere inainte sa se uite la el.
 */
export function tonStatus(status: StatusCerere): "bun" | "rau" | "atentie" | "neutru" {
  if (status === "oferta" || status === "acceptata") return "bun";
  if (status === "respinsa") return "rau";
  if (status === "analiza_manuala" || status === "asteapta_documente") return "atentie";
  return "neutru";
}

/** Suma din backend (string zecimal) in lei formatati romaneste. */
export function lei(valoare: string | number | null | undefined): string {
  if (valoare === null || valoare === undefined) return "—";
  return Number(valoare).toLocaleString("ro-RO", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

/**
 * Starea stratului de model din detectia de anomalii.
 *
 * Lipsa modelului e tacuta prin proiectare — detectia continua pe reguli
 * statistice — asa ca panoul trebuie sa o spuna explicit. Altfel un
 * administrator ia decizii pe o lista incompleta fara sa aiba de unde sti.
 */
export type StareDetectie = {
  activ: boolean;
  antrenat_la: string | null;
  marime_kb: number | null;
  explicatie: string;
};

// ---- Analiza unui cont ----------------------------------------------------

export type Decizie = "acceptat" | "frauda" | "deblocat";

export type RezultatAnaliza = {
  decizie: Decizie;
  observatie: string | null;
  conturi_atinse: number;
  notificare_trimisa: boolean;
  creat_la: string;
};

export type IstoricAnaliza = {
  id: string;
  decizie: Decizie;
  observatie: string | null;
  gravitate: number | null;
  numar_semnalari: number | null;
  conturi_blocate: number;
  creat_la: string;
};

export const ETICHETE_DECIZIE: Record<Decizie, string> = {
  acceptat: "Verificat, fără probleme",
  frauda: "Confirmat ca fraudă",
  deblocat: "Deblocat",
};

export type StareCont = {
  conturi_total: number;
  conturi_blocate: number;
  analize: IstoricAnaliza[];
};

export type StareConturi = {
  id_utilizator: string;
  total: number;
  blocate: number;
};


// -----------------------------------------------------------------------------
// Cereri de inchidere a relatiei cu banca (0036-0038)
//
// Tipurile si regulile stau AICI, nu langa `backendFetch`, fiindca de ele au
// nevoie si componentele de client. Modulele din `lib/data/` importa
// `@/lib/backend`, care e `server-only`: un singur import de-acolo intr-o
// componenta „use client" opreste build-ul intreg cu
// „You're importing a module that depends on server-only".
// -----------------------------------------------------------------------------

export type ContClient = {
  nume: string | null;
  sold: string;
  valuta: string | null;
  blocat: boolean;
};

export type CerereStergere = {
  id: string;
  id_utilizator: string;
  nume: string | null;
  email: string | null;
  motiv: string | null;
  status: string;
  creat_la: string;
  decis_la: string | null;
  motiv_refuz: string | null;
  conturi: ContClient[];
  credite_in_derulare: number;
};

/** Toate conturile pe zero, fara blocari si fara credite — vezi 0038. */
export function sePoateSterge(cerere: CerereStergere): boolean {
  return (
    cerere.status === "aprobata" &&
    cerere.credite_in_derulare === 0 &&
    cerere.conturi.every((cont) => Number(cont.sold) === 0 && !cont.blocat)
  );
}

/** De ce nu se poate, in cuvinte — ca butonul dezactivat sa nu fie mut. */
export function motiveleStergerii(cerere: CerereStergere): string[] {
  const motive: string[] = [];

  if (cerere.status !== "aprobata") {
    motive.push("Cererea trebuie aprobată întâi.");
  }
  if (cerere.credite_in_derulare > 0) {
    motive.push(`Are ${cerere.credite_in_derulare} credit(e) în derulare.`);
  }

  const cuBani = cerere.conturi.filter((cont) => Number(cont.sold) !== 0);
  if (cuBani.length > 0) {
    motive.push(
      `Are sold în ${cuBani.length} cont(uri): ` +
        cuBani.map((c) => `${c.nume ?? "Cont"} ${c.sold} ${c.valuta ?? ""}`.trim()).join(", ") +
        ".",
    );
  }

  const blocate = cerere.conturi.filter((cont) => cont.blocat);
  if (blocate.length > 0) {
    motive.push(`Are ${blocate.length} cont(uri) blocate administrativ.`);
  }

  return motive;
}


// -----------------------------------------------------------------------------
// Cereri de inchidere a unui CONT BANCAR (0040)
//
// Alta operatiune decat cea de mai sus, si se confunda usor: acolo pleaca omul
// din banca, aici se inchide un singur cont bancar si omul ramane client.
// -----------------------------------------------------------------------------

export type ContAdmin = {
  id: string;
  nume: string | null;
  sold: string;
  valuta: string | null;
  blocat: boolean;
  inchis: boolean;
  este_principal: boolean;
};

export type CardInchis = {
  id: string;
  ultimele4: string;
  tip: string | null;
};

export type CerereInchidere = {
  id: string;
  id_utilizator: string;
  id_cont: string;
  id_cont_destinatie: string | null;
  nume: string | null;
  email: string | null;
  motiv: string | null;
  status: string;
  creat_la: string;
  decis_la: string | null;
  motiv_refuz: string | null;
  cont: ContAdmin | null;
  destinatii: ContAdmin[];
  carduri: CardInchis[];
};

/**
 * Destinatia din care porneste analistul: propunerea clientului daca mai e
 * valida, altfel contul principal, altfel primul deschis.
 *
 * Propunerea poate sa nu mai fie valida — contul ales de client putea fi inchis
 * intre timp — de aceea se cauta in `destinatii`, nu se foloseste id-ul brut.
 */
export function destinatiaImplicita(cerere: CerereInchidere): ContAdmin | null {
  const propusa = cerere.destinatii.find((c) => c.id === cerere.id_cont_destinatie);
  if (propusa) return propusa;
  return cerere.destinatii.find((c) => c.este_principal) ?? cerere.destinatii[0] ?? null;
}

/** De ce nu se poate aproba, in cuvinte — ca butonul dezactivat sa nu fie mut. */
export function motiveleInchiderii(cerere: CerereInchidere): string[] {
  const motive: string[] = [];
  const cont = cerere.cont;
  if (!cont) return ["Contul nu mai există."];

  if (cont.este_principal) {
    motive.push("E contul principal al clientului; acesta nu se poate închide.");
  }
  if (cont.blocat) {
    motive.push("Contul e blocat administrativ; se lămurește întâi blocarea.");
  }
  if (Number(cont.sold) < 0) {
    motive.push("Contul are sold negativ; se acoperă înainte de închidere.");
  }
  if (Number(cont.sold) > 0 && cerere.destinatii.length === 0) {
    motive.push("Are sold, dar clientul nu mai are alt cont deschis în care să fie mutat.");
  }
  return motive;
}

export function sePoateAproba(cerere: CerereInchidere): boolean {
  return cerere.status === "in_asteptare" && motiveleInchiderii(cerere).length === 0;
}


// -----------------------------------------------------------------------------
// Popriri
//
// Nu se confunda cu blocarea contului: blocarea (0030) opreste TOT ce pleaca
// dintr-un cont, poprirea (0047) indisponibilizeaza o SUMA pe toate conturile
// clientului. Pot fi si amandoua deodata.
// -----------------------------------------------------------------------------

export type Poprire = {
  id: string;
  id_utilizator: string;
  creditor: string;
  dosar: string | null;
  /** Sume in RON, ca text — vin din `numeric(14,2)`, nu prin float. */
  suma_totala: string;
  suma_incasata: string;
  valuta: string;
  status: "activa" | "stinsa" | "ridicata";
  creat_la: string;
  incheiat_la: string | null;
  observatie: string | null;
  nume: string | null;
  email: string | null;
  /** Soldul cumulat al clientului. Fara el nu se stie daca se poate incasa azi. */
  disponibil: string | null;
};

export function restDePlata(poprire: Poprire): number {
  return Number(poprire.suma_totala) - Number(poprire.suma_incasata);
}

/**
 * Cat se poate lua ACUM: `min(disponibil, rest de plata)`.
 *
 * Aceeasi formula ca in RPC (0047). Aici e doar ca sa nu ofere interfata un
 * buton care ar fi respins oricum — decizia ramane a bazei, care recalculeaza
 * cu soldul din momentul apasarii, nu cu cel de la incarcarea paginii.
 */
export function sePoateIncasaAcum(poprire: Poprire): number {
  const disponibil = Number(poprire.disponibil ?? 0);
  return Math.max(0, Math.min(disponibil, restDePlata(poprire)));
}

/**
 * Cat se poate aduce inapoi: exact cat s-a virat catre creditor.
 *
 * Se poate storna si dintr-o poprire stinsa sau ridicata — acolo e chiar cazul
 * obisnuit: contestatia a fost admisa dupa ce banca virase deja banii.
 */
export function sePoateStorna(poprire: Poprire): number {
  return Number(poprire.suma_incasata);
}
