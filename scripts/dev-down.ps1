$ErrorActionPreference = "Continue"

# Compose validates this interpolation even for `down`, although the value is
# not used while containers are being removed.
if (-not $env:NEXT_PUBLIC_SUPABASE_ANON_KEY) {
  $env:NEXT_PUBLIC_SUPABASE_ANON_KEY = "unused-by-compose-down"
}

docker compose down
& "$PSScriptRoot\supabase.ps1" stop
