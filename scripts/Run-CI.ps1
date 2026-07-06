[CmdletBinding()]
param(
    [switch]$SkipSync
)

$ErrorActionPreference = "Stop"
if ($PSVersionTable.PSVersion.Major -ge 7) {
    $PSNativeCommandUseErrorActionPreference = $true
}

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:UV_PYTHON = "3.11"

if (-not $env:CI) {
    if (-not $env:UV_CACHE_DIR) {
        $env:UV_CACHE_DIR = Join-Path $RepoRoot ".cache\uv"
    }
    if (-not $env:UV_PYTHON_INSTALL_DIR) {
        $env:UV_PYTHON_INSTALL_DIR = Join-Path $RepoRoot ".local\uv-python"
    }
}

function Invoke-NativeStep {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,

        [Parameter(Mandatory = $true)]
        [scriptblock]$Command
    )

    Write-Host "==> $Name"
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE"
    }
}

Push-Location $RepoRoot
try {
    Invoke-NativeStep "uv version" { uv --version }

    if (-not $SkipSync) {
        Invoke-NativeStep "dependency sync" { uv sync --frozen }
    }

    Invoke-NativeStep "python version" { uv run python --version }
    Invoke-NativeStep "compile check" { uv run python -m compileall -q app webui cli.py main.py }
    Invoke-NativeStep "unit tests" { uv run python -m unittest discover -s test }
}
finally {
    Pop-Location
}
