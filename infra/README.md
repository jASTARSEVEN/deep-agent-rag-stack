# Infra Module

[繁體中文版本](README.zh-TW.md)

## Purpose

This module contains the local Docker Compose stack and the container build assets required to run the Areas + Documents & Ingestion MVP.

## How to Start

- From the repository root:
  - `cp .env.example .env`
  - `docker compose -f infra/docker-compose.yml --env-file .env up --build`

## Environment Variables

- `POSTGRES_*`
- `REDIS_PORT`
- `MINIO_*`
- `KEYCLOAK_*`
- `API_*`
- `DATABASE_URL`
- `REDIS_URL`
- `STORAGE_BACKEND`
- `LOCAL_STORAGE_PATH`
- `MAX_UPLOAD_SIZE_BYTES`
- `CELERY_*`
- `INGEST_INLINE_MODE`
- `VITE_*`
- `PG_JIEBA_REPO_URL`
- `PG_JIEBA_REF`

## Main Directory Structure

- `docker-compose.yml`: local service orchestration
- `docker/postgres`: Postgres base image with future `pg_jieba` build hooks
- `docker/api`: API container image
- `docker/worker`: worker container image
- `docker/web`: web container image
- `keycloak`: bootstrap import assets for local realm initialization

## Public Interfaces

- Local service ports:
  - Web: `13000`
  - API: `18000`
  - Keycloak: `18080`
  - MinIO API: `19000`
  - MinIO Console: `19001`
  - Postgres: `15432`
  - Redis: `16379`

## Troubleshooting

- `PG_JIEBA_REF` is still only a placeholder at this stage. Pin it to a fixed commit SHA before implementing FTS.
- Keycloak automatically imports the `deep-agent-dev` realm, the `deep-agent-web` client, the groups mapper, and default users/groups on first startup.
- To restore the default Keycloak identity data, remove the `keycloak-db` volume and restart the stack.
- Current compose health checks only verify stack readiness, not complete business correctness.
- The default compose setup uses `STORAGE_BACKEND=minio`. For local test-mode verification, switch to `filesystem` and pair it with `INGEST_INLINE_MODE=true`.
