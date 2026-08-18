/**
 * Adevarat doar daca exista credentiale Supabase reale in mediu (.env.local).
 * Fara ele, aplicatia ruleaza in mod previzualizare: fara login, cu profilul
 * demo din lib/mock-data.ts, ca interfata sa poata fi vazuta inainte ca
 * backend-ul sa fie legat.
 */
export const supabaseConfigurat = Boolean(
  process.env.NEXT_PUBLIC_SUPABASE_URL && process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY,
);
