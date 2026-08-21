import Link from "next/link";
import { notFound } from "next/navigation";
import { ChevronLeft } from "lucide-react";
import { cereAdmin } from "@/lib/admin";
import { obtineCaz } from "@/lib/data/admin-verificari";
import { BackendError } from "@/lib/backend";
import { EticheteCaz } from "@/components/admin/etichete-caz";
import { DeciziaCazului } from "@/components/admin/decizia-cazului";
import { PozeCaz } from "@/components/admin/poze-caz";

export const dynamic = "force-dynamic";

export default async function PaginaCaz({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const admin = await cereAdmin();

  const caz = await obtineCaz(admin.token, id).catch((exc) => {
    if (exc instanceof BackendError && exc.status === 404) notFound();
    throw exc;
  });

  const decis = caz.status !== "pending_review";

  return (
    <div className="flex flex-col gap-6">
      <Link
        href="/admin"
        className="inline-flex w-fit items-center gap-1.5 text-[13px] font-semibold text-primary-600 hover:underline"
      >
        <ChevronLeft size={16} strokeWidth={2} aria-hidden />
        Toate cazurile
      </Link>

      <div>
        <h1 className="text-[26px] font-bold leading-8 tracking-[-0.02em] text-ink">
          {caz.nume}
        </h1>
        <p className="mt-1 text-[15px] text-ink-soft">{caz.email}</p>
        <EticheteCaz caz={caz} className="mt-3" />
      </div>

      <PozeCaz
        urlBuletin={caz.url_buletin}
        urlSelfie={caz.url_selfie}
        secunde={caz.secunde_valabilitate}
      />

      <section className="rounded-card border border-line bg-surface p-5">
        <h2 className="text-[15px] font-semibold text-ink">Ce spun dovezile</h2>

        <div className="mt-3">
          <Rand
            eticheta="Distanța dintre fețe"
            valoare={
              caz.distanta_fete === null
                ? "Nu s-a detectat o față clară"
                : `${caz.distanta_fete.toFixed(5)} (prag ${caz.prag?.toFixed(2) ?? "—"})`
            }
            nota={
              caz.distanta_fete === null
                ? "Fără o față detectată, comparația nu s-a putut face."
                : caz.sub_prag
                  ? "Sub prag: fețele se potrivesc. Mai mic înseamnă mai asemănător."
                  : "Peste prag: fețele nu se potrivesc destul."
            }
          />
          <Rand eticheta="CNP declarat la înregistrare" valoare={caz.cnp_declarat ?? "—"} mono />
          <Rand
            eticheta="CNP citit de pe buletin"
            valoare={caz.cnp_extras ?? "Nu a putut fi citit"}
            mono={Boolean(caz.cnp_extras)}
            nota={
              caz.cnp_se_potriveste === null
                ? "OCR-ul nu a găsit un CNP în poză; compară-l tu cu ochiul."
                : caz.cnp_se_potriveste
                  ? "Identic cu cel declarat."
                  : "Diferit de cel declarat — verifică poza cu atenție."
            }
          />
          <Rand
            eticheta="Trimis la"
            valoare={new Date(caz.creat_la).toLocaleString("ro-RO", {
              day: "numeric",
              month: "long",
              year: "numeric",
              hour: "2-digit",
              minute: "2-digit",
            })}
          />
        </div>
      </section>

      {decis ? (
        <section className="rounded-card border border-line bg-muted p-5">
          <p className="text-[15px] font-semibold text-ink">
            Cazul a fost {caz.status === "verified" ? "aprobat" : "respins"}
          </p>
          {caz.reviewed_at ? (
            <p className="mt-1 text-[13px] text-ink-faint">
              {new Date(caz.reviewed_at).toLocaleString("ro-RO", {
                day: "numeric",
                month: "long",
                year: "numeric",
                hour: "2-digit",
                minute: "2-digit",
              })}
            </p>
          ) : null}
          {caz.notes ? (
            <p className="mt-3 text-[13px] leading-[19px] text-ink-soft">„{caz.notes}"</p>
          ) : null}
        </section>
      ) : (
        <DeciziaCazului verificationId={caz.id} nume={caz.nume} />
      )}
    </div>
  );
}

function Rand({
  eticheta,
  valoare,
  nota,
  mono,
}: {
  eticheta: string;
  valoare: string;
  nota?: string;
  mono?: boolean;
}) {
  return (
    <div className="border-b border-line py-3 last:border-0">
      <div className="flex items-start justify-between gap-4">
        <span className="text-[13px] text-ink-faint">{eticheta}</span>
        <span className={`text-right text-[15px] text-ink ${mono ? "tabular" : ""}`}>
          {valoare}
        </span>
      </div>
      {nota ? <p className="mt-1 text-[12.5px] leading-[18px] text-ink-faint">{nota}</p> : null}
    </div>
  );
}
