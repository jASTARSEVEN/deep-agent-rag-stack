# 專案層級說明：
# 這支腳本用於 Windows PowerShell 的 Marker worker GPU 安裝流程。
# 它會建立或重用 `.worker-venv`，先安裝 CUDA 版 PyTorch，再安裝 worker 與 Marker 依賴，
# 最後驗證 `torch.cuda.is_available()` 是否為 True，避免再次誤裝成 CPU 版 torch。

[CmdletBinding()]
param(
    [string]$WorkerVenvDir = ".worker-venv",
    [string]$PythonVersion = "3.12",
    [string]$UvCacheDir = ".uv-cache",
    [string]$UvTempDir = ".uv-tmp",
    [string]$TorchIndexUrl = "https://download.pytorch.org/whl/cu128",
    [string]$TorchPackage = "torch",
    [string]$TorchVisionPackage = "torchvision",
    [string]$MarkerPackageSpec = "marker-pdf>=1.9.2,<2.0.0",
    [string]$PillowVersion = "10.4.0",
    [string]$SetuptoolsVersion = "82.0.1",
    [string]$FilelockVersion = "3.25.2"
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
執行 Python 模組命令並在失敗時中止。

.DESCRIPTION
透過指定 Python 執行檔執行 `-m` 模組指令，保留引數順序，並在任一步驟失敗時拋出明確錯誤。

.PARAMETER PythonExecutable
要使用的 Python 執行檔完整路徑。

.PARAMETER ModuleName
要執行的 Python 模組名稱。

.PARAMETER Arguments
要傳給模組的其餘命令列參數。

.OUTPUTS
[void]
#>
function Invoke-PythonModule {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PythonExecutable,

        [Parameter(Mandatory = $true)]
        [string]$ModuleName,

        [string[]]$Arguments = @()
    )

    & $PythonExecutable -m $ModuleName @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed: $PythonExecutable -m $ModuleName $($Arguments -join ' ')"
    }
}

<#
.SYNOPSIS
驗證 worker GPU 環境是否已準備完成。

.DESCRIPTION
同時檢查 `marker`、`worker` 與 `torch.cuda.is_available()`。
只有當 Marker 與 worker 模組可 import，且 CUDA 已可用時，才視為 GPU 環境已準備完成。

.PARAMETER PythonExecutable
要檢查的 Python 執行檔完整路徑。

.PARAMETER RepoRoot
repo 根目錄，用來組合 `PYTHONPATH`。

.OUTPUTS
[bool]
若 Marker worker GPU 環境已可用則回傳 True，否則回傳 False。
#>
function Test-WorkerMarkerGpuReady {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PythonExecutable,

        [Parameter(Mandatory = $true)]
        [string]$RepoRoot
    )

    $env:PYTHONPATH = Join-Path $RepoRoot "apps\worker\src"
    & $PythonExecutable -c "import marker, worker, torch; raise SystemExit(0 if torch.cuda.is_available() else 1)" | Out-Null
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
    if (Test-WorkerMarkerGpuReady -PythonExecutable $workerPython -RepoRoot $repoRoot) {
        Write-Host "Install skipped: worker marker GPU environment is already ready." -ForegroundColor Green
        Write-Host "  worker python = $workerPython"
        exit 0
    }
}

New-Item -ItemType Directory -Force -Path $uvCachePath | Out-Null
New-Item -ItemType Directory -Force -Path $uvTempPath | Out-Null

$env:UV_CACHE_DIR = $uvCachePath
$env:TEMP = $uvTempPath
$env:TMP = $uvTempPath
$env:PYTHONPATH = Join-Path $repoRoot "apps\worker\src"

Invoke-PythonModule -PythonExecutable $workerPython -ModuleName "ensurepip" -Arguments @("--upgrade")
Invoke-PythonModule -PythonExecutable $workerPython -ModuleName "pip" -Arguments @("install", "--upgrade", "pip")
Invoke-PythonModule -PythonExecutable $workerPython -ModuleName "pip" -Arguments @(
    "install",
    "--no-cache-dir",
    "--force-reinstall",
    "--index-url",
    $TorchIndexUrl,
    $TorchPackage,
    $TorchVisionPackage
)
Invoke-PythonModule -PythonExecutable $workerPython -ModuleName "pip" -Arguments @(
    "install",
    "--no-cache-dir",
    "--force-reinstall",
    "-e",
    "$workerPackagePath[dev]",
    $MarkerPackageSpec
)
Invoke-PythonModule -PythonExecutable $workerPython -ModuleName "pip" -Arguments @(
    "install",
    "--no-cache-dir",
    "pillow==$PillowVersion",
    "setuptools==$SetuptoolsVersion",
    "filelock==$FilelockVersion"
)

$cudaCheckOutput = & $workerPython -c "import torch; print(torch.__version__); print(torch.version.cuda); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'None')"
if ($LASTEXITCODE -ne 0) {
    throw "GPU verification failed: unable to query torch CUDA status."
}

$cudaCheckLines = @($cudaCheckOutput)
if ($cudaCheckLines.Count -lt 3 -or $cudaCheckLines[2].ToString().Trim().ToLowerInvariant() -ne "true") {
    throw "GPU verification failed: torch CUDA is not available in $workerPython."
}

Write-Host "GPU install completed." -ForegroundColor Green
Write-Host "  uv.exe = $uvExe"
Write-Host "  worker python = $workerPython"
Write-Host "  UV_CACHE_DIR = $uvCachePath"
Write-Host "  TEMP = $uvTempPath"
Write-Host "  torch = $($cudaCheckLines[0])"
Write-Host "  cuda = $($cudaCheckLines[1])"
Write-Host "  cuda_available = $($cudaCheckLines[2])"
Write-Host "  device = $($cudaCheckLines[3])"
