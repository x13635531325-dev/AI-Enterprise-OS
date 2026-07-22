$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$backendPath = Join-Path $repoRoot "backend"

$env:PYTHONPATH = $backendPath
Set-Location $backendPath

python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
