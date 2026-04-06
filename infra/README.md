# Infra Module

[繁體中文版本](README.zh-TW.md)

## Purpose

This module contains the local Docker Compose stack and the container build assets required to run the self-hosted platform.
The current deployment model uses a single public HTTPS origin through `Caddy`, while `web`, `api`, and `keycloak` remain on the internal Docker network.

## How to Start

- From the repository root:
  - `cp .env.example .env`
  - For local development, keep the default `PUBLIC_HOST=localhost`
  - For public deployment, set `PUBLIC_HOST`, `PUBLIC_BASE_URL`, and `TLS_ACME_EMAIL`
  - If you enable local Hugging Face providers, set `API_INSTALL_OPTIONAL_GROUPS=local-huggingface`; when worker embeddings also use Hugging Face, set `WORKER_INSTALL_OPTIONAL_GROUPS=local-huggingface`
  - For public deployment, point DNS for `PUBLIC_HOST` at the deployment machine
  - For public deployment, forward external `80` and `443` to the Docker host
  - `docker compose --env-file .env -f infra/docker-compose.yml up --build`
- The compose file pins the project name to `deep-agent-rag-stack`.
- The `worker` service now starts in CPU-safe mode by default and no longer requests Docker GPU devices automatically.

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
- `OPENDATALOADER_*`
- `LLAMAPARSE_*`
- `CELERY_*`
- `NVIDIA_*`
- `API_INSTALL_OPTIONAL_GROUPS`
- `WORKER_INSTALL_OPTIONAL_GROUPS`
- `EMBEDDING_*`
- `OPENAI_API_KEY`
- `RERANK_*`
- `COHERE_API_KEY`
- `SELF_HOSTED_EMBEDDING_*`
- `SELF_HOSTED_RERANK_*`
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
  - Local development: `http://localhost/`, `http://localhost/api/*`, `http://localhost/auth/*`
  - Public deployment: `https://<PUBLIC_HOST>/`, `https://<PUBLIC_HOST>/api/*`, `https://<PUBLIC_HOST>/auth/*`
- Public ports:
  - Local development: `80`
  - Public deployment: `443` primary HTTPS, `80` ACME / redirect
- Operational host ports that may still be published for local administration:
  - MinIO API: `19000`
  - MinIO Console: `19001`
  - Postgres (Supabase): `15432`
  - Redis: `16379`

## Troubleshooting

- When `PUBLIC_HOST=localhost` or `127.0.0.1`, Caddy intentionally serves plain HTTP so local development does not depend on ACME certificates.
- If certificates are not issued, verify that `PUBLIC_HOST` resolves publicly and ports `80/443` reach the Docker host.
- If login fails after the reverse proxy cutover, verify that `KEYCLOAK_PUBLIC_URL`, `KEYCLOAK_ISSUER`, `KEYCLOAK_JWKS_URL`, and the realm client redirect URIs all point to `/auth`.
- `Caddy` routes `/auth/callback` to the web app and the rest of `/auth*` to Keycloak because the frontend callback path shares the `/auth` prefix.
- `KEYCLOAK_EXPOSE_ADMIN=false` blocks `/auth/admin*` at the proxy. Set it to `true` only when you intentionally need remote admin console access.
- The compose stack no longer publishes the previous `13000/18000/18080` host ports, so direct host access to web / API / Keycloak is expected to fail.
- If you need GPU acceleration, add Docker GPU runtime settings explicitly for your environment before starting the worker. The default Compose path intentionally avoids requesting GPU devices.
- The default API / worker images do not install optional local Hugging Face dependencies. If you switch to `EMBEDDING_PROVIDER=huggingface` or `RERANK_PROVIDER=huggingface`, rebuild with `API_INSTALL_OPTIONAL_GROUPS=local-huggingface` and, for worker-side embeddings, `WORKER_INSTALL_OPTIONAL_GROUPS=local-huggingface`.
- `supabase-db` uses the `supabase/postgres` image with built-in PGroonga for Traditional Chinese search.
- Compose health checks only verify service readiness, not complete business correctness.
