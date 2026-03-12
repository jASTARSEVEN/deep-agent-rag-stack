# Docker 資產

## 模組目的

此目錄包含本機 Docker Compose stack 會使用到的容器建置定義。

## 啟動方式

- 這些 Dockerfile 會透過 `infra/docker-compose.yml` 建置。
- 只有在除錯 container 問題時才需要手動個別建置。

## 環境變數

- `PG_JIEBA_REPO_URL`
- `PG_JIEBA_REF`
- App-level variables are injected through Compose rather than hardcoded here.

## 主要目錄結構

- `api`: FastAPI container image
- `worker`: Celery worker container image
- `web`: React frontend container image
- `postgres`: Postgres base image with future pg_jieba build hooks

## 對外介面

- 提供本機 Compose stack 使用的 container 映像。

## 疑難排解

- 若建置失敗，可用 `docker compose -f infra/docker-compose.yml build <service>` 單獨重建服務。
