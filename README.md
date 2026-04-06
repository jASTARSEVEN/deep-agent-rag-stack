# Deep Agent RAG Stack

![Actual Dashboard Live](actual-dashboard-live.png)
![Access Modal Test](access-modal-test.png)
![Chunk-Aware Preview](chunk-aware.png)

A self-hosted, NotebookLM-style document QA platform built for enterprise constraints first.

[繁體中文版本](README.zh-TW.md)

## Purpose

Deep Agent RAG Stack is an MVP for a self-hosted knowledge assistant. The product flow is intentionally focused:

1. Sign in
2. Create a Knowledge Area
3. Upload documents
4. Run background indexing
5. Ask questions with citations inside area-scoped access boundaries

This repository is not a "chat demo first" project. It is an engineering validation of a full enterprise-ready path across authentication, authorization, document lifecycle, retrieval quality, and local reproducibility.

## Background

Most internal RAG systems fail on the operational details, not on the LLM call itself. The hard parts are:

- enforcing authorization before retrieval results return
- preventing non-ready data from leaking into chat
- combining vector recall and keyword recall without losing control of cost
- keeping the full system runnable by one team on local infrastructure

This project exists to validate those constraints in one stack: `FastAPI`, `React`, `Celery`, `PostgreSQL + pgvector + PGroonga`, `MinIO`, `Keycloak`, `LangGraph`, and `Docker Compose`.

## Project Highlights

- Security-first retrieval boundaries with `deny-by-default`, same-`404`, `JWT sub/groups`, effective-role merging, and SQL gate enforcement
- Ready-only document lifecycle: only `status=ready` documents are allowed into retrieval and chat
- Hybrid retrieval path: `SQL gate + vector recall + PGroonga FTS + RRF + rerank + assembled-context citations`
- Rerank optimization with parent-level candidate aggregation, `Header/Content` formatting, provider abstraction, bounded `RERANK_TOP_N`, bounded per-document chars, and fail-open fallback
- Table-aware ingestion and retrieval for `PDF`, `DOCX`, `PPTX`, `XLSX`, `TXT/MD`, and `HTML`
- One-page dashboard UX with area navigation, streaming chat, document drawer, access modal, and chunk-aware preview
- LangGraph + Deep Agents runtime with observable retrieval traces and tool-call visibility
- Benchmark-driven retrieval governance with a fixed baseline and explicit anti-domain-overfit rules

## Retrieval And Evaluation Flow

### Hybrid Search

The current retrieval path is not "vector search only". The mainline flow is:

1. apply SQL gate and ready-only filtering
2. run vector recall and PGroonga full-text recall
3. merge candidates with `RRF`
4. pass merged parent-level candidates into rerank
5. assemble final contexts and citations for chat

### Reranker

The reranker is an active ranking layer in production-like evaluation, not just a future placeholder.

- parent-level aggregation reduces child-level fragmentation before ranking
- rerank text is normalized into `Header:` and `Content:` fields
- providers are swappable: `self-hosted`, local `BGE`, local `Qwen`, `Cohere`, and `deterministic`
- cost is bounded by `RERANK_TOP_N` and `RERANK_MAX_CHARS_PER_DOC`
- failures are handled with fail-open fallback so auth and ready-only boundaries do not regress

### Evaluation Pipeline

Retrieval quality is measured through an internal evaluation pipeline instead of relying only on subjective answer demos.

1. build area-scoped datasets and gold source spans
2. preview `recall`, `rerank`, and `assembled` candidates
3. run benchmark profiles through the same retrieval pipeline used by the product
4. compare new runs against the fixed baseline
5. keep only improvements that survive anti-domain-overfit checks

## Current Status

The latest completed milestone is `Phase 7 — Retrieval Correctness Evaluation v1`.

The current MVP already includes:

- area management with Keycloak group-based access control
- document upload, delete, reindex, and ingest progress tracking
- chunk-aware document preview and citation navigation
- an optional fact-heavy evidence-centric child refinement path in worker chunking, currently kept off by default and excluded from the current baseline
- LangGraph-based chat runtime backed by Deep Agents
- retrieval evaluation datasets, reviewer UI, CLI runner, and baseline compare
- a single public entry model behind `Caddy` with `/`, `/api/*`, and `/auth/*`

## Benchmark Snapshot

Current benchmark scores are important to this project because retrieval quality is treated as a first-class engineering outcome, not as an afterthought.

The fixed current baseline is the `production_like_v1` snapshot from `2026-04-05`.

| Dataset | Lang | Recall@10 | nDCG@10 | MRR@10 | Role |
| --- | --- | ---: | ---: | ---: | --- |
| `dureader-robust-curated-v1-100` | `zh-TW` | `1.0000` | `0.9677` | `0.9570` | Near-ceiling Chinese sanity check |
| `msmarco-curated-v1-100` | `en` | `1.0000` | `0.9674` | `0.9550` | Near-ceiling passage matching sanity check |
| `drcd-curated-v1-100` | `zh-TW` | `0.9700` | `0.8650` | `0.8308` | Traditional Chinese rerank sentinel |
| `nq-curated-v1-100` | `en` | `0.7500` | `0.7443` | `0.7425` | Assembler pressure-test lane |
| `uda-curated-v1-pilot` | `en` | `0.8462` | `0.7333` | `0.7051` | Pilot stability set |
| `tw-insurance-rag-benchmark-v1` | `zh-TW` | `0.8667` | `0.7254` | `0.6792` | Internal domain benchmark |
| `uda-curated-v1-100` | `en` | `0.8300` | `0.6818` | `0.6340` | Same-document localization lane |
| `qasper-curated-v1-pilot` | `en` | `0.7778` | `0.5507` | `0.4844` | Pilot hard set |
| `qasper-curated-v1-100` | `en` | `0.5900` | `0.3797` | `0.3142` | Main hard external lane |

Current benchmark interpretation at the README level:

- rerank is already a real optimization layer in the current stack, not just a planned box in the pipeline; the system uses parent-level rerank with cost guardrails and traceable fallback behavior
- `QASPER 100` is still the main hard external retrieval lane
- `NQ 100` is the assembler pressure-test lane
- `DRCD 100` is the Traditional Chinese rerank sentinel
- `DuReader-robust 100` and `MS MARCO 100` are near-ceiling sanity checks

For the full benchmark analysis, see [`docs/retrieval-benchmark-strategy-analysis.md`](docs/retrieval-benchmark-strategy-analysis.md).

## How To Start

### Prerequisites

- Docker and Docker Compose
- Java `11+` if you keep the default `PDF_PARSER_PROVIDER=opendataloader`
- At least one embedding provider credential for real ingest and retrieval:
  - `SELF_HOSTED_EMBEDDING_API_KEY`, or
  - `OPENAI_API_KEY`, or
  - `OPENROUTER_API_KEY`, or
- A rerank provider credential when the configured rerank provider needs one:
  - `SELF_HOSTED_RERANK_API_KEY`, or
  - `COHERE_API_KEY`, or
- For public HTTPS deployment, a reachable `PUBLIC_HOST` and `TLS_ACME_EMAIL`

### Quick Start

1. Copy the environment template.

```bash
cp .env.example .env
```

2. Edit `.env`.

- Keep the default `localhost` URLs for local development.
- Fill the provider keys that match your chosen embedding and rerank providers.
- If you want public HTTPS instead of local `localhost`, set `PUBLIC_HOST`, `PUBLIC_BASE_URL`, `WEB_PUBLIC_URL`, `API_PUBLIC_URL`, `KEYCLOAK_PUBLIC_URL`, and `TLS_ACME_EMAIL`.

3. Start the full stack.

```bash
./scripts/compose.sh up --build
```

4. Open the local services.

- Web: `http://localhost`
- API health: `http://localhost/api/health`
- Keycloak: `http://localhost/auth`
- MinIO API: `http://localhost:19000`
- MinIO Console: `http://localhost:19001`

5. Verify the main flow.

- sign in from the web app
- create a Knowledge Area
- upload a supported document
- wait until the document becomes `ready`
- ask a question and confirm citations appear

6. Stop the stack when finished.

```bash
./scripts/compose.sh down
```

The local Keycloak development realm is imported automatically by the Compose stack.

## Environment Variables

Review these groups first:

- Public routing: `PUBLIC_HOST`, `PUBLIC_BASE_URL`, `WEB_PUBLIC_URL`, `API_PUBLIC_URL`, `KEYCLOAK_PUBLIC_URL`, `TLS_ACME_EMAIL`
- Auth: `KEYCLOAK_REALM`, `KEYCLOAK_CLIENT_ID`, `KEYCLOAK_ISSUER`, `KEYCLOAK_JWKS_URL`, `KEYCLOAK_GROUPS_CLAIM`
- Storage and infra: `POSTGRES_*`, `REDIS_URL`, `MINIO_*`, `STORAGE_BACKEND`
- Ingestion: `PDF_PARSER_PROVIDER`, `LLAMAPARSE_API_KEY`
- Retrieval: `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`, `RERANK_PROVIDER`, `RERANK_MODEL`
- Chat and observability: `CHAT_PROVIDER`, `CHAT_MODEL`, `LANGSMITH_TRACING`

Use [`.env.example`](.env.example) as the full source of truth.

## Main Directory Structure

- `apps/api`: FastAPI app, auth, RBAC, retrieval, evaluation, and LangGraph runtime glue
- `apps/worker`: Celery ingestion, parsing, chunking, embeddings, and indexing
- `apps/web`: React + Tailwind dashboard, auth flow, chat UI, files UI, and evaluation UI
- `infra`: Dockerfiles, Compose stack, Caddy, and Keycloak bootstrap
- `benchmarks`: benchmark packages and evaluation assets
- `packages/shared`: shared types and settings when needed

## Public Interfaces

Main user-facing interfaces in the current MVP:

- Web dashboard at `/`
- API health and auth context at `/api/health` and `/api/auth/context`
- Area, document, access, and evaluation APIs under `/api/*`
- Keycloak login and OIDC endpoints under `/auth/*`
- LangGraph-backed chat runtime consumed by the web app through the API service

Long-lived project documents:

- Product scope: [`Summary.md`](Summary.md)
- Current implementation status: [`PROJECT_STATUS.md`](PROJECT_STATUS.md)
- Milestones and sequencing: [`ROADMAP.md`](ROADMAP.md)
- System design: [`ARCHITECTURE.md`](ARCHITECTURE.md)

## Troubleshooting

- If `./scripts/compose.sh` fails immediately, make sure `.env` exists at the repository root.
- If PDF parsing fails with `opendataloader`, verify `java -version` reports Java `11+`.
- If login fails, re-check `KEYCLOAK_PUBLIC_URL`, `VITE_KEYCLOAK_URL`, and `PUBLIC_BASE_URL`.
- If retrieval fails on an existing database, rerun:

```bash
./scripts/compose.sh exec api python -m app.db.migration_runner
```

- If answers are empty or poor, verify that your embedding and rerank provider keys match the configured providers in `.env`.

## Contact

- Author: Pin-Zhi Zhuo
- Email: `easypinex@gmail.com`
- GitHub: [easypinex/deep-agent-rag-stack](https://github.com/easypinex/deep-agent-rag-stack)

## License

Licensed under `Apache-2.0`. See [LICENSE](LICENSE).
