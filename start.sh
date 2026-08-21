#!/usr/bin/env bash
# Porneste toata aplicatia Libra Galaxy (frontend + backend) intr-un singur pas.
#
# Singura dependinta locala e Docker: nimeni nu instaleaza Node sau Python pe
# masina lui, totul (npm install, pip install) se face in imaginile din
# docker-compose.yml, la build.
#
# Rulare:  ./start.sh          (foreground, Ctrl+C opreste tot)
#          ./start.sh -d       (fundal — vezi logs cu docker compose logs -f)

set -euo pipefail
cd "$(dirname "$0")"

if ! docker info >/dev/null 2>&1; then
  echo "Docker nu ruleaza. Porneste Docker Desktop si incearca din nou." >&2
  exit 1
fi

if [ ! -f backend/.env ]; then
  if [ -f backend/.env.example ]; then
    cp backend/.env.example backend/.env
    echo "Am creat backend/.env din .env.example — completeaza-l cu credentialele Foundry/Speech/Supabase inainte sa astepti raspunsuri reale de la asistent."
  else
    echo "Lipseste backend/.env — vezi backend/.env.example pentru variabilele necesare." >&2
    exit 1
  fi
fi

if [ ! -f frontend/.env ]; then
  echo "Lipseste frontend/.env (NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY, BACKEND_API_URL)." >&2
  exit 1
fi

echo "Pornesc Libra Galaxy — frontend: http://localhost:3000, backend: http://localhost:8000"
docker compose -f docker-compose.yml up --build "$@"
