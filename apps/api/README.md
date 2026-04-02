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
- LangGraph Server built-in thread/run chat runtime
- An external benchmark curation CLI that converts `QASPER` / `UDA`-style datasets into the existing retrieval evaluation snapshot format
- SQLAlchemy ORM models and metadata

## How to Start

- Local Python run:
  - `python -m venv .venv && source .venv/bin/activate`
  - `pip install -e .[dev]`
  - (Note: Alembic is the single schema migration source of truth. Run `python -m app.db.migration_runner` before starting the API against a fresh or existing PostgreSQL database.)
  - `langgraph dev --config langgraph.json --host 0.0.0.0 --port 18000 --no-browser`
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
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`
- `EMBEDDING_PROVIDER`
- `EMBEDDING_MODEL`
- `EMBEDDING_DIMENSIONS`
- `OPENAI_API_KEY`
- `RERANK_PROVIDER`
- `RERANK_MODEL`
- `COHERE_API_KEY`
- `RERANK_TOP_N`
- `RERANK_MAX_CHARS_PER_DOC`
- `ASSEMBLER_MAX_CONTEXTS`
- `ASSEMBLER_MAX_CHARS_PER_CONTEXT`
- `ASSEMBLER_MAX_CHILDREN_PER_PARENT`
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
- `CHAT_PROVIDER`
- `CHAT_MODEL`
- `CHAT_MAX_OUTPUT_TOKENS`
- `CHAT_TIMEOUT_SECONDS`
- `CHAT_INCLUDE_TRACE`
- `CHAT_STREAM_CHUNK_SIZE`
- `CHAT_STREAM_DEBUG`
- `LANGGRAPH_SERVICE_PORT`
- `LANGSMITH_TRACING`
- `LANGSMITH_API_KEY`
- `LANGSMITH_PROJECT`
- `LANGSMITH_ENDPOINT`
- `LANGSMITH_WORKSPACE_ID`

## Main Directory Structure

- `src/app/main.py`: FastAPI application entry point
- `src/app/core`: settings and shared runtime helpers
- `src/app/auth`: JWT validation, principal parsing, and auth dependencies
- `src/app/chat`: Deep Agents main agent, agent tools, and LangGraph runtime glue
- `src/app/db`: SQLAlchemy models, sessions, and metadata
- `src/app/routes`: HTTP routes
- `src/app/services`: authorization, storage, task dispatch, internal retrieval, and assembler services
- `src/app/scripts`: benchmark import/export/run utilities and the external benchmark curation CLI
- `langgraph.json`: LangGraph Server loader config for the built-in thread/run runtime
- `tests`: authorization and API tests

## Public Interfaces

- `GET /`
- `GET /health`
- `GET /auth/context`
- `POST /areas`
- `GET /areas`
- `GET /areas/{area_id}`
- `PUT /areas/{area_id}`
- `DELETE /areas/{area_id}`
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

- If the API process does not start, verify that `langgraph-cli[inmem]` is installed and `langgraph.json` is present in `apps/api`.
- For local auth tests, enable `AUTH_TEST_MODE=true` and use `Bearer test::<sub>::<group1,group2>`.
- `GET /areas/{area_id}`, `PUT /areas/{area_id}`, `DELETE /areas/{area_id}`, and `GET /areas/{area_id}/access` return `404` for both unauthorized and missing resources by design to preserve `deny-by-default`.
- `AUTH_TEST_MODE=true` is commonly used together with `STORAGE_BACKEND=filesystem` for API tests; Playwright E2E should start both the API and the worker.
- Upload and reindex routes only create `documents=status=uploaded` and `ingest_jobs=status=queued`; parsing, chunking, indexing, and final status transitions are worker-owned.
- Reindex and delete still clear the document-scoped `artifacts/` prefix before the worker writes new parse artifacts.
- Area delete is a hard delete: the API first removes each document's source object and parse artifacts, then deletes the area and cascaded database rows.
- `document_chunks` include `structure_kind=text|table` for downstream retrieval and observability.
- Text children are split with `LangChain RecursiveCharacterTextSplitter`; table children preserve whole tables or split by row groups.
- `ready` now means chunk tree, embeddings, and PGroonga-indexed retrieval content have all been written.
- This module now includes an internal retrieval foundation with SQL gate, vector recall, PGroonga FTS recall, Python-layer `RRF`, minimal rerank, and a table-aware retrieval assembler, but it is not exposed as a public HTTP route yet.
- The assembler turns reranked child chunks into chat-ready contexts and citation-ready metadata with explicit budget guardrails.
- Use `RERANK_PROVIDER=deterministic` for offline tests, or switch to `RERANK_PROVIDER=cohere` and provide `COHERE_API_KEY` for compose-backed retrieval ranking.
- To fold `QASPER` / `UDA`-style datasets into the existing benchmark contract, use `python -m app.scripts.prepare_external_benchmark` and run `prepare-source`, `filter-items`, `align-spans`, `build-snapshot`, and `report` in sequence.
- Agentic LlamaParse modes are not enabled in this module yet; only the standard Markdown conversion path is implemented.
- Unsupported formats still move into controlled `failed`.
- Chat now runs through LangGraph Server built-in thread/run endpoints with custom auth; the retrieval pipeline remains SQL-gated and ready-only before the answer layer.
