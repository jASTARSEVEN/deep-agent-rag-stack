# Docker Assets

[English README](README.md)

## 模組目的

此目錄包含本機 Docker Compose stack 所需的容器建置定義。

## 啟動方式

- 這些 Dockerfile 是透過 `infra/docker-compose.yml` 啟動的。
- 只有在除錯容器特定問題時，才需要單獨進行手動建置。

## 環境變數

- 應用程式層級的變數是由 Compose 注入的，而非硬編碼於此。

## 主要目錄結構

- `api`：FastAPI container 映像
- `worker`：Celery worker container 映像
- `web`：React 前端 container 映像

## 對外介面

- 提供本機 Compose stack 使用的容器映像。

## 疑難排解

- 若建置失敗，請透過 `docker compose -f infra/docker-compose.yml build <service>` 單獨重新建置該服務。
