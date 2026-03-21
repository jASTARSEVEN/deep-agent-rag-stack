# 專案層級說明：
# 這支腳本用於 Windows PowerShell 的 hybrid Marker worker 啟動流程。
# 它會先讀取 repo 根目錄 `.env`、啟動 Docker Compose 依賴服務，
# 再以 `.worker-venv` 啟動本機 Celery worker，讓 Windows 行為對齊 `start-hybrid-worker.sh`。

[CmdletBinding()]
param(
    [string]$WorkerVenvDir = ".worker-venv",
    [string]$LogLevel = "INFO",
    [string]$MarkerModelCacheDir = ".marker-cache\models",
    [switch]$SkipCompose
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

<#
.SYNOPSIS
確認指定 Python 環境中是否已安裝 marker 模組。

.DESCRIPTION
透過 `importlib.util.find_spec("marker")` 驗證 worker virtualenv 是否具備 Marker。
若沒有安裝 Marker，就在啟動前明確失敗，避免 worker 啟動後才暴露錯誤。

.PARAMETER PythonExecutable
要檢查的 Python 執行檔完整路徑。

.OUTPUTS
[bool]
若已安裝 marker 模組則回傳 True，否則回傳 False。
#>
function Test-MarkerModule {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PythonExecutable
    )

    & $PythonExecutable -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('marker') else 1)" | Out-Null
    return ($LASTEXITCODE -eq 0)
}

<#
.SYNOPSIS
從 `.env` 檔載入環境變數到目前 PowerShell process。

.DESCRIPTION
忽略空白行與註解行，保留 `KEY=VALUE` 的簡單格式。

.PARAMETER EnvFilePath
要讀取的 `.env` 完整路徑。

.OUTPUTS
[void]
#>
function Import-EnvFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$EnvFilePath
    )

    Get-Content $EnvFilePath | ForEach-Object {
        if ($_ -match '^\s*#' -or $_ -match '^\s*$') {
            return
        }

        $parts = $_ -split '=', 2
        if ($parts.Length -eq 2) {
            [System.Environment]::SetEnvironmentVariable($parts[0], $parts[1], 'Process')
        }
    }
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$workerVenvPath = Join-Path $repoRoot $WorkerVenvDir
$workerPython = Join-Path $workerVenvPath "Scripts\python.exe"
$workerCelery = Join-Path $workerVenvPath "Scripts\celery.exe"
$markerCachePath = Join-Path $repoRoot $MarkerModelCacheDir
$envFile = Join-Path $repoRoot ".env"
$composeFile = Join-Path $repoRoot "infra\docker-compose.yml"

if (-not (Test-Path $workerPython) -or -not (Test-Path $workerCelery)) {
    throw "Worker virtualenv not found. Run scripts\\install-worker-marker.ps1 first."
}

if (-not (Test-MarkerModule -PythonExecutable $workerPython)) {
    throw "marker-pdf is not installed in the worker virtualenv. Run scripts\\install-worker-marker.ps1 first."
}

if (Test-Path $envFile) {
    Import-EnvFile -EnvFilePath $envFile
}

New-Item -ItemType Directory -Force -Path $markerCachePath | Out-Null

$postgresDb = if ($env:POSTGRES_DB) { $env:POSTGRES_DB } else { "deep_agent_rag" }
$postgresUser = if ($env:POSTGRES_USER) { $env:POSTGRES_USER } else { "app" }
$postgresPassword = if ($env:POSTGRES_PASSWORD) { $env:POSTGRES_PASSWORD } else { "app" }
$postgresPort = if ($env:POSTGRES_PORT) { $env:POSTGRES_PORT } else { "15432" }
$redisPort = if ($env:REDIS_PORT) { $env:REDIS_PORT } else { "16379" }
$minioRootUser = if ($env:MINIO_ROOT_USER) { $env:MINIO_ROOT_USER } else { "minio" }
$minioRootPassword = if ($env:MINIO_ROOT_PASSWORD) { $env:MINIO_ROOT_PASSWORD } else { "minio123" }
$minioPort = if ($env:MINIO_PORT) { $env:MINIO_PORT } else { "19000" }
$minioBucket = if ($env:MINIO_BUCKET) { $env:MINIO_BUCKET } else { "documents" }

$env:PYTHONPATH = Join-Path $repoRoot "apps\worker\src"
$env:PDF_PARSER_PROVIDER = "marker"
$env:MARKER_MODEL_CACHE_DIR = $markerCachePath
$env:DATABASE_URL = "postgresql://$postgresUser`:$postgresPassword@127.0.0.1:$postgresPort/$postgresDb"
$env:CELERY_BROKER_URL = "redis://127.0.0.1:$redisPort/0"
$env:CELERY_RESULT_BACKEND = "redis://127.0.0.1:$redisPort/1"
$env:MINIO_ENDPOINT = "http://127.0.0.1:$minioPort"
$env:MINIO_ACCESS_KEY = if ($env:MINIO_ACCESS_KEY) { $env:MINIO_ACCESS_KEY } else { $minioRootUser }
$env:MINIO_SECRET_KEY = if ($env:MINIO_SECRET_KEY) { $env:MINIO_SECRET_KEY } else { $minioRootPassword }
$env:MINIO_BUCKET = $minioBucket

if (-not $SkipCompose) {
    Write-Host "Starting compose dependencies..." -ForegroundColor Green
    & docker compose --env-file $envFile -f $composeFile up -d supabase-db redis minio keycloak api-migrate api web caddy --build
}

Write-Host "Starting Marker worker..." -ForegroundColor Green
Write-Host "  worker python = $workerPython"
Write-Host "  worker celery = $workerCelery"
Write-Host "  PDF_PARSER_PROVIDER = $env:PDF_PARSER_PROVIDER"
Write-Host "  MARKER_MODEL_CACHE_DIR = $env:MARKER_MODEL_CACHE_DIR"
Write-Host "  DATABASE_URL = postgresql://$postgresUser`:***@127.0.0.1:$postgresPort/$postgresDb"
Write-Host "  CELERY_BROKER_URL = redis://127.0.0.1:$redisPort/0"
Write-Host "  MINIO_ENDPOINT = http://127.0.0.1:$minioPort"

& $workerCelery -A worker.celery_app.celery_app worker --loglevel=$LogLevel
