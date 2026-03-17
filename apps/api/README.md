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
- SQLAlchemy ORM models and metadata

## How to Start

- Local Python run:
  - `python -m venv .venv && source .venv/bin/activate`
  - `pip install -e .[dev]`
  - (Note: `supabase/migrations/` is the schema source of truth for new environments; existing database upgrades still use Alembic until a dedicated migration runner is in place.)
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
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`
- `INGEST_INLINE_MODE`
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
- `src/app/services`: authorization, indexing, internal retrieval, and assembler services
- `langgraph.json`: LangGraph Server loader config for the built-in thread/run runtime
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

- If the API process does not start, verify that `langgraph-cli[inmem]` is installed and `langgraph.json` is present in `apps/api`.
- For local auth tests, enable `AUTH_TEST_MODE=true` and use `Bearer test::<sub>::<group1,group2>`.
- `GET /areas/{area_id}` and `GET /areas/{area_id}/access` return `404` for both unauthorized and missing resources by design to preserve `deny-by-default`.
- `AUTH_TEST_MODE=true` is commonly used together with `STORAGE_BACKEND=filesystem` and `INGEST_INLINE_MODE=true` for API tests and Playwright E2E.
- `TXT`, `Markdown`, `HTML`, and `PDF` uploads now produce SQL-first parent-child `document_chunks`.
- `PDF_PARSER_PROVIDER=local` uses `Unstructured partition_pdf(strategy="fast")` as the self-hosted fallback; `PDF_PARSER_PROVIDER=llamaparse` converts PDFs to Markdown through LlamaParse before the existing Markdown parser and chunk tree.
- `.xlsx` uploads use `unstructured.partition_xlsx`, prefer worksheet `text_as_html`, and then re-enter the existing HTML table-aware parser and chunk tree.
- `.docx` and `.pptx` uploads use `unstructured.partition_docx` / `partition_pptx`, then map Unstructured elements into the existing `text/table` block-aware parser contract.
- `LLAMAPARSE_DO_NOT_CACHE=true` is the recommended default for enterprise documents, and `LLAMAPARSE_MERGE_CONTINUED_TABLES=false` keeps cross-page table merges opt-in.
- `document_chunks` include `structure_kind=text|table` for downstream retrieval and observability.
- Text children are split with `LangChain RecursiveCharacterTextSplitter`; table children preserve whole tables or split by row groups.
- `ready` now means chunk tree, embeddings, and PGroonga-indexed retrieval content have all been written.
- This module now includes an internal retrieval foundation with SQL gate, vector recall, PGroonga FTS recall, Python-layer `RRF`, minimal rerank, and a table-aware retrieval assembler, but it is not exposed as a public HTTP route yet.
- The assembler turns reranked child chunks into chat-ready contexts and citation-ready metadata with explicit budget guardrails.
- Use `RERANK_PROVIDER=deterministic` for offline tests, or switch to `RERANK_PROVIDER=cohere` and provide `COHERE_API_KEY` for compose-backed retrieval ranking.
- Agentic LlamaParse modes are not enabled in this module yet; only the standard Markdown conversion path is implemented.
- Unsupported formats still move into controlled `failed`.
- Chat now runs through LangGraph Server built-in thread/run endpoints with custom auth; the retrieval pipeline remains SQL-gated and ready-only before the answer layer.
