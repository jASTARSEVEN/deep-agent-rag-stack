# Deep Agent RAG Stack

![Actual Dashboard Live](actual-dashboard-live.png)
![Access Modal Test](access-modal-test.png)
![Chunk Aware](chunk-aware.png)

An enterprise knowledge assistant prototype with OAuth2-based authentication, RBAC, and multi-strategy retrieval.

[繁體中文版本](README.zh-TW.md)

## Purpose

This repository is an engineering implementation project built around a self-hosted, NotebookLM-style enterprise knowledge chat application, and also serves as an experimental prototype for a multi-agent collaborative development workflow. The development process adopts multi-agent collaboration for task decomposition and implementation. The project focuses on real enterprise problems such as document upload and background processing, multi-strategy `RAG` retrieval, `Keycloak` OAuth2 integration, group-based `RBAC`, and `deny-by-default` access control for knowledge areas and documents.

The "multi-agent" part refers to the development process: task decomposition, role specialization, and collaborative implementation. It is not a user-facing product feature. The goal is not just to build a chat UI, but to validate an end-to-end knowledge system architecture that can scale toward enterprise use cases across auth, data boundaries, background jobs, and retrieval strategy.

## Why This Project

The hard part of enterprise knowledge chat is rarely just plugging in an LLM. The real challenge is organizing, authorizing, indexing, and retrieving internal documents safely while keeping quality and cost under control. This project focuses on those operational constraints to validate a knowledge system prototype that is closer to real enterprise adoption requirements.

## Future Direction

This project is not intended to stop at document Q&A. The longer-term direction is to evolve from "answering questions" into a real assistant that can understand context, call tools, and execute tasks through `Deep Agents`. The next-stage vision includes integrating `MCP`, reusable `Skill` modules, multi-step task orchestration, and external system operations so the knowledge system can participate in enterprise workflows instead of only returning information.

## What Makes This Project Different

Unlike many RAG demos that focus only on a chat interface or a single vector retrieval path, this project treats enterprise constraints as first-class design requirements from the start. That includes `Keycloak` group-based authorization, `deny-by-default`, `ready-only` document lifecycle controls, and a planned `SQL gate + vector recall + FTS recall + RRF + rerank` retrieval flow. The target is not just a system that can answer questions, but a knowledge assistant foundation that is closer to enterprise production expectations.

## Engineering Highlights

- Merges direct roles and `Keycloak groups` to compute an effective area-level `RBAC` role
- Enforces `deny-by-default` at the data access layer and uses consistent unauthorized `404` responses to avoid resource existence leaks
- Models the document lifecycle as `uploaded -> processing -> ready|failed` so incomplete data never enters retrieval
- Implements `SQL gate + vector recall + FTS recall + RRF + rerank + assembled-context citations` as the chat retrieval foundation
- Uses `Deep Agents` as the formal chat core and `LangGraph Server` built-in `thread/run` as the runtime and streaming layer
- Builds a locally reproducible vertical slice with `FastAPI + PostgreSQL + Celery + Redis + MinIO + React`

## What I Personally Owned

- Project scoping, module boundaries, and phase-by-phase implementation planning
- Authentication and authorization design, including JWT claims, group-based access, and area access management
- Local integration across API, worker, web, and Docker Compose
- Document upload and ingest state transitions, test strategy, and E2E testing foundations
- Project documentation, architecture notes, and long-term repo governance docs

## Current Status

The deployment entrypoint is now designed around a single HTTPS origin behind `Caddy`, with automatic TLS issuance and renewal for `easypinex.duckdns.org`. Public traffic is expected to use:

- `https://easypinex.duckdns.org/` for the web app
- `https://easypinex.duckdns.org/api/*` for the API
- `https://easypinex.duckdns.org/auth/*` for Keycloak

The latest completed milestone is `Phase 6.1 — Public HTTPS Entry & Migration Bootstrap Hardening`. The repository now includes a single public HTTPS entrypoint behind `Caddy`, a `/auth`-prefixed Keycloak deployment model, and a unified API-side migration runner based on Alembic.

- Monorepo structure, Docker Compose, and the local development stack
- Basic wiring across the `FastAPI` API, `Celery` worker, and `React + Tailwind` web app
- `Keycloak` OAuth2 login flow, JWT claim parsing, and auth context verification
- Area-level `RBAC` based on merged user roles and group roles
- `deny-by-default` protection for area and document access with consistent `404` behavior
- **User-friendly Access Management**: Integrated `@` mentions for users and groups with autocomplete, consistently using `username` for identification and display.
- Knowledge Area create/list/detail/access-management MVP
- Document upload, object storage, ingest job creation, and `uploaded -> processing -> ready|failed` transitions
- SQL-first `parent -> child` chunk tree generation with `structure_kind=text|table`, covering `TXT`, `Markdown`, and table-aware `HTML`
- Hybrid chunking: custom parent sectioning plus LangChain-based text child splitting, with dedicated table preserve / row-group split rules
- Ready-only retrieval foundation with SQL gate, vector recall, FTS recall, `RRF`, rerank, and table-aware context assembly
- Modernized One-Page Dashboard: A unified workspace featuring fixed sidebar navigation for Knowledge Areas, a full-height center chat as the primary workspace, and a slide-out drawer for non-interruptive file management.
- `Deep Agents` main agent plus single `retrieve_area_contexts` tool for formal chat execution
- `LangGraph Server` built-in `thread/run` runtime, custom auth injection, and streaming to the web app
- Real-time chat features including assembled-context references, tool-call tracking, and interactive debug views

## Evaluation Benchmark

This repository reports retrieval metrics against a versioned, document-grounded benchmark instead of presenting isolated demo examples. The current benchmark description below is aligned to the dataset that is actually loaded in the project database and used by the evaluation runner, rather than only to the original workbook draft.

Benchmark identity:

- Name: `tw-insurance-rag-benchmark-v1`
- Current database dataset: `tw-insurance-rag-benchmark-v1` (`bb10c343-7d7c-4ae3-b78b-a513759867f2`)
- Current area: `我的第一個知識區域`
- Evaluation profile: `production_like_v1`
- Run ID: `e2b12fa7-894f-4b94-8069-3ad4c11e44d8`
- Run date: `2026-04-01`
- Scope: retrieval correctness across `recall`, `rerank`, and `assembled` stages

Benchmark source documents:

- `個人保險保單服務暨契約變更手冊(114年9月版).pdf`
- `理賠審核原則.xlsx`
- `新契約個人保險投保規則手冊-核保及行政篇(114年9月版).pdf`
- `新契約個人保險投保規則手冊-商品篇(114年9月版).pdf`

Current database-backed dataset shape:

- `30` evaluation items
- `30` gold spans
- `4` ready documents
- `0` retrieval-miss spans
- Language distribution: `30 zh-TW`
- Query type distribution: `30 fact_lookup`

Document distribution in the current dataset:

- `理賠審核原則.xlsx`: `10` items
- `個人保險保單服務暨契約變更手冊(114年9月版).pdf`: `8` items
- `新契約個人保險投保規則手冊-商品篇(114年9月版).pdf`: `6` items
- `新契約個人保險投保規則手冊-核保及行政篇(114年9月版).pdf`: `6` items

Current summary metrics:

| Stage | nDCG@k | Recall@k | MRR@k | Precision@k | Doc Coverage@k |
| --- | ---: | ---: | ---: | ---: | ---: |
| recall | 0.602 | 0.867 | 0.526 | 0.160 | 1.000 |
| rerank | 0.813 | 0.867 | 0.794 | 0.087 | 1.000 |
| assembled | 0.813 | 0.867 | 0.794 | 0.087 | 1.000 |

Config snapshot:

- Retrieval: `vector_top_k=30`, `fts_top_k=30`, `max_candidates=30`, `rrf_k=60`, `hnsw_ef_search=100`
- Rerank: `provider=cohere`, `model=rerank-v3.5`, `top_n=30`, `max_chars_per_doc=2000`
- Assembler: `max_contexts=6`, `max_chars_per_context=2500`, `max_children_per_parent=7`
- Reported top-k: `10`

Interpretation notes:

- This benchmark is a project benchmark, not a generic public leaderboard claim.
- The current benchmark already points to `Parent_Chunk_ID` and `Child_Chunk_ID`, which makes it suitable for validating chunk assembly and citation grounding, not only answer text overlap.
- For external comparison, this benchmark should be reported together with at least one public benchmark such as `QASPER` or `UDA-Benchmark`.

Recommended public release format:

1. Export the database evaluation dataset into stable machine-readable files such as `documents.jsonl`, `questions.jsonl`, and `gold_spans.jsonl`.
2. Publish the four source documents together with that exported dataset snapshot as a small benchmark package.
3. Add a dataset card that explains document scope, question-writing rules, evidence policy, and metric definitions.
4. Publish the package on `Hugging Face Datasets` or a dedicated GitHub repository with version tags such as `v1.0.0`.
5. Keep the README metrics tied to a dataset version, a dataset snapshot export date, and a run ID so others can rerun the same benchmark.

## Not Yet Implemented

- Broader compose smoke coverage for real `Keycloak + LangGraph + Deep Agents` runtime behavior
- More end-to-end coverage for tool failure, no-context answers, and streaming edge cases
- Broader regression coverage for area-management interactions across access, documents, and chat state transitions
- Future `Deep Agents` expansion points such as sub-agents, `MCP`, and reusable `Skill` modules

## TODO / Future Additions

- Add a system architecture diagram showing the relationships among web, API, worker, DB, MinIO, Keycloak, and retrieval flow
- Add an E2E demo that shows the main flow from login to upload, processing, and access validation
- Add a testing coverage summary for authorization, state transitions, API boundaries, and E2E scope
- Add explicit permission boundary examples for different roles and groups across area / document / chat access
- Add failure-handling flow documentation for upload, ingest, unsupported file types, and authorization failures

## License

This project is licensed under `Apache-2.0`. See the root `LICENSE` file for the full text.

## Contact

- Maintainer: Pin-Chih Cho
- Email: `easypinex@gmail.com`

## Repository Structure

- `apps/api`: FastAPI API, JWT auth, RBAC, internal retrieval services, `app/chat` Deep Agents domain, and LangGraph loader/runtime glue
- `apps/worker`: Celery background jobs for ingest and status transitions
- `apps/web`: React + Tailwind frontend, modernized one-page dashboard (integrated area navigation, chat center, and file management drawers)
- `infra`: Docker Compose assets and container build definitions
- `packages/shared`: Reserved space for shared types and configuration

## How to Start

1. Copy the environment file:
   - `cp .env.example .env`
2. Optionally install local Python dependencies:
   - `python -m venv .venv && source .venv/bin/activate`
   - `pip install -e ./apps/api -e ./apps/worker`
   - Shared workspace sync: `uv sync`
   - `PDF_PARSER_PROVIDER=opendataloader` is now the default path and requires `Java 11+` on the machine running the worker.
   - OpenDataLoader follows the official `json,markdown` recommendation in this repository. The worker persists `opendataloader.json` and `opendataloader.cleaned.md`, keeps AI safety filters enabled, and enables `use_struct_tree=true` with automatic fallback when tags are missing.
3. Build and start the local stack:
   - `./scripts/compose.sh up --build`
   - The wrapper always uses the repository root `.env` and `infra/docker-compose.yml`, which prevents secrets such as `OPENAI_API_KEY` from silently becoming empty when the command is run from a different working directory.
   - The Compose project name is pinned to `deep-agent-rag-stack`, so container names stay stable and do not drift to fallback names such as `infra-*`.
4. Point `PUBLIC_HOST` DNS to the deployment host and forward external `80/443` to the Docker machine.
5. Open the public services:
   - Web: `https://easypinex.duckdns.org`
   - API health: `https://easypinex.duckdns.org/api/health`
   - Keycloak OIDC base: `https://easypinex.duckdns.org/auth`
   - MinIO API: `http://localhost:19000`
   - MinIO Console: `http://localhost:19001`

## Public Access Model

- Customers use a single public service port: `443`.
- Port `80` is reserved for ACME validation and HTTP-to-HTTPS redirect.
- Compose no longer publishes `13000`, `18000`, and `18080` to the host.
- `Caddy` terminates TLS, renews certificates automatically, and reverse proxies to `web`, `api`, and `keycloak` over the internal Docker network.
- `KEYCLOAK_EXPOSE_ADMIN=false` blocks `/auth/admin*` at the reverse proxy while keeping the login and OIDC endpoints reachable.

## Database Init and Upgrade

- The repository uses Alembic as the single schema migration source of truth.
- The compose stack upgrades both fresh and existing databases through `python -m app.db.migration_runner`.
- If you need to rerun the upgrade path manually in an existing environment, use:
  - `./scripts/compose.sh exec api python -m app.db.migration_runner`
- If retrieval SQL or PostgreSQL RPCs change, make sure the change is represented in Alembic revisions before shipping the code change.
- After an upgrade, verify the API and retrieval path before assuming the environment is healthy.

## Environment Variables

See `.env.example` for the full local default configuration. The template is grouped by variable category and includes bilingual comments.

## Verification

- API health:
  - `curl https://easypinex.duckdns.org/api/health`
- Auth context:
  - `curl -H "Authorization: Bearer <access-token>" https://easypinex.duckdns.org/api/auth/context`
- LangGraph chat runtime:
  - `cd apps/api && langgraph dev --config langgraph.json --host 0.0.0.0 --port 18000 --no-browser`
- Worker ping task:
  - `./scripts/compose.sh exec worker python -m worker.scripts.healthcheck`
- Web / Areas / Files / Chat:
  - Open `https://easypinex.duckdns.org`, sign in, and verify area listing, file upload, document status, and area-scoped chat behavior
- Phase 1 auth verification guide:
  - `docs/phase1-auth-verification.md`

## Troubleshooting

- If Docker image builds fail, confirm Docker Desktop is running and can reach package registries.
- If Keycloak starts slowly, wait until the `keycloak` health check passes before opening the UI.
- If the web app cannot reach the API, verify `VITE_API_BASE_URL` in `.env`.
- If the API starts but Deep Agents retrieval fails only on an existing database, rerun `python -m app.db.migration_runner` inside the API container and verify that the PostgreSQL schema and RPCs reached the latest Alembic head.
- If the hybrid worker runs with `PDF_PARSER_PROVIDER=opendataloader`, confirm `java -version` resolves to Java 11 or newer before starting Celery.
- Windows local worker entrypoint is available at `scripts/start-worker-marker.ps1` for compatibility. Use `-Mode compose` to start the container worker, or `-Mode hybrid` to keep infra in Compose and run Celery from the project root `.venv`. The worker now shares the same virtual environment as the main project.
