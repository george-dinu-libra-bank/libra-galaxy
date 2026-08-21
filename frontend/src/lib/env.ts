/**
 * Singurul loc care citeste process.env in frontend — echivalentul
 * backend/app/core/config.py. Variabilele NEXT_PUBLIC_* raman scrise literal
 * (nu acces dinamic): Next.js le inlocuieste la build oriunde apar in cod,
 * inclusiv intr-un modul importat, deci centralizarea e sigura si pentru
 * cod care ajunge in bundle-ul de browser.
 *
 * BACKEND_INTERNAL_URL e singurul nume canonic pentru URL-ul backend-ului —
 * inainte existau trei (BACKEND_INTERNAL_URL/BACKEND_API_URL/BACKEND_URL),
 * aparute in paralel in fisiere diferite, cu un singur nume prezent de fapt
 * in .env (vezi istoricul din lib/data/backend.ts).
 */

// "||", nu "??": cheile de mai jos pot fi prezente dar goale in .env
// (SUPABASE_INTERNAL_URL="" e placeholder-ul documentat pentru cazul cloud),
// iar "??" cade pe fallback doar la null/undefined, nu si la string gol.
export const BACKEND_INTERNAL_URL = process.env.BACKEND_INTERNAL_URL || "http://localhost:8000";
export const BACKEND_INTERNAL_API_KEY = process.env.BACKEND_INTERNAL_API_KEY;

export const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
export const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "";
// Doar pentru Supabase local prin Docker (scripts/dev-up.ps1) — containerele
// vorbesc cu Supabase prin host.docker.internal, browserul prin localhost.
export const SUPABASE_INTERNAL_URL = process.env.SUPABASE_INTERNAL_URL || SUPABASE_URL;
export const SUPABASE_SERVICE_ROLE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;

export const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL;

/**
 * Adevarat doar daca exista credentiale Supabase reale in mediu. Fara ele,
 * aplicatia ruleaza in mod previzualizare: fara login, cu profilul demo din
 * lib/mock-data.ts, ca interfata sa poata fi vazuta inainte ca backend-ul sa
 * fie legat.
 */
export const supabaseConfigurat = Boolean(SUPABASE_URL && SUPABASE_ANON_KEY);
