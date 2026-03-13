# API Module

[繁體中文版本](README.zh-TW.md)

## Purpose

This module contains the project's FastAPI service. It currently provides:
- Minimal landing and health routes
- JWT / Keycloak authentication scaffolding
- `sub` / `groups` claim parsing
- A minimal Knowledge Area create/list/detail slice
- Area access management APIs
- An area access-check verification slice
- Document upload / list / detail APIs
- Ingest job detail APIs
- SQLAlchemy and Alembic migration scaffolding

## How to Start

- Local Python run:
  - `python -m venv .venv && source .venv/bin/activate`
  - `pip install -e .[dev]`
  - `alembic upgrade head`
  - `uvicorn app.main:app --app-dir src --reload --host 0.0.0.0 --port 18000`
- Run tests locally:
  - `pytest`
- Docker Compose:
  - `docker compose -f ../../infra/docker-compose.yml --env-file ../../.env up api`

## Environment Variables

- `API_SERVICE_NAME`
- `API_VERSION`
- `API_HOST`
- `API_PORT`
- `API_CORS_ORIGINS`
- `DATABASE_URL`
- `DATABASE_ECHO`
- `REDIS_URL`
- `STORAGE_BACKEND`
- `MINIO_ENDPOINT`
- `MINIO_ACCESS_KEY`
- `MINIO_SECRET_KEY`
- `MINIO_SECURE`
- `MINIO_BUCKET`
- `LOCAL_STORAGE_PATH`
- `MAX_UPLOAD_SIZE_BYTES`
- `CHUNK_MIN_PARENT_SECTION_LENGTH`
- `CHUNK_TARGET_CHILD_SIZE`
- `CHUNK_CHILD_OVERLAP`
- `CHUNK_CONTENT_PREVIEW_LENGTH`
- `CHUNK_TXT_PARENT_GROUP_SIZE`
- `CHUNK_TABLE_PRESERVE_MAX_CHARS`
- `CHUNK_TABLE_MAX_ROWS_PER_CHILD`
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`
- `INGEST_INLINE_MODE`
- `EMBEDDING_PROVIDER`
- `EMBEDDING_MODEL`
- `EMBEDDING_DIMENSIONS`
- `OPENAI_API_KEY`
- `TEXT_SEARCH_CONFIG`
- `RETRIEVAL_VECTOR_TOP_K`
- `RETRIEVAL_FTS_TOP_K`
- `RETRIEVAL_MAX_CANDIDATES`
- `RETRIEVAL_RRF_K`
- `RETRIEVAL_HNSW_EF_SEARCH`
- `KEYCLOAK_URL`
- `KEYCLOAK_ISSUER`
- `KEYCLOAK_JWKS_URL`
- `KEYCLOAK_GROUPS_CLAIM`
- `AUTH_TEST_MODE`

## Main Directory Structure

- `src/app/main.py`: FastAPI application entry point
- `src/app/core`: settings and shared runtime helpers
- `src/app/auth`: JWT validation, principal parsing, and auth dependencies
- `src/app/db`: SQLAlchemy models, sessions, and metadata
- `src/app/routes`: HTTP routes
- `src/app/schemas`: response schemas
- `src/app/services`: authorization, indexing, and internal retrieval services
- `alembic`: migration environment and revision scripts
- `tests`: authorization and API tests

## Public Interfaces

- `GET /`
- `GET /health`
- `GET /auth/context`
- `POST /areas`
- `GET /areas`
- `GET /areas/{area_id}`
- `GET /areas/{area_id}/access`
- `PUT /areas/{area_id}/access`
- `GET /areas/{area_id}/access-check`
- `POST /areas/{area_id}/documents`
- `GET /areas/{area_id}/documents`
- `GET /documents/{document_id}`
- `POST /documents/{document_id}/reindex`
- `DELETE /documents/{document_id}`
- `GET /ingest-jobs/{job_id}`

## Troubleshooting

- If imports fail, make sure the startup command includes `--app-dir src`.
- If `alembic upgrade head` cannot connect to the database, verify `DATABASE_URL` in the repo root `.env`.
- For local auth tests, enable `AUTH_TEST_MODE=true` and use `Bearer test::<sub>::<group1,group2>`.
- `GET /areas/{area_id}` and `GET /areas/{area_id}/access` return `404` for both unauthorized and missing resources by design to preserve `deny-by-default`.
- `AUTH_TEST_MODE=true` is commonly used together with `STORAGE_BACKEND=filesystem` and `INGEST_INLINE_MODE=true` for API tests and Playwright E2E.
- `TXT`, `Markdown`, and `HTML` uploads now produce SQL-first parent-child `document_chunks`.
- `document_chunks` include `structure_kind=text|table` for downstream retrieval and observability.
- Text children are split with `LangChain RecursiveCharacterTextSplitter`; table children preserve whole tables or split by row groups.
- `ready` now means chunk tree, embeddings, and FTS payloads have all been written.
- This module now includes an internal retrieval foundation with SQL gate, HNSW-backed vector recall, FTS recall, and `RRF` merge, but it is not exposed as a public HTTP route yet.
- Unsupported formats still move into controlled `failed`.
- Chat, citations, and rerank remain out of scope for this module's current phase.
