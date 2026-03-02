param(
  [string]$VenvDir = ".venv"
)

$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

if (-not (Test-Path $VenvDir)) {
  python -m venv $VenvDir
}

$python = Join-Path $VenvDir "Scripts\python.exe"
& $python -m pip install --upgrade pip
& $python -m pip install -r requirements.txt

Write-Host "Install complete. Use: $python src/main.py"
