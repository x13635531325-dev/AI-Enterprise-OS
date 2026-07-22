$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$frontendPath = Join-Path $repoRoot "frontend\react-chat"

Set-Location $frontendPath

npm run dev
