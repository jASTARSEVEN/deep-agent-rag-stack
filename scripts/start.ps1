#!/usr/bin/env pwsh
# 啟動 Windows 本地 worker。
# 目的：保留既有 start-worker-marker.ps1 入口，但實際改為 OpenDataLoader worker
# 啟動器，支援純 Compose 與 Hybrid 兩種模式。

[CmdletBinding()]
param(
    [ValidateSet("compose", "hybrid")]
    [string]$Mode = "hybrid",
    [string]$EnvFile = "",
    [string]$CeleryLogLevel = "",
    [string]$TorchDevice = "",
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$CeleryArgs = @()
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Section {
    param([string]$Message)
    Write-Host ""
    Write-Host "== $Message =="
}

function Require-Command {
    param(
        [string]$CommandName,
        [string]$InstallHint
    )

    if (-not (Get-Command $CommandName -ErrorAction SilentlyContinue)) {
        throw "找不到指令 '$CommandName'。$InstallHint"
    }
}

function Import-DotEnvFile {
    param([string]$Path)

    $values = @{}
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "找不到環境檔：$Path"
    }

    foreach ($line in Get-Content -LiteralPath $Path) {
        $trimmed = $line.Trim()
        if ([string]::IsNullOrWhiteSpace($trimmed) -or $trimmed.StartsWith("#")) {
            continue
        }

        $separatorIndex = $trimmed.IndexOf("=")
        if ($separatorIndex -lt 1) {
            continue
        }

        $key = $trimmed.Substring(0, $separatorIndex).Trim()
        $value = $trimmed.Substring($separatorIndex + 1).Trim()
        if (
            ($value.StartsWith('"') -and $value.EndsWith('"')) -or
            ($value.StartsWith("'") -and $value.EndsWith("'"))
        ) {
            $value = $value.Substring(1, $value.Length - 2)
        }

        $values[$key] = $value
    }

    return $values
}

function Get-EnvValue {
    param(
        [hashtable]$DotEnv,
        [string]$Name,
        [string]$DefaultValue = ""
    )

    $processValue = [Environment]::GetEnvironmentVariable($Name)
    if (-not [string]::IsNullOrWhiteSpace($processValue)) {
        return $processValue
    }

    if ($DotEnv.ContainsKey($Name) -and -not [string]::IsNullOrWhiteSpace([string]$DotEnv[$Name])) {
        return [string]$DotEnv[$Name]
    }

    return $DefaultValue
}

function Invoke-DockerCompose {
    param(
        [string]$RepoRoot,
        [string]$EnvFilePath,
        [string[]]$Arguments
    )

    $composeFile = Join-Path $RepoRoot "infra/docker-compose.yml"
    & docker compose --env-file $EnvFilePath -f $composeFile @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose 執行失敗。"
    }
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
$resolvedEnvFile = if ([string]::IsNullOrWhiteSpace($EnvFile)) {
    Join-Path $repoRoot ".env"
} else {
    $EnvFile
}

$resolvedWorkerVenvDir = Join-Path $repoRoot ".venv"

Require-Command -CommandName "docker" -InstallHint "請先安裝 Docker Desktop。"

$dotenv = Import-DotEnvFile -Path $resolvedEnvFile

$postgresDb = Get-EnvValue -DotEnv $dotenv -Name "POSTGRES_DB" -DefaultValue "deep_agent_rag"
$postgresUser = Get-EnvValue -DotEnv $dotenv -Name "POSTGRES_USER" -DefaultValue "app"
$postgresPassword = Get-EnvValue -DotEnv $dotenv -Name "POSTGRES_PASSWORD" -DefaultValue "app"
$postgresPort = Get-EnvValue -DotEnv $dotenv -Name "POSTGRES_PORT" -DefaultValue "15432"
$redisPort = Get-EnvValue -DotEnv $dotenv -Name "REDIS_PORT" -DefaultValue "16379"
$minioRootUser = Get-EnvValue -DotEnv $dotenv -Name "MINIO_ROOT_USER" -DefaultValue "minio"
$minioRootPassword = Get-EnvValue -DotEnv $dotenv -Name "MINIO_ROOT_PASSWORD" -DefaultValue "minio123"
$minioPort = Get-EnvValue -DotEnv $dotenv -Name "MINIO_PORT" -DefaultValue "19000"
$minioBucket = Get-EnvValue -DotEnv $dotenv -Name "MINIO_BUCKET" -DefaultValue "documents"
$pdfParserProvider = Get-EnvValue -DotEnv $dotenv -Name "PDF_PARSER_PROVIDER" -DefaultValue "opendataloader"
$resolvedTorchDevice = if ([string]::IsNullOrWhiteSpace($TorchDevice)) {
    Get-EnvValue -DotEnv $dotenv -Name "TORCH_DEVICE" -DefaultValue "cpu"
} else {
    $TorchDevice
}
$resolvedCeleryLogLevel = if ([string]::IsNullOrWhiteSpace($CeleryLogLevel)) {
    Get-EnvValue -DotEnv $dotenv -Name "CELERY_LOGLEVEL" -DefaultValue "INFO"
} else {
    $CeleryLogLevel
}

if ($pdfParserProvider -eq "opendataloader") {
    Require-Command -CommandName "java" -InstallHint "PDF_PARSER_PROVIDER=opendataloader 需要 Java 11+。"
}

if ($Mode -eq "compose") {
    Write-Section "啟動 Compose 模式"
    Invoke-DockerCompose -RepoRoot $repoRoot -EnvFilePath $resolvedEnvFile -Arguments @("up", "-d", "worker", "--build")
    exit 0
}

Require-Command -CommandName "uv" -InstallHint "Hybrid 模式需要使用 uv 管理本機 Python 環境。"

$venvPython = Join-Path $resolvedWorkerVenvDir "Scripts/python.exe"
$venvCelery = Join-Path $resolvedWorkerVenvDir "Scripts/celery.exe"

if (-not (Test-Path -LiteralPath $venvPython) -or -not (Test-Path -LiteralPath $venvCelery)) {
    throw "找不到專案虛擬環境：$resolvedWorkerVenvDir。worker 與主專案固定共用同一個 .venv；請先執行 uv sync。"
}

if ($pdfParserProvider -eq "opendataloader") {
    & $venvPython -c "import opendataloader_pdf" *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "偵測到 PDF_PARSER_PROVIDER=opendataloader，但 $resolvedWorkerVenvDir 尚未安裝 opendataloader-pdf。請先在 repo 根目錄執行 uv sync。"
    }
}

Write-Section "啟動 Hybrid 基礎服務"
Invoke-DockerCompose -RepoRoot $repoRoot -EnvFilePath $resolvedEnvFile -Arguments @(
    "up",
    "-d",
    "supabase-db",
    "redis",
    "minio",
    "keycloak",
    "api-migrate",
    "keycloak",
    "api",
    "web",
    "caddy",
    "--build"
)

Write-Section "以本機 Windows worker 啟動 Celery"
Write-Host "DATABASE_URL=postgresql://${postgresUser}:***@127.0.0.1:${postgresPort}/${postgresDb}"
Write-Host "CELERY_BROKER_URL=redis://127.0.0.1:${redisPort}/0"
Write-Host "MINIO_ENDPOINT=http://127.0.0.1:${minioPort}"
Write-Host "PDF_PARSER_PROVIDER=$pdfParserProvider"
Write-Host "TORCH_DEVICE=$resolvedTorchDevice"
Write-Host "WORKER_VENV_DIR=$resolvedWorkerVenvDir"

Set-Location $repoRoot

$existingPythonPath = [Environment]::GetEnvironmentVariable("PYTHONPATH")
$pythonPathEntries = @((Join-Path $repoRoot "apps/worker/src"))
if (-not [string]::IsNullOrWhiteSpace($existingPythonPath)) {
    $pythonPathEntries += $existingPythonPath
}
$env:PYTHONPATH = ($pythonPathEntries -join [IO.Path]::PathSeparator)
$env:DATABASE_URL = "postgresql://${postgresUser}:${postgresPassword}@127.0.0.1:${postgresPort}/${postgresDb}"
$env:CELERY_BROKER_URL = "redis://127.0.0.1:${redisPort}/0"
$env:CELERY_RESULT_BACKEND = "redis://127.0.0.1:${redisPort}/1"
$env:STORAGE_BACKEND = Get-EnvValue -DotEnv $dotenv -Name "STORAGE_BACKEND" -DefaultValue "minio"
$env:MINIO_ENDPOINT = "http://127.0.0.1:${minioPort}"
$env:MINIO_ACCESS_KEY = Get-EnvValue -DotEnv $dotenv -Name "MINIO_ACCESS_KEY" -DefaultValue $minioRootUser
$env:MINIO_SECRET_KEY = Get-EnvValue -DotEnv $dotenv -Name "MINIO_SECRET_KEY" -DefaultValue $minioRootPassword
$env:MINIO_BUCKET = $minioBucket
$env:PDF_PARSER_PROVIDER = $pdfParserProvider
$env:TORCH_DEVICE = $resolvedTorchDevice

& $venvCelery -A worker.celery_app.celery_app worker --loglevel=$resolvedCeleryLogLevel @CeleryArgs
exit $LASTEXITCODE
