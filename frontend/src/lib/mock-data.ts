/**
 * Date simulate — nu exista inca tabele Supabase pentru conturi, tranzactii,
 * carduri si beneficiari (doar `profiles`). Backend-ul real vine separat;
 * functiile de mai jos sunt async si intorc forme apropiate de ce va veni
 * de la API, ca inlocuirea ulterioara sa fie directa.
 */

export type TipCont = "curent" | "economii";

export type Cont = {
  id: string;
  tip: TipCont;
  nume: string;
  iban: string;
  sold: number;
  valuta: string;
};

export type CategorieTranzactie =
  | "alimente"
  | "transport"
  | "utilitati"
  | "divertisment"
  | "shopping"
  | "sanatate"
  | "salariu"
  | "transfer"
  | "altele";

export type Tranzactie = {
  id: string;
  contId: string;
  tip: "incasare" | "plata";
  suma: number;
  valuta: string;
  descriere: string;
  categorie: CategorieTranzactie;
  comerciant: string;
  data: string;
  stare: "finalizata" | "in_asteptare";
};

export type Card = {
  id: string;
  contId: string;
  tip: "debit" | "credit";
  numarMascat: string;
  detinator: string;
  expira: string;
  stare: "activ" | "blocat";
  culoare: "primar" | "grafit";
  limitaZilnica: number;
  cheltuitAstazi: number;
};

export type Beneficiar = {
  id: string;
  nume: string;
  iban: string;
  banca: string;
  favorit: boolean;
};

export const ETICHETE_CATEGORII: Record<CategorieTranzactie, string> = {
  alimente: "Alimente",
  transport: "Transport",
  utilitati: "Utilitati",
  divertisment: "Divertisment",
  shopping: "Shopping",
  sanatate: "Sanatate",
  salariu: "Salariu",
  transfer: "Transfer",
  altele: "Altele",
};

function acumZileInUrma(zile: number, ora = "12:00") {
  const d = new Date();
  d.setDate(d.getDate() - zile);
  const [h, m] = ora.split(":").map(Number);
  d.setHours(h, m, 0, 0);
  return d.toISOString();
}

const CONTURI: Cont[] = [
  {
    id: "cont-curent",
    tip: "curent",
    nume: "Cont curent",
    iban: "RO49LIBR1B310075938400",
    sold: 4287.52,
    valuta: "RON",
  },
  {
    id: "cont-economii",
    tip: "economii",
    nume: "Economii",
    iban: "RO12LIBR9F204488310017",
    sold: 12500,
    valuta: "RON",
  },
];

const TRANZACTII: Tranzactie[] = [
  {
    id: "t1",
    contId: "cont-curent",
    tip: "plata",
    suma: 47.9,
    valuta: "RON",
    descriere: "Cumparaturi",
    categorie: "alimente",
    comerciant: "Kaufland",
    data: acumZileInUrma(0, "09:14"),
    stare: "finalizata",
  },
  {
    id: "t2",
    contId: "cont-curent",
    tip: "plata",
    suma: 18.5,
    valuta: "RON",
    descriere: "Abonament transport",
    categorie: "transport",
    comerciant: "STB",
    data: acumZileInUrma(0, "07:52"),
    stare: "finalizata",
  },
  {
    id: "t3",
    contId: "cont-curent",
    tip: "plata",
    suma: 32.0,
    valuta: "RON",
    descriere: "Prânz",
    categorie: "alimente",
    comerciant: "Glovo",
    data: acumZileInUrma(1, "13:20"),
    stare: "finalizata",
  },
  {
    id: "t4",
    contId: "cont-curent",
    tip: "plata",
    suma: 189.99,
    valuta: "RON",
    descriere: "Factura curent electric",
    categorie: "utilitati",
    comerciant: "Enel",
    data: acumZileInUrma(1, "10:05"),
    stare: "finalizata",
  },
  {
    id: "t5",
    contId: "cont-curent",
    tip: "incasare",
    suma: 6200,
    valuta: "RON",
    descriere: "Salariu august",
    categorie: "salariu",
    comerciant: "Angajator SRL",
    data: acumZileInUrma(2, "08:00"),
    stare: "finalizata",
  },
  {
    id: "t6",
    contId: "cont-curent",
    tip: "plata",
    suma: 64.0,
    valuta: "RON",
    descriere: "Abonament streaming",
    categorie: "divertisment",
    comerciant: "Netflix",
    data: acumZileInUrma(3, "19:41"),
    stare: "finalizata",
  },
  {
    id: "t7",
    contId: "cont-curent",
    tip: "plata",
    suma: 215.4,
    valuta: "RON",
    descriere: "Incaltaminte",
    categorie: "shopping",
    comerciant: "Zalando",
    data: acumZileInUrma(4, "16:12"),
    stare: "finalizata",
  },
  {
    id: "t8",
    contId: "cont-curent",
    tip: "plata",
    suma: 89.0,
    valuta: "RON",
    descriere: "Consultatie",
    categorie: "sanatate",
    comerciant: "Regina Maria",
    data: acumZileInUrma(6, "11:30"),
    stare: "finalizata",
  },
  {
    id: "t9",
    contId: "cont-curent",
    tip: "plata",
    suma: 500,
    valuta: "RON",
    descriere: "Catre Economii",
    categorie: "transfer",
    comerciant: "Transfer intern",
    data: acumZileInUrma(7, "09:00"),
    stare: "finalizata",
  },
  {
    id: "t10",
    contId: "cont-curent",
    tip: "plata",
    suma: 76.2,
    valuta: "RON",
    descriere: "Combustibil",
    categorie: "transport",
    comerciant: "OMV",
    data: acumZileInUrma(9, "18:04"),
    stare: "finalizata",
  },
  {
    id: "t11",
    contId: "cont-curent",
    tip: "plata",
    suma: 145.0,
    valuta: "RON",
    descriere: "Factura internet",
    categorie: "utilitati",
    comerciant: "Digi",
    data: acumZileInUrma(12, "10:00"),
    stare: "finalizata",
  },
  {
    id: "t12",
    contId: "cont-curent",
    tip: "incasare",
    suma: 350,
    valuta: "RON",
    descriere: "Restituire",
    categorie: "altele",
    comerciant: "Andrei P.",
    data: acumZileInUrma(15, "20:22"),
    stare: "finalizata",
  },
  {
    id: "t13",
    contId: "cont-curent",
    tip: "plata",
    suma: 22.5,
    valuta: "RON",
    descriere: "Cafea si covrigi",
    categorie: "alimente",
    comerciant: "5 to Go",
    data: acumZileInUrma(18, "08:45"),
    stare: "finalizata",
  },
  {
    id: "t14",
    contId: "cont-curent",
    tip: "plata",
    suma: 60,
    valuta: "RON",
    descriere: "Bilete cinema",
    categorie: "divertisment",
    comerciant: "Cinema City",
    data: acumZileInUrma(22, "21:10"),
    stare: "finalizata",
  },
  {
    id: "t15",
    contId: "cont-curent",
    tip: "plata",
    suma: 128.3,
    valuta: "RON",
    descriere: "Plata in asteptare",
    categorie: "shopping",
    comerciant: "eMAG",
    data: acumZileInUrma(0, "15:02"),
    stare: "in_asteptare",
  },
];

const CARDURI: Card[] = [
  {
    id: "card-1",
    contId: "cont-curent",
    tip: "debit",
    numarMascat: "•••• •••• •••• 4521",
    detinator: "TITULAR CONT",
    expira: "08/28",
    stare: "activ",
    culoare: "primar",
    limitaZilnica: 5000,
    cheltuitAstazi: 66.4,
  },
  {
    id: "card-2",
    contId: "cont-curent",
    tip: "credit",
    numarMascat: "•••• •••• •••• 7788",
    detinator: "TITULAR CONT",
    expira: "03/27",
    stare: "blocat",
    culoare: "grafit",
    limitaZilnica: 2000,
    cheltuitAstazi: 0,
  },
];

const BENEFICIARI: Beneficiar[] = [
  {
    id: "b1",
    nume: "Andrei Popescu",
    iban: "RO91BTRL0000000012345678",
    banca: "Banca Transilvania",
    favorit: true,
  },
  {
    id: "b2",
    nume: "Maria Ionescu",
    iban: "RO49BRDE310SV00012345601",
    banca: "BRD",
    favorit: true,
  },
  {
    id: "b3",
    nume: "Enel Energie",
    iban: "RO22RNCB0082000123456789",
    banca: "BCR",
    favorit: false,
  },
  {
    id: "b4",
    nume: "Cristina Dumitrescu",
    iban: "RO35INGB0000999912345678",
    banca: "ING Bank",
    favorit: false,
  },
];

/** Folosit pe dashboard si in Setari cat timp nu exista credentiale Supabase reale. */
export const PROFIL_DEMO = {
  nume: "Ana Popescu",
  cnp: "2960101123456",
  telefon: "+40712345678",
  email: "ana.popescu@exemplu.ro",
  iban_cont: "RO49LIBR1B310075938400",
  creat_la: "2025-01-15T09:00:00.000Z",
};

export async function obtineConturi(): Promise<Cont[]> {
  return CONTURI;
}

export async function obtineCont(id: string): Promise<Cont | undefined> {
  return CONTURI.find((c) => c.id === id);
}

export async function obtineTranzactii(): Promise<Tranzactie[]> {
  return [...TRANZACTII].sort((a, b) => (a.data < b.data ? 1 : -1));
}

export async function obtineCarduri(): Promise<Card[]> {
  return CARDURI;
}

export async function obtineBeneficiari(): Promise<Beneficiar[]> {
  return [...BENEFICIARI].sort((a, b) => Number(b.favorit) - Number(a.favorit));
}
