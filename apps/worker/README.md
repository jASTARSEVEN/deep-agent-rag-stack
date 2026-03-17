# Worker Module

[繁體中文版本](README.zh-TW.md)

## Purpose

This module contains the project's Celery worker. It currently provides the minimal ingest task flow, document status transitions, and parser routing scaffolding while leaving room for future indexing expansion.

## How to Start

- Local Python run:
  - `python -m venv .venv && source .venv/bin/activate`
  - `pip install -e .[dev]`
  - `celery -A worker.celery_app.celery_app worker --loglevel=INFO`
- Local health check:
  - `python -m worker.scripts.healthcheck`
- Docker Compose:
  - `docker compose -f ../../infra/docker-compose.yml --env-file ../../.env up worker`

## Environment Variables

- `WORKER_SERVICE_NAME`
- `DATABASE_URL`
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`
- `STORAGE_BACKEND`
- `MINIO_ENDPOINT`
- `MINIO_ACCESS_KEY`
- `MINIO_SECRET_KEY`
- `MINIO_SECURE`
- `MINIO_BUCKET`
- `LOCAL_STORAGE_PATH`
- `PDF_PARSER_PROVIDER`
- `LLAMAPARSE_API_KEY`
- `LLAMAPARSE_DO_NOT_CACHE`
- `LLAMAPARSE_MERGE_CONTINUED_TABLES`
- `CHUNK_MIN_PARENT_SECTION_LENGTH`
- `CHUNK_TARGET_CHILD_SIZE`
- `CHUNK_CHILD_OVERLAP`
- `CHUNK_CONTENT_PREVIEW_LENGTH`
- `CHUNK_TXT_PARENT_GROUP_SIZE`
- `CHUNK_TABLE_PRESERVE_MAX_CHARS`
- `CHUNK_TABLE_MAX_ROWS_PER_CHILD`
- `EMBEDDING_PROVIDER`
- `EMBEDDING_MODEL`
- `EMBEDDING_DIMENSIONS`
- `OPENAI_API_KEY`

## Main Directory Structure

- `src/worker/celery_app.py`: Celery application entry point
- `src/worker/tasks`: health, ingest, and indexing task modules
- `src/worker/core`: worker settings and shared helpers
- `src/worker/db.py`: minimal DB models and session helpers used by the worker
- `src/worker/storage.py`: object storage access abstraction
- `src/worker/parsers.py`: minimal parser router
- `src/worker/scripts`: operational helper scripts

## Public Interfaces

- Celery task: `worker.tasks.health.ping`
- Celery task: `worker.tasks.ingest.process_document_ingest`
- Health check script: `python -m worker.scripts.healthcheck`

## Troubleshooting

- If the worker cannot connect to Redis, verify `CELERY_BROKER_URL`.
- If ingest tasks cannot update the database, make sure `DATABASE_URL` points to the same database used by the API.
- If the runtime cannot read document content, confirm that `MINIO_*` and `MINIO_BUCKET` match the deployment settings.
- If no tasks are registered, make sure the `worker.tasks` package is loaded by Celery.
- `TXT`, `Markdown`, `HTML`, and `PDF` files now produce SQL-first parent-child chunks.
- `PDF_PARSER_PROVIDER=local` uses LangChain PDF loading as the self-hosted fallback; `PDF_PARSER_PROVIDER=llamaparse` converts PDFs to Markdown through LlamaParse and then reuses the existing Markdown parser and chunk tree.
- `LLAMAPARSE_DO_NOT_CACHE=true` is the recommended default for enterprise documents, and `LLAMAPARSE_MERGE_CONTINUED_TABLES=false` keeps cross-page table merges opt-in.
- `document_chunks` include `structure_kind=text|table`, so table-aware results remain visible to the API and later retrieval layers.
- Text children are split by `LangChain RecursiveCharacterTextSplitter`; large tables are split by row groups with repeated headers.
- `ready` now means chunking and embeddings have been completed.
- The worker is now responsible for child-chunk embeddings.
- Agentic LlamaParse modes are not enabled in this module yet; only the standard Markdown conversion path is implemented.
- File types outside the implemented parser set still move into controlled `failed` status.
- Public retrieval APIs, rerank, and chat orchestration remain outside this module.
