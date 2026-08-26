
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
