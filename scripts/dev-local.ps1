# Backend direct pe masina, frontend in container.
#
# De ce asa: backend-ul pe host poate folosi Entra (`az login`), deci nu mai e
# nevoie de nicio cheie in .env. Frontend-ul ramane in container fiindca cere
# Node.js, care nu e instalat.
#
# Pentru tot in Docker: scripts/dev-up-cloud.ps1.
$ErrorActionPreference = "Continue"

$radacina = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$venv = Join-Path $radacina "backend\.venv\Scripts\uvicorn.exe"

if (-not (Test-Path $venv)) {
  Write-Host "Nu exista mediul virtual. Il construiesc..."
  python -m venv (Join-Path $radacina "backend\.venv")
  & (Join-Path $radacina "backend\.venv\Scripts\pip.exe") install -e "$radacina\backend[dev]"
  if ($LASTEXITCODE -ne 0) { throw "Instalarea dependintelor a esuat." }
}

# Frontend-ul ruleaza in container si trebuie sa iasa la backend-ul de pe host.
$env:BACKEND_INTERNAL_URL = "http://host.docker.internal:8000"
docker compose up --build -d --no-deps frontend
if ($LASTEXITCODE -ne 0) { throw "Pornirea frontend-ului a esuat." }

Write-Host ""
Write-Host "Frontend: http://localhost:3000"
Write-Host "FastAPI docs: http://localhost:8000/docs"
Write-Host "Backend: pe masina, cu reincarcare la salvare. Ctrl+C il opreste."
Write-Host ""

Set-Location (Join-Path $radacina "backend")
& $venv app.main:app --reload --port 8000
