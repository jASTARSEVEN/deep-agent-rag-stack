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

## Main Directory Structure

- `src/worker/celery_app.py`: Celery application entry point
- `src/worker/tasks`: health and ingest task modules
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
- File types other than `TXT/MD` currently move into controlled `failed` status by design for the Phase 3 MVP.
- Chunking, embeddings, FTS preparation, and retrieval indexing are not implemented in this module yet.
