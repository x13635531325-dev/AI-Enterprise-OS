$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$backendPath = Join-Path $repoRoot "backend"
$frontendPath = Join-Path $repoRoot "frontend\react-chat"

$env:PYTHONPATH = $backendPath
$testTemp = Join-Path $backendPath ("data\pytest-" + [Guid]::NewGuid().ToString("N"))
$env:TEMP = $testTemp
$env:TMP = $testTemp

Set-Location $repoRoot
pytest tests --basetemp $testTemp
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Set-Location $backendPath
python -m app.evals.run_rag_answer_eval --ci-mode --min-pass-rate 1.0 --no-save-report
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Set-Location $frontendPath
npm run lint
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
npm run build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
