"use client";

import LogoLoop from "@/components/reactbits/LogoLoop";
import { useMiscareRedusa } from "@/hooks/use-miscare-redusa";

const TEHNOLOGII = [
  "Next.js 16",
  "React 19",
  "Tailwind CSS 4",
  "TypeScript",
  "Supabase",
  "PostgreSQL",
  "FastAPI",
  "Python",
  "Docker",
];

function Pastila({ text }: { text: string }) {
  return (
    <span className="whitespace-nowrap rounded-full border border-line bg-surface px-4 py-2 text-[13px] font-medium text-ink-soft">
      {text}
    </span>
  );
}

/**
 * Banda cu tehnologii. Pastile de text, nu logo-uri: n-avem drepturile pe
 * marcile respective si nici fisierele in `public/`, iar un logo lipsa e mai
 * urat decat lipsa lui cu totul.
 */
export function Stack() {
  const miscareRedusa = useMiscareRedusa();

  const logos = TEHNOLOGII.map((text) => ({
    node: <Pastila text={text} />,
    title: text,
    ariaLabel: text,
  }));

  return (
    <section className="mx-auto w-full max-w-6xl px-5 py-12 sm:px-8">
      <p className="text-center text-[12.5px] font-semibold uppercase tracking-[0.08em] text-ink-faint">
        Construită cu
      </p>

      <div className="mt-5">
        {miscareRedusa ? (
          <ul className="flex flex-wrap justify-center gap-2.5">
            {TEHNOLOGII.map((text) => (
              <li key={text}>
                <Pastila text={text} />
              </li>
            ))}
          </ul>
        ) : (
          <LogoLoop
            logos={logos}
            speed={40}
            gap={14}
            logoHeight={38}
            pauseOnHover
            fadeOut
            fadeOutColor="var(--color-bg)"
            ariaLabel="Tehnologiile pe care e construită aplicația"
          />
        )}
      </div>
    </section>
  );
}
