# Infra Module

[繁體中文版本](README.zh-TW.md)

## Purpose

This module contains the local Docker Compose stack and the container build assets required to run the self-hosted platform.
The current deployment model uses a single public HTTPS origin through `Caddy`, while `web`, `api`, and `keycloak` remain on the internal Docker network.

## How to Start

- From the repository root:
  - `cp .env.example .env`
  - Set `PUBLIC_HOST`, `PUBLIC_BASE_URL`, and `TLS_ACME_EMAIL`
  - Point DNS for `PUBLIC_HOST` at the deployment machine
  - Forward external `80` and `443` to the Docker host
  - `docker compose --env-file .env -f infra/docker-compose.yml up --build`
- The compose file pins the project name to `deep-agent-rag-stack`.
- The `worker` service requests GPU access by default through `WORKER_GPUS=all`.

## Environment Variables

- `PUBLIC_HOST`
- `PUBLIC_BASE_URL`
- `TLS_ACME_*`
- `KEYCLOAK_EXPOSE_ADMIN`
- `WEB_PUBLIC_URL`
- `API_PUBLIC_URL`
- `KEYCLOAK_PUBLIC_URL`
- `POSTGRES_*`
- `REDIS_PORT`
- `MINIO_*`
- `KEYCLOAK_*`
- `API_*`
- `DATABASE_URL`
- `REDIS_URL`
- `STORAGE_BACKEND`
- `LOCAL_STORAGE_PATH`
- `PDF_PARSER_PROVIDER`
- `MARKER_*`
- `LLAMAPARSE_*`
- `CELERY_*`
- `WORKER_GPUS`
- `NVIDIA_*`
- `EMBEDDING_*`
- `OPENAI_API_KEY`
- `RERANK_*`
- `COHERE_API_KEY`
- `LANGSMITH_*`
- `RETRIEVAL_*`
- `VITE_*`

## Main Directory Structure

- `docker-compose.yml`: local service orchestration
- `docker/caddy`: reverse proxy image, template, and startup renderer
- `docker/api`: API container image
- `docker/worker`: worker container image
- `docker/web`: web container image
- `keycloak`: bootstrap import assets for local realm initialization

## Public Interfaces

- Public browser entrypoint:
  - `https://<PUBLIC_HOST>/`
  - `https://<PUBLIC_HOST>/api/*`
  - `https://<PUBLIC_HOST>/auth/*`
- Public ports:
  - `443`: primary customer-facing HTTPS entrypoint
  - `80`: ACME / redirect only
- Operational host ports that may still be published for local administration:
  - MinIO API: `19000`
  - MinIO Console: `19001`
  - Postgres (Supabase): `15432`
  - Redis: `16379`

## Troubleshooting

- If certificates are not issued, verify that `PUBLIC_HOST` resolves publicly and ports `80/443` reach the Docker host.
- If login fails after the reverse proxy cutover, verify that `KEYCLOAK_PUBLIC_URL`, `KEYCLOAK_ISSUER`, `KEYCLOAK_JWKS_URL`, and the realm client redirect URIs all point to `/auth`.
- `Caddy` routes `/auth/callback` to the web app and the rest of `/auth*` to Keycloak because the frontend callback path shares the `/auth` prefix.
- `KEYCLOAK_EXPOSE_ADMIN=false` blocks `/auth/admin*` at the proxy. Set it to `true` only when you intentionally need remote admin console access.
- The compose stack no longer publishes the previous `13000/18000/18080` host ports, so direct host access to web / API / Keycloak is expected to fail.
- If the worker cannot start after GPU enablement, verify that Docker Desktop exposes the NVIDIA runtime and narrow `WORKER_GPUS` or `NVIDIA_VISIBLE_DEVICES` if needed.
- `supabase-db` uses the `supabase/postgres` image with built-in PGroonga for Traditional Chinese search.
- Compose health checks only verify service readiness, not complete business correctness.
