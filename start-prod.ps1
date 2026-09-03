# Porneste Libra Galaxy in varianta de productie: frontend-ul trece prin
# "npm run build" si ruleaza serverul standalone, in loc de "next dev".
#
# start.ps1 ramane scriptul de zi cu zi (hot-reload). Foloseste-l pe acesta
# cand vrei sa vezi aplicatia asa cum ajunge in productie sau cand vrei ca
# erorile de TypeScript sa opreasca pornirea — "next build" pica la ele,
# "next dev" nu.
#
# Rulare:  .\start-prod.ps1          (foreground, Ctrl+C opreste tot)
#          .\start-prod.ps1 -d       (fundal - vezi logs cu docker compose logs -f)
#
# Diferente fata de start.ps1, ca sa nu te surprinda:
#   - nu exista hot reload; orice modificare de cod cere repornirea scriptului
#   - pornirea e mult mai lenta, pentru ca "next build" ruleaza in imagine
#   - SUPABASE_URL si SUPABASE_ANON_KEY trebuie completate in .env INAINTE de
#     build: se coc in bundle-ul de client si nu se mai pot schimba dupa

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
        Write-Error "Am creat .env din .env.example. Completeaza-l INAINTE de build: variabilele NEXT_PUBLIC_* se inlineaza in bundle la build, nu se citesc la pornire."
        exit 1
    } else {
        Write-Error "Lipseste .env - vezi .env.example (radacina) pentru variabilele necesare."
        exit 1
    }
}

Write-Host "Construiesc si pornesc Libra Galaxy (build de productie) - frontend: http://localhost:3000, backend: http://localhost:8000"
Write-Host "Primul build dureaza cateva minute."
docker compose -f docker-compose.prod.yml up --build @ComposeArgs
