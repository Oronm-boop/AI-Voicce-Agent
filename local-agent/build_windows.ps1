param(
  [switch]$Clean
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
  throw "Python virtual environment not found: $venvPython"
}

Push-Location $projectRoot
try {
  & $venvPython -m pip install -r requirements.txt -r requirements-packaging.txt

  if ($Clean) {
    if (Test-Path ".\build") { Remove-Item -LiteralPath ".\build" -Recurse -Force }
    if (Test-Path ".\dist\local-agent-runtime") {
      Remove-Item -LiteralPath ".\dist\local-agent-runtime" -Recurse -Force
    }
    if (Test-Path ".\runtime_entry.spec") { Remove-Item -LiteralPath ".\runtime_entry.spec" -Force }
  }

  & $venvPython -m PyInstaller `
    --noconfirm `
    --clean `
    --onedir `
    --name local-agent-runtime `
    --collect-submodules uvicorn `
    --collect-all sherpa_onnx `
    --hidden-import uvicorn.logging `
    runtime_entry.py

  $exePath = Join-Path $projectRoot "dist\local-agent-runtime\local-agent-runtime.exe"
  if (-not (Test-Path $exePath)) {
    throw "Build failed: executable not found at $exePath"
  }

  Write-Output "Build success: $exePath"
}
finally {
  Pop-Location
}
