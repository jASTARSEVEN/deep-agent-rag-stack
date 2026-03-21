# 專案層級說明：
# 這支腳本用於 Windows PowerShell 的 Marker worker 安裝流程。
# 它會建立或重用 `.worker-venv`，優先檢查既有環境是否已可直接使用；
# 若尚未安裝完成，才會建立 virtualenv 並安裝必要套件，避免重複安裝時再次踩到
# Windows 暫存或權限問題。

[CmdletBinding()]
param(
    [string]$WorkerVenvDir = ".worker-venv",
    [string]$PythonVersion = "3.12",
    [string]$UvCacheDir = ".uv-cache",
    [string]$UvTempDir = ".uv-tmp"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

<#
.SYNOPSIS
解析可直接執行的 uv.exe 路徑。

.DESCRIPTION
優先使用目前 shell 已解析到且副檔名為 `.exe` 的 `uv`。
若目前 shell 只找到 pyenv shim 或找不到 `uv`，則退回到使用者目錄下搜尋 `uv.exe`。

.PARAMETER PreferredCommand
目前 shell 中預期可解析的 uv 指令名稱。

.OUTPUTS
[string]
回傳可直接執行的 uv.exe 完整路徑。
#>
function Resolve-UvExecutable {
    param(
        [string]$PreferredCommand = "uv"
    )

    try {
        $resolved = Get-Command $PreferredCommand -ErrorAction Stop
        if ($resolved.Path -and $resolved.Path.ToLowerInvariant().EndsWith(".exe")) {
            return $resolved.Path
        }
    }
    catch {
    }

    $pyenvUv = Join-Path $env:USERPROFILE ".pyenv\pyenv-win\versions\3.12.10\Scripts\uv.exe"
    if (Test-Path $pyenvUv) {
        return $pyenvUv
    }

    $candidates = Get-ChildItem -Path (Join-Path $env:USERPROFILE ".pyenv") -Recurse -Filter "uv.exe" -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty FullName
    if ($candidates) {
        return $candidates[0]
    }

    throw "uv.exe not found. Install uv or make sure pyenv-win exposes a working uv.exe."
}

<#
.SYNOPSIS
確認 worker virtualenv 是否已具備可用的 Marker 環境。

.DESCRIPTION
同時檢查 `marker` 與 `worker` 模組是否可被 import。
若兩者都可用，代表安裝已完成，可以直接跳過後續安裝步驟。

.PARAMETER PythonExecutable
要檢查的 Python 執行檔完整路徑。

.OUTPUTS
[bool]
若 `marker` 與 `worker` 都可 import 則回傳 True，否則回傳 False。
#>
function Test-WorkerMarkerInstalled {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PythonExecutable,

        [Parameter(Mandatory = $true)]
        [string]$RepoRoot
    )

    $env:PYTHONPATH = Join-Path $RepoRoot "apps\worker\src"
    & $PythonExecutable -c "import marker, worker" | Out-Null
    return ($LASTEXITCODE -eq 0)
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$workerVenvPath = Join-Path $repoRoot $WorkerVenvDir
$workerPython = Join-Path $workerVenvPath "Scripts\python.exe"
$uvCachePath = Join-Path $repoRoot $UvCacheDir
$uvTempPath = Join-Path $repoRoot $UvTempDir
$workerPackagePath = Join-Path $repoRoot "apps\worker"
$uvExe = Resolve-UvExecutable

if (-not (Test-Path $workerPython)) {
    & $uvExe venv $workerVenvPath --python $PythonVersion
}

if (Test-Path $workerPython) {
    if (Test-WorkerMarkerInstalled -PythonExecutable $workerPython -RepoRoot $repoRoot) {
        Write-Host "Install skipped: worker marker environment is already ready." -ForegroundColor Green
        Write-Host "  worker python = $workerPython"
        exit 0
    }
}

New-Item -ItemType Directory -Force -Path $uvCachePath | Out-Null
New-Item -ItemType Directory -Force -Path $uvTempPath | Out-Null

$env:UV_CACHE_DIR = $uvCachePath
$env:TEMP = $uvTempPath
$env:TMP = $uvTempPath

& $workerPython -m ensurepip --upgrade
& $workerPython -m pip install --upgrade pip
& $workerPython -m pip install -e "$workerPackagePath[dev]" 'marker-pdf>=1.9.2,<2.0.0'

Write-Host "Install completed." -ForegroundColor Green
Write-Host "  uv.exe = $uvExe"
Write-Host "  worker python = $workerPython"
Write-Host "  UV_CACHE_DIR = $uvCachePath"
Write-Host "  TEMP = $uvTempPath"
