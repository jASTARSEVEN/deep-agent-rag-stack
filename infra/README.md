# Infra Module

[繁體中文版本](README.zh-TW.md)

## Purpose

This module contains the local Docker Compose stack and the container build assets required to run the Documents + Retrieval Foundation stack.

## How to Start

- From the repository root:
  - `cp .env.example .env`
  - `./scripts/compose.sh up --build`
  - The wrapper script always injects the repository root `.env` and `infra/docker-compose.yml`, which prevents empty `OPENAI_API_KEY` / `COHERE_API_KEY` values when Compose is invoked from a different working directory.
  - The Compose file pins the project name to `deep-agent-rag-stack` and uses repo-standard fallback host ports (`13000/18000/18080/19000/19001/15432/16379`) so accidental omission of `--env-file` is less likely to create port drift.

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
- `EMBEDDING_*`
- `OPENAI_API_KEY`
- `RERANK_*`
- `COHERE_API_KEY`
- `LANGSMITH_*`
- `RETRIEVAL_*`
- `VITE_*`

## Main Directory Structure

- `docker-compose.yml`: local service orchestration
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
  - Postgres (Supabase): `15432`
  - Redis: `16379`

## Troubleshooting

- If you previously started the stack before the pinned project name was added, you may still have older containers such as `infra-*`. Clean them up before assuming the current stack is serving the expected ports.
- The `supabase-db` service uses the `supabase/postgres` image with built-in PGroonga for Traditional Chinese search.
- Keycloak automatically imports the `deep-agent-dev` realm, the `deep-agent-web` client, the groups mapper, and default users/groups on first startup.
- `supabase/migrations/` is mounted into `/docker-entrypoint-initdb.d` only for fresh database volumes. Existing databases still need Alembic-based upgrades until a dedicated migration runner lands.
- Current compose health checks only verify stack readiness, not complete business correctness.
- The default compose setup uses `STORAGE_BACKEND=minio`. For local test-mode verification, switch to `filesystem` and pair it with `INGEST_INLINE_MODE=true`.
- To enable Cohere rerank in compose, provide `COHERE_API_KEY` in `.env` and keep `RERANK_PROVIDER=cohere`.
