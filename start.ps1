# Porneste toata aplicatia Libra Galaxy (frontend + backend) intr-un singur pas.
#
# Singura dependinta locala e Docker Desktop: nimeni nu instaleaza Node sau
# Python pe masina lui, totul (npm install, pip install) se face in imaginile
# din docker-compose.yml, la build.
#
# Rulare:  .\start.ps1          (foreground, Ctrl+C opreste tot)
#          .\start.ps1 -d       (fundal — vezi logs cu docker compose logs -f)

param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ComposeArgs
)

Set-Location $PSScriptRoot

docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Error "Docker nu ruleaza. Porneste Docker Desktop si incearca din nou."
    exit 1
}

if (-not (Test-Path "backend\.env")) {
    if (Test-Path "backend\.env.example") {
        Copy-Item "backend\.env.example" "backend\.env"
        Write-Host "Am creat backend\.env din .env.example - completeaza-l cu credentialele Foundry/Speech/Supabase inainte sa astepti raspunsuri reale de la asistent."
    } else {
        Write-Error "Lipseste backend\.env - vezi backend\.env.example pentru variabilele necesare."
        exit 1
    }
}

if (-not (Test-Path "frontend\.env")) {
    Write-Error "Lipseste frontend\.env (NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY, BACKEND_API_URL)."
    exit 1
}

Write-Host "Pornesc Libra Galaxy - frontend: http://localhost:3000, backend: http://localhost:8000"
# -f explicit: exista si compose.yaml (scripts/dev-up*.ps1, Supabase local/cloud),
# care altfel ar castiga implicit fata de docker-compose.yml (Docker prefera
# numele "compose.yaml"), lasand deoparte montarea galaxy-bank-knowledge si
# restul variabilelor din backend/.env (Foundry, Speech, atasamente).
docker compose -f docker-compose.yml up --build @ComposeArgs
