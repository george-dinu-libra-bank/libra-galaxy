# Porneste frontend + backend peste proiectul Supabase din .env (cloud).
# Pentru Supabase local foloseste dev-up.ps1.
#
# Comenzile native isi raporteaza esecul prin exit code, verificat explicit mai jos.
$ErrorActionPreference = "Continue"

$radacina = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$fisierEnv = Join-Path $radacina ".env"

if (-not (Test-Path $fisierEnv)) {
  throw "Lipseste .env la radacina. Copiaza .env.example si completeaza-l cu datele proiectului Supabase."
}

$valori = @{}
foreach ($linie in Get-Content $fisierEnv) {
  if ($linie -match '^\s*([A-Z_]+)\s*=\s*(.*)$') {
    $valori[$matches[1]] = $matches[2].Trim()
  }
}

foreach ($cheie in @("NEXT_PUBLIC_SUPABASE_URL", "SUPABASE_INTERNAL_URL", "NEXT_PUBLIC_SUPABASE_ANON_KEY")) {
  if (-not $valori[$cheie]) {
    throw "$cheie lipseste din .env."
  }
}

# Un dev-up.ps1 rulat mai devreme in aceeasi consola ar lasa cheia locala in
# mediu, iar mediul are prioritate fata de .env. O stergem ca sa castige .env.
Remove-Item Env:NEXT_PUBLIC_SUPABASE_ANON_KEY -ErrorAction SilentlyContinue
Remove-Item Env:SUPABASE_INTERNAL_URL -ErrorAction SilentlyContinue
Remove-Item Env:NEXT_PUBLIC_SUPABASE_URL -ErrorAction SilentlyContinue

Write-Host "Supabase: $($valori['NEXT_PUBLIC_SUPABASE_URL'])"
docker compose -f "$PSScriptRoot/../docker-compose.yml" up --build -d
if ($LASTEXITCODE -ne 0) {
  throw "docker compose up a esuat (cod $LASTEXITCODE)."
}
docker compose -f "$PSScriptRoot/../docker-compose.yml" ps

Write-Host "Frontend: http://localhost:3000"
Write-Host "FastAPI docs: http://localhost:8000/docs"
