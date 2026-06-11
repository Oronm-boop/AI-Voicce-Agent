param(
  [switch]$Clean,
  [switch]$SkipMcp
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
    if (Test-Path ".\dist\mcp-server") {
      Remove-Item -LiteralPath ".\dist\mcp-server" -Recurse -Force
    }
    if (Test-Path ".\mcp_server_entry.spec") { Remove-Item -LiteralPath ".\mcp_server_entry.spec" -Force }
  }

  # ── Build local-agent-runtime ──────────────────────────────────────────────
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

  $runtimeDir = Split-Path -Parent $exePath
  $modelsSource = Join-Path $projectRoot "models"
  $modelsTarget = Join-Path $runtimeDir "models"
  if (Test-Path $modelsSource) {
    if (Test-Path $modelsTarget) {
      Remove-Item -LiteralPath $modelsTarget -Recurse -Force
    }
    Copy-Item -LiteralPath $modelsSource -Destination $modelsTarget -Recurse
  }

  $projectRootParent = Split-Path -Parent $projectRoot
  $modelConfigSource = Join-Path $projectRootParent "model_config.json"
  if (Test-Path $modelConfigSource) {
    $modelConfigTarget = Join-Path $runtimeDir "model_config.json"
    Copy-Item -LiteralPath $modelConfigSource -Destination $modelConfigTarget -Force
    Write-Output "Copied model_config.json to $modelConfigTarget"
  }

  Write-Output "Build success: $exePath"

  # ── Build MCP server (windows-mcp) ────────────────────────────────────────
  if (-not $SkipMcp) {
    Write-Output ""
    Write-Output "=== Building MCP server ==="

    Write-Output "Installing windows-mcp into venv..."
    & $venvPython -m pip install "windows-mcp"

    # Discover the console_scripts entry point for windows-mcp
    $mcpEntryPoint = & $venvPython -c @"
try:
    from importlib.metadata import entry_points
    try:
        eps = list(entry_points(group='console_scripts'))
    except TypeError:
        eps = list(entry_points().get('console_scripts', []))
    found = [ep for ep in eps if ep.name == 'windows-mcp']
    print(found[0].value if found else 'NOT_FOUND')
except Exception as e:
    print('NOT_FOUND')
"@

    $mcpEntryPoint = $mcpEntryPoint.Trim()
    if ($mcpEntryPoint -eq "NOT_FOUND" -or [string]::IsNullOrEmpty($mcpEntryPoint)) {
      Write-Warning "Could not find windows-mcp console_scripts entry point. Skipping MCP server build."
      Write-Warning "MCP features will require manual installation of 'uvx windows-mcp'."
    } else {
      Write-Output "Discovered entry point: $mcpEntryPoint"

      # Parse "module:function" format
      $epParts   = $mcpEntryPoint -split ":"
      $epModule  = $epParts[0].Trim()
      $epFunc    = $epParts[1].Trim()
      # Top-level package name (e.g. windows_mcp)
      $epPackage = ($epModule -split "\.")[0]

      # Generate entry script (PowerShell expands $epModule / $epFunc here)
      $entryScriptContent = @"
import sys
from $epModule import $epFunc

if __name__ == '__main__':
    sys.exit($epFunc())
"@
      Set-Content -Path ".\mcp_server_entry.py" -Value $entryScriptContent -Encoding UTF8
      Write-Output "Generated mcp_server_entry.py (module=$epModule, func=$epFunc)"

      # Install typer (required by windows-mcp dependencies for PyInstaller analysis)
      & $venvPython -m pip install typer --quiet

      & $venvPython -m PyInstaller `
        --noconfirm `
        --clean `
        --onedir `
        --name mcp-server `
        --collect-all $epPackage `
        --collect-all fastmcp `
        --collect-all mcp `
        --collect-submodules uvicorn `
        --collect-submodules typer `
        --hidden-import uvicorn.logging `
        --hidden-import anyio `
        --hidden-import anyio._backends._asyncio `
        --hidden-import anyio._backends._trio `
        --hidden-import starlette `
        --hidden-import starlette.routing `
        --hidden-import starlette.middleware `
        --copy-metadata windows-mcp `
        --copy-metadata fastmcp `
        --copy-metadata fastmcp-slim `
        --copy-metadata mcp `
        --copy-metadata uvicorn `
        --copy-metadata starlette `
        --copy-metadata fastapi `
        --copy-metadata anyio `
        --copy-metadata pydantic `
        --copy-metadata httpx `
        --copy-metadata cyclopts `
        --copy-metadata rich `
        --copy-metadata typer `
        mcp_server_entry.py

      $mcpExePath = Join-Path $projectRoot "dist\mcp-server\mcp-server.exe"
      if (Test-Path $mcpExePath) {
        Write-Output "MCP server build success: $mcpExePath"
      } else {
        Write-Warning "MCP server executable not found at $mcpExePath — build may have failed."
      }
    }
  } else {
    Write-Output "Skipping MCP server build (-SkipMcp flag set)."
  }
}
finally {
  Pop-Location
}
