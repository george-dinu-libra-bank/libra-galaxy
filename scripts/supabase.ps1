param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$SupabaseArgs
)

# Comenzile native isi raporteaza esecul prin exit code, verificat explicit mai jos.
# Pe Windows PowerShell 5.1, "Stop" ar transforma orice linie de stderr a lui docker
# intr-o eroare terminanta (NativeCommandError), chiar cand comanda reuseste.
$ErrorActionPreference = "Continue"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$imageName = "libra-galaxy-supabase-cli"
$dockerfile = Join-Path $PSScriptRoot "Dockerfile.supabase-cli"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  throw "Docker nu este disponibil. Instaleaza si porneste Docker Desktop."
}

docker image inspect $imageName 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
  Write-Host "Construiesc containerul pentru Supabase CLI (Node.js + npx)..."
  docker build --tag $imageName --file $dockerfile $projectRoot
  if ($LASTEXITCODE -ne 0) {
    throw "Construirea containerului Supabase CLI a esuat."
  }
}

$dockerArgs = @(
  "run",
  "--rm",
  "--network", "host",
  "--volume", "/var/run/docker.sock:/var/run/docker.sock",
  "--volume", "${projectRoot}:/workspace",
  "--workdir", "/workspace",
  $imageName
) + $SupabaseArgs

& docker @dockerArgs
if ($LASTEXITCODE -ne 0) {
  throw "Comanda Supabase CLI a esuat (cod $LASTEXITCODE)."
}
