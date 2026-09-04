[CmdletBinding()]
param(
    [switch]$SkipSync
)

$ErrorActionPreference = "Stop"
if ($PSVersionTable.PSVersion.Major -ge 7) {
    $PSNativeCommandUseErrorActionPreference = $true
}

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")

# 固定 ruff 版本，保证本地与 GitHub Actions 得到一致的 lint 结果。
$RuffVersion = "0.16.6"

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

    # 只启用能捕获真实缺陷的规则：
    #   E9 = 语法/解析错误，F = pyflakes（未定义名称、未使用导入、无用赋值）。
    # 不引入风格类规则，避免给现有代码制造大量无关改动。
    # ruff 通过 uvx 按固定版本临时执行，不进入项目依赖，也不改动 uv.lock。
    Invoke-NativeStep "lint" {
        uvx ruff@$RuffVersion check --select E9,F app webui cli.py main.py test
    }

    Invoke-NativeStep "unit tests" { uv run python -m unittest discover -s test }
}
finally {
    Pop-Location
}
