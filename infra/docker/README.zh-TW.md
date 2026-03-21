# Docker Assets

[English README](README.md)

## Purpose

此目錄存放 Compose stack 使用的 container build 定義，現在也包含新的 `Caddy` reverse proxy 映像。

## How to Start

- 這些 Dockerfile 會由 `infra/docker-compose.yml` 自動建置。
- 只有在除錯特定 image 問題時，才需要手動逐一 build。

## Environment Variables

- 執行期環境變數由 Compose 注入。
- `caddy` 映像主要使用 `PUBLIC_HOST`、`TLS_ACME_EMAIL`、`TLS_ACME_STAGING`、`KEYCLOAK_EXPOSE_ADMIN`。

## Main Directory Structure

- `api`：FastAPI container 映像
- `worker`：Celery worker container 映像
- `web`：React 前端 container 映像
- `caddy`：單一入口 reverse proxy 與 TLS bootstrap 映像

## Public Interfaces

- 提供 Compose stack 使用的 container images。

## Troubleshooting

- 若 image build 失敗，可使用 `docker compose -f infra/docker-compose.yml build <service>` 單獨重建該 service。
