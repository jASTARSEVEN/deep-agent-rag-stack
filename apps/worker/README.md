# Worker Module

[繁體中文版本](README.zh-TW.md)

## Purpose

This module contains the project's Celery worker. It currently provides the minimal ingest task flow, document status transitions, and parser routing scaffolding while leaving room for future indexing expansion.

## How to Start

- Local Python run:
  - `python -m venv .venv && source .venv/bin/activate`
  - `pip install -e .[dev]`
  - If you need `PDF_PARSER_PROVIDER=marker`, use a dedicated worker virtualenv and install Marker there:
    `uv venv ../../.worker-venv --python 3.12 && uv pip install --python ../../.worker-venv/bin/python -e .[dev] "marker-pdf>=1.9.2,<2.0.0"`
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
- `CELERY_WORKER_POOL`
- `CELERY_WORKER_CONCURRENCY`
- `CELERY_WORKER_PREFETCH_MULTIPLIER`
- `CELERY_WORKER_MAX_TASKS_PER_CHILD`
- `CELERY_TASK_ACKS_LATE`
- `CELERY_TASK_REJECT_ON_WORKER_LOST`
- `STORAGE_BACKEND`
- `MINIO_ENDPOINT`
- `MINIO_ACCESS_KEY`
- `MINIO_SECRET_KEY`
- `MINIO_SECURE`
- `MINIO_BUCKET`
- `LOCAL_STORAGE_PATH`
- `PDF_PARSER_PROVIDER`
- `MARKER_MODEL_CACHE_DIR`
- `MARKER_FORCE_OCR`
- `MARKER_STRIP_EXISTING_OCR`
- `MARKER_USE_LLM`
- `MARKER_LLM_SERVICE`
- `MARKER_OPENAI_API_KEY`
- `MARKER_OPENAI_MODEL`
- `MARKER_OPENAI_BASE_URL`
- `MARKER_DISABLE_IMAGE_EXTRACTION`
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
- If `marker` PDF ingest fails with `Worker exited prematurely: signal 9 (SIGKILL)` in Celery logs, the usual cause is the OS killing a prefork child during a heavy PDF runtime. Compose now defaults to `CELERY_WORKER_POOL=solo`, `CELERY_WORKER_CONCURRENCY=1`, `CELERY_WORKER_PREFETCH_MULTIPLIER=1`, `CELERY_WORKER_MAX_TASKS_PER_CHILD=1`, and `CELERY_TASK_ACKS_LATE=true` so the worker keeps only one in-flight job at a time.
- `CELERY_TASK_REJECT_ON_WORKER_LOST=true` pushes an unfinished job back to the queue if the worker process dies unexpectedly, instead of letting the job disappear after it was already reserved.
- If ingest tasks cannot update the database, make sure `DATABASE_URL` points to the same database used by the API.
- If the runtime cannot read document content, confirm that `MINIO_*` and `MINIO_BUCKET` match the deployment settings.
- If no tasks are registered, make sure the `worker.tasks` package is loaded by Celery.
- `TXT`, `Markdown`, `HTML`, and `PDF` files now produce SQL-first parent-child chunks.
- `PDF_PARSER_PROVIDER=marker` is the default path. It converts PDFs to Markdown with Marker, persists only `marker.cleaned.md`, and then reuses the existing Markdown parser and chunk tree.
- `marker-pdf` is intentionally not part of the shared workspace solve because `deepagents` and Marker currently require incompatible `anthropic` versions. If you want the Marker path locally, install it into a dedicated worker virtualenv such as `../../.worker-venv`. The hybrid worker launcher can pick that environment automatically for `PDF_PARSER_PROVIDER=marker`.
- `MARKER_MODEL_CACHE_DIR` should point to a writable directory so Marker / Surya model downloads do not fail on restricted cache paths. In compose, that directory is now backed by a named volume so the model cache survives worker restarts and rebuilds.
- When `MARKER_USE_LLM=true`, the worker now forwards `MARKER_LLM_SERVICE`, `MARKER_OPENAI_API_KEY`, `MARKER_OPENAI_MODEL`, and `MARKER_OPENAI_BASE_URL` into Marker's OpenAI-compatible LLM config.
- `PDF_PARSER_PROVIDER=local` uses `Unstructured partition_pdf(strategy="fast")` as the self-hosted fallback; `PDF_PARSER_PROVIDER=llamaparse` converts PDFs to Markdown through LlamaParse and then reuses the existing Markdown parser and chunk tree.
- `.xlsx` files use `unstructured.partition_xlsx`, prefer worksheet `text_as_html`, and then reuse the existing HTML table-aware parser and chunk tree.
- `.docx` and `.pptx` files use `unstructured.partition_docx` / `partition_pptx`, then map Unstructured elements back into the existing `text/table` block-aware parser contract.
- `LLAMAPARSE_DO_NOT_CACHE=true` is the recommended default for enterprise documents, and `LLAMAPARSE_MERGE_CONTINUED_TABLES=false` keeps cross-page table merges opt-in.
- Fresh ingest runs clear the document-scoped `artifacts/` prefix before writing new parse artifacts.
- `document_chunks` include `structure_kind=text|table`, so table-aware results remain visible to the API and later retrieval layers.
- Text children are split by `LangChain RecursiveCharacterTextSplitter`; large tables are split by row groups with repeated headers.
- `ready` now means chunking and embeddings have been completed.
- The worker is now responsible for child-chunk embeddings.
- Agentic LlamaParse modes are not enabled in this module yet; only the standard Markdown conversion path is implemented.
- File types outside the implemented parser set still move into controlled `failed` status.
- Public retrieval APIs, rerank, and chat orchestration remain outside this module.
