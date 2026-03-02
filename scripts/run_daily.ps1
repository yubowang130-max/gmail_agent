$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

$venvPython = ".venv\Scripts\python.exe"
if (Test-Path $venvPython) {
  & $venvPython "src/main.py"
} else {
  python "src/main.py"
}
