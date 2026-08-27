import {
  ArrowLeftRight,
  Calculator,
  CreditCard,
  Landmark,
  ListFilter,
  QrCode,
  ShoppingBag,
  Sparkles,
  Users,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import SpotlightCard from "@/components/reactbits/SpotlightCard";
import { AntetSectiune } from "./antet";
import { RamaTelefon } from "./rama-telefon";
import { CAPTURI } from "./capturi";

const FUNCTII: { icoana: LucideIcon; titlu: string; text: string }[] = [
  {
    icoana: Landmark,
    titlu: "Cont curent cu IBAN",
    text: "Primești IBAN-ul imediat după verificarea identității. Soldul și ultimele mișcări, pe primul ecran.",
  },
  {
    icoana: ArrowLeftRight,
    titlu: "Transfer instant",
    text: "Alegi beneficiarul dintr-o listă salvată, confirmi într-un drawer și banii pleacă. Fără pagini intermediare.",
  },
  {
    icoana: QrCode,
    titlu: "Încasare prin cod QR",
    text: "Generezi un cod cu suma deja completată. Cine scanează are formularul de plată gata.",
  },
  {
    icoana: ListFilter,
    titlu: "Istoric care se poate citi",
    text: "Grupat pe zile, filtrat după perioadă și sumă, cu detaliul fiecărei tranzacții într-un drawer.",
  },
  {
    icoana: CreditCard,
    titlu: "Carduri",
    text: "Emiți un card pe orice cont, îi alegi tematica vizuală și îl blochezi când nu-l folosești.",
  },
  {
    icoana: Calculator,
    titlu: "Credite, cap-coadă",
    text: "Simulezi rata, depui cererea și urmărești dosarul. Analiza pornește automat, decizia rămâne la om.",
  },
  {
    icoana: Users,
    titlu: "Grupuri cu sold comun",
    text: "Un cont împărțit și o conversație, pentru oamenii cu care împarți cheltuieli. Intri pe bază de link.",
  },
  {
    icoana: Sparkles,
    titlu: "Asistent pentru bani",
    text: "Întrebi în cuvintele tale unde s-au dus banii. Răspunsul vine din date reale, nu din presupuneri.",
  },
  {
    icoana: ShoppingBag,
    titlu: "Galaxy Shop",
    text: "O vitrină publică unde plătești direct cu cardul emis în aplicație — fluxul complet, de la coș la extras.",
  },
];

const ECRANE = [
  CAPTURI.transfer,
  CAPTURI.qr,
  CAPTURI.istoric,
  CAPTURI.carduri,
  CAPTURI.credite,
  CAPTURI.grupuri,
];

export function Functii() {
  return (
    <section id="functii" className="mx-auto w-full max-w-6xl scroll-mt-20 px-5 py-16 sm:px-8">
      <AntetSectiune
        supratitlu="Ce poți face"
        titlu="Toată banca, într-un singur ecran de telefon"
        subtitlu="Fiecare funcție e construită pentru 390 px lățime și abia apoi întinsă pe desktop — nu invers."
      />

      <div className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {FUNCTII.map(({ icoana: Icoana, titlu, text }) => (
          <SpotlightCard key={titlu} className="shadow-sm">
            <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary-50">
              <Icoana size={20} strokeWidth={1.75} aria-hidden className="text-primary-600" />
            </span>
            <h3 className="mt-4 text-[17px] font-semibold leading-6 text-ink">{titlu}</h3>
            <p className="mt-2 text-[14px] leading-[21px] text-ink-soft">{text}</p>
          </SpotlightCard>
        ))}
      </div>

      <h3 className="mt-14 text-[18px] font-semibold leading-6 text-ink">Ecranele, pe rând</h3>
      <p className="mt-1.5 text-[13px] leading-[19px] text-ink-faint sm:hidden">
        Derulează lateral.
      </p>

      {/* Pe telefon o banda care se deruleaza lateral; de la `sm` in sus o
          grila, altfel ultimul cadru ramane taiat de marginea ecranului. */}
      <ul className="-mx-5 mt-5 flex snap-x snap-mandatory gap-4 overflow-x-auto px-5 pb-4 sm:mx-0 sm:grid sm:grid-cols-2 sm:overflow-visible sm:px-0 sm:pb-0 lg:grid-cols-3">
        {ECRANE.map((captura) => (
          <li key={captura.fisier} className="w-[260px] shrink-0 snap-start sm:w-auto">
            <RamaTelefon captura={captura} className="mx-auto max-w-[280px]" />
          </li>
        ))}
      </ul>
    </section>
  );
}
