param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$SupabaseArgs
)

$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$imageName = "libra-galaxy-supabase-cli"
$dockerfile = Join-Path $PSScriptRoot "Dockerfile.supabase-cli"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  throw "Docker nu este disponibil. Instaleaza si porneste Docker Desktop."
}

docker image inspect $imageName *> $null
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
