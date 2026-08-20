"""Verifica ruta /alerte prin HTTP real, pe datele din Supabase.

    python scripts/verifica_alerte_http.py --user <uuid>

Porneste serverul pe un port liber si trimite cereri adevarate prin socket, ca
sa treaca prin tot ce trece si o cerere din browser: uvicorn, rutare, validare,
serializare. Doar verificarea tokenului e inlocuita, ca scriptul sa nu aiba
nevoie de parola cuiva; bariera de autentificare e verificata separat, la
inceput, inainte de inlocuire.

Cere SUPABASE_URL si SUPABASE_SERVICE_ROLE_KEY in mediu (sau in backend/.env).
"""

import argparse
import json
import os
import pathlib
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from uuid import UUID

RADACINA = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RADACINA / "backend"))


def _mediu() -> tuple[str, str]:
    url = os.environ.get("SUPABASE_URL", "")
    cheie = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if url and cheie:
        return url.rstrip("/"), cheie

    cale = RADACINA / "backend" / ".env"
    if cale.exists():
        valori = {}
        for linie in cale.read_text(encoding="utf-8").splitlines():
            if linie.strip() and not linie.startswith("#") and "=" in linie:
                nume, _, valoare = linie.partition("=")
                valori[nume.strip()] = valoare.strip()
        url = url or valori.get("SUPABASE_URL", "")
        cheie = cheie or valori.get("SUPABASE_SERVICE_ROLE_KEY", "")

    if not url or not cheie:
        raise SystemExit("Am nevoie de SUPABASE_URL si SUPABASE_SERVICE_ROLE_KEY.")
    return url.rstrip("/"), cheie


def _port_liber() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _cere(url: str, token: str | None = None) -> tuple[int, str]:
    cerere = urllib.request.Request(url)
    if token:
        cerere.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(cerere, timeout=60) as raspuns:
            return raspuns.status, raspuns.read().decode()
    except urllib.error.HTTPError as eroare:
        return eroare.code, eroare.read().decode("utf-8", "replace")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", default="84caf4a1-a7f5-4b95-bd83-836bbdb541d6")
    argumente = parser.parse_args()

    url_supabase, cheie = _mediu()
    os.environ.setdefault("SUPABASE_URL", url_supabase)
    os.environ.setdefault("SUPABASE_ANON_KEY", cheie)

    import uvicorn
    from supabase import create_client

    from app.api.dependencies import UserContext, get_current_user, get_user_supabase
    from app.main import app

    port = _port_liber()
    baza = f"http://127.0.0.1:{port}/api/v1"

    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    )
    threading.Thread(target=server.run, daemon=True).start()

    for _ in range(50):
        if server.started:
            break
        time.sleep(0.2)
    else:
        raise SystemExit("Serverul nu a pornit.")

    esecuri = 0

    def verifica(eticheta: str, obtinut, asteptat) -> None:
        nonlocal esecuri
        ok = obtinut == asteptat
        esecuri += 0 if ok else 1
        print(f"  [{'ok ' if ok else 'ESEC'}] {eticheta}: {obtinut}", end="")
        print("" if ok else f"  (asteptat {asteptat})")

    try:
        print(f"\nserver pornit pe {baza}\n")
        print("bariera de autentificare (fara inlocuiri):")
        cod, _ = _cere(f"{baza}/health")
        verifica("GET /health", cod, 200)
        cod, _ = _cere(f"{baza}/alerte?zile=180")
        verifica("GET /alerte fara token", cod, 401)
        cod, _ = _cere(f"{baza}/alerte?zile=180", token="token-inventat")
        verifica("GET /alerte cu token invalid", cod, 401)

        # De aici incolo, identitatea e fixata: verificarea tokenului tocmai a
        # fost confirmata mai sus, iar scriptul nu are parola nimanui.
        utilizator = UserContext(user_id=UUID(argumente.user), access_token="stub")
        client = create_client(url_supabase, cheie)
        app.dependency_overrides[get_current_user] = lambda: utilizator
        app.dependency_overrides[get_user_supabase] = lambda: client

        print("\nvalidarea parametrilor:")
        cod, _ = _cere(f"{baza}/alerte?zile=400")
        verifica("zile=400", cod, 422)
        cod, _ = _cere(f"{baza}/alerte?zile=0")
        verifica("zile=0", cod, 422)

        print("\ncerere autentificata pe date reale:")
        cod, corp = _cere(f"{baza}/alerte?zile=180")
        verifica("GET /alerte?zile=180", cod, 200)

        if cod != 200:
            print(f"  raspuns: {corp[:300]}")
            return 1

        constatari = json.loads(corp)
        print(f"\n  {len(constatari)} constatari primite prin HTTP\n")

        campuri = {
            "id_tranzactie",
            "data",
            "suma",
            "valuta",
            "comerciant",
            "tip",
            "explicatie",
            "scor",
        }
        if constatari:
            verifica("forma raspunsului", set(constatari[0]), campuri)
            scoruri = [c["scor"] for c in constatari]
            verifica("ordonate dupa scor", scoruri == sorted(scoruri, reverse=True), True)

        for c in constatari[:8]:
            print(f"  [{c['scor']:7.2f}] {c['tip']:18} {c['suma']:9.2f} {c['valuta']}  {c['data']}")
            print(f"            {c['explicatie']}")
    finally:
        app.dependency_overrides.clear()
        server.should_exit = True

    print(f"\n{'toate verificarile au trecut' if not esecuri else f'{esecuri} esecuri'}")
    return 1 if esecuri else 0


if __name__ == "__main__":
    sys.exit(main())
