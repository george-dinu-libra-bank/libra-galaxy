$ErrorActionPreference = "Stop"

# Edge Runtime needs a host filesystem path that is not available when the CLI
# itself runs in Docker. This project has no Edge Functions, so omit that service.
& "$PSScriptRoot\supabase.ps1" start --exclude edge-runtime

$statusArgs = @("status", "-o", "env")
$statusLines = & "$PSScriptRoot\supabase.ps1" @statusArgs
$supabaseValues = @{}
foreach ($line in $statusLines) {
  if ($line -match '^([A-Z_]+)="?(.*?)"?$') {
    $supabaseValues[$matches[1]] = $matches[2].TrimEnd('"')
  }
}

if (-not $supabaseValues.ContainsKey("ANON_KEY")) {
  throw "Supabase nu a returnat ANON_KEY. Verifica iesirea comenzii '.\scripts\supabase.ps1 status'."
}

$env:NEXT_PUBLIC_SUPABASE_ANON_KEY = $supabaseValues["ANON_KEY"]
docker compose up --build -d
docker compose ps

Write-Host "Frontend: http://localhost:3000"
Write-Host "FastAPI docs: http://localhost:8000/docs"
Write-Host "Supabase Studio: http://localhost:54323"
