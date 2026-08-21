"""Obtine un access token de utilizator, pentru testat API-ul din /docs.

    python scripts/obtine_token.py                      # cere emailul si parola
    python scripts/obtine_token.py --email a@b.ro       # cere doar parola
    python scripts/obtine_token.py --doar-token         # numai tokenul, de copiat

Se autentifica la Supabase exact ca aplicatia. Parola nu se salveaza nicaieri si
nu se afiseaza la tastare. Tokenul e valabil o ora.
"""

import argparse
import getpass
import json
import pathlib
import sys
import urllib.error
import urllib.request

RADACINA = pathlib.Path(__file__).resolve().parent.parent


def mediu() -> tuple[str, str]:
    """Ia URL-ul si cheia publishable din primul .env care le are pe amandoua."""
    for cale in (RADACINA / ".env", RADACINA / "frontend" / ".env"):
        if not cale.exists():
            continue
        valori = {}
        for linie in cale.read_text(encoding="utf-8").splitlines():
            if linie.strip() and not linie.startswith("#") and "=" in linie:
                cheie, _, valoare = linie.partition("=")
                valori[cheie.strip()] = valoare.strip()
        url = valori.get("NEXT_PUBLIC_SUPABASE_URL", "")
        anon = valori.get("NEXT_PUBLIC_SUPABASE_ANON_KEY", "")
        if url and anon:
            return url.rstrip("/"), anon
    raise SystemExit("Nu am gasit NEXT_PUBLIC_SUPABASE_URL si ANON_KEY in .env.")


def autentifica(url: str, anon: str, email: str, parola: str) -> dict:
    cerere = urllib.request.Request(
        f"{url}/auth/v1/token?grant_type=password",
        data=json.dumps({"email": email, "password": parola}).encode(),
        headers={"apikey": anon, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(cerere, timeout=30) as raspuns:
        return json.loads(raspuns.read().decode())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--email")
    parser.add_argument("--doar-token", action="store_true", help="afiseaza numai tokenul")
    argumente = parser.parse_args()

    url, anon = mediu()
    email = argumente.email or input("email: ").strip()
    parola = getpass.getpass("parola: ")

    try:
        date = autentifica(url, anon, email, parola)
    except urllib.error.HTTPError as eroare:
        corp = eroare.read().decode("utf-8", "replace")
        try:
            detaliu = json.loads(corp)
            corp = detaliu.get("error_description") or detaliu.get("msg") or corp
        except json.JSONDecodeError:
            pass
        print(f"Autentificare esuata (HTTP {eroare.code}): {corp}", file=sys.stderr)
        if eroare.code == 400:
            print(
                "\nDaca parola e buna, verifica in Supabase daca emailul e confirmat: "
                "Authentication > Users.",
                file=sys.stderr,
            )
        return 1

    token = date["access_token"]

    if argumente.doar_token:
        print(token)
        return 0

    print()
    print("Token obtinut, valabil o ora.")
    print("Il pui in http://localhost:8000/docs -> Authorize.")
    print()
    print("Sau direct din linia de comanda:")
    print()
    comanda = (
        "curl -X POST http://localhost:8000/api/v1/agents/chat "
        '-H "Content-Type: application/json" '
        f'-H "Authorization: Bearer {token}" '
        """-d "{\\"mesaj\\": \\"cati bani am?\\"}" """
    )
    print("  " + comanda.strip())
    print()
    print("Tokenul singur:")
    print(token)
    return 0


if __name__ == "__main__":
    sys.exit(main())
