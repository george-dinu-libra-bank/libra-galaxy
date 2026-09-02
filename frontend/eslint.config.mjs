import nextCoreWebVitals from "eslint-config-next/core-web-vitals";
import nextTypescript from "eslint-config-next/typescript";

/**
 * Configurarea ESLint, in format flat.
 *
 * Pana la eslint-config-next 16, `next/core-web-vitals` si `next/typescript`
 * erau configuratii in stilul vechi (.eslintrc), iar fisierul asta le aducea
 * prin `FlatCompat.extends(...)`. De la 16 ele sunt EXPORTATE DIRECT ca
 * vectori de configuratie flat (`dist/core-web-vitals.js`, `dist/typescript.js`),
 * asa ca puntea de compatibilitate nu mai are ce sa converteasca: incerca sa le
 * valideze dupa schema veche, esua, si apoi crapa chiar in formatarea erorii
 * („Converting circular structure to JSON" — pluginurile flat se refera intre
 * ele, deci JSON.stringify intra in cerc). Rezultatul era ca `npm run lint`
 * nu apuca sa se uite la niciun fisier.
 *
 * Deci se importa direct, fara @eslint/eslintrc. `core-web-vitals` include deja
 * configuratia de baza a lui Next.
 */
const eslintConfig = [
  {
    ignores: [".next/**", "out/**", "build/**", "next-env.d.ts"],
  },
  ...nextCoreWebVitals,
  ...nextTypescript,
];

export default eslintConfig;
