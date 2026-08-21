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

if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host "Am creat .env din .env.example - completeaza-l cu credentialele Supabase/Foundry/Speech inainte sa astepti raspunsuri reale de la asistent."
    } else {
        Write-Error "Lipseste .env - vezi .env.example (radacina) pentru variabilele necesare."
        exit 1
    }
}

Write-Host "Pornesc Libra Galaxy - frontend: http://localhost:3000, backend: http://localhost:8000"
# -f explicit: exista si compose.yaml (scripts/dev-up*.ps1, Supabase local/cloud),
# care altfel ar castiga implicit fata de docker-compose.yml (Docker prefera
# numele "compose.yaml"), lasand deoparte montarea galaxy-bank-knowledge si
# hot-reload-ul din Dockerfile.dev.
docker compose -f docker-compose.yml up --build @ComposeArgs
