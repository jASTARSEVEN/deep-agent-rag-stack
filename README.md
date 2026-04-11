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
- providers are swappable: `self-hosted`, local `huggingface` rerank, `Cohere`, and `deterministic`
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

The fixed current baseline started from the `production_like_v1` snapshot from `2026-04-05`; specified-document external benchmark rows are updated when their source task contract requires document context.

For `qasper-*`, `uda-*`, and `drcd-*` evaluation datasets, benchmark runs now use the gold source document as a specified-document scope. This matches those datasets' source task contracts, where each question is tied to an actual document instead of being an unscoped multi-document query.

| Dataset | Lang | Query Scope | Recall@10 | nDCG@10 | MRR@10 | Role |
| --- | --- | --- | ---: | ---: | ---: | --- |
| `dureader-robust-curated-v1-100` | `zh-TW` | `Multi-doc` | `1.0000` | `0.9677` | `0.9570` | Near-ceiling Chinese sanity check |
| `msmarco-curated-v1-100` | `en` | `Multi-doc` | `1.0000` | `0.9674` | `0.9550` | Near-ceiling passage matching sanity check |
| `drcd-curated-v1-100` | `zh-TW` | `Specified-doc` | `1.0000` | `0.8894` | `0.8517` | Specified-document Traditional Chinese rerank sentinel |
| `nq-curated-v1-100` | `en` | `Multi-doc` | `0.7600` | `0.7600` | `0.7600` | Assembler pressure-test lane |
| `tw-insurance-rag-benchmark-v1` | `zh-TW` | `Multi-doc` | `0.9333` | `0.7578` | `0.7136` | Internal domain benchmark |
| `uda-curated-v1-100` | `en` | `Specified-doc` | `0.7900` | `0.6492` | `0.6044` | Specified-document same-document localization lane |
| `qasper-curated-v1-100` | `en` | `Specified-doc` | `0.9200` | `0.6105` | `0.5127` | Specified-document scientific-paper hard lane |

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
- If you want local Hugging Face models instead of hosted embeddings / rerank:
  - set `EMBEDDING_PROVIDER=huggingface` for local `Qwen/Qwen3-Embedding-0.6B`
  - set `RERANK_PROVIDER=huggingface` for local `BAAI/bge-reranker-v2-m3`
  - install optional dependencies with `pip install -e .[dev,local-huggingface]`, or set `API_INSTALL_OPTIONAL_GROUPS=local-huggingface` and `WORKER_INSTALL_OPTIONAL_GROUPS=local-huggingface` before `docker compose build`
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
- If you use local Hugging Face models, also enable the optional dependency groups before rebuilding Compose images.
- If you want public HTTPS instead of local `localhost`, set `PUBLIC_HOST`, `PUBLIC_BASE_URL`, and `TLS_ACME_EMAIL`.

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

## Quick Start For Humans

If you only want to boot the app and try the main flow, use this section instead of reading the architecture first.

### Default Local Accounts

The local Compose stack imports a fixed Keycloak development realm on first startup.

| Username | Password | Groups | Recommended use |
| --- | --- | --- | --- |
| `alice` | `alice123` | `/dept/hr` | First interactive demo user |
| `bob` | `bob123` | `/dept/finance` | Cross-group access check |
| `carol` | `carol123` | `/dept/rd` | Another normal user |
| `dave` | `dave123` | none | `deny-by-default` check |
| `erin` | `erin123` | `/dept/hr`, `/dept/rd` | Multi-group effective-role check |
| `frank` | `frank123` | `/platform/knowledge-admins` | Platform admin-style demo user |

Notes:

- Keycloak realm: `deep-agent-dev`
- Keycloak client: `deep-agent-web`
- These users come from [`infra/keycloak/deep-agent-dev-realm.json`](infra/keycloak/deep-agent-dev-realm.json).
- If you already started Keycloak once and later changed the realm import, you must reset Keycloak persistent data before the new users take effect.

### What You Usually Do In The App

The intended happy path is:

1. Open `http://localhost`
2. Click `Use Keycloak Login`
3. Sign in with one of the accounts above
4. Open `/areas`
5. Create a new Knowledge Area if this is your first time
6. Upload a document into that area
7. Wait until the document status becomes `ready`
8. Ask a question in the chat panel and inspect the citations

What to expect after first login:

- On a fresh system, you may see no accessible areas yet. That is normal.
- The simplest first action is to create your own area.
- The creator of an area becomes that area's `admin`.
- Access to an existing area depends on area-level user or group mappings, not just on being able to log in.

### 5-Minute Demo Flow

Use `alice / alice123` for the shortest demo:

1. Start the stack with `./scripts/compose.sh up --build`
2. Open `http://localhost`
3. Log in as `alice`
4. Create an area such as `HR Policies`
5. Upload one `PDF`, `DOCX`, `TXT/MD`, `PPTX`, `HTML`, or `XLSX` file
6. Wait for the file to move from `uploaded` or `processing` to `ready`
7. Ask a concrete question that should be answerable from the file
8. Click the returned citations to inspect the source text in the preview pane

### Simple Access-Control Demo

If you want to understand the authorization model quickly:

1. Log in as `alice` and create an area
2. In the access settings, grant `/dept/hr` as `reader`
3. Log out and log in again as `bob`
4. `bob` should not see that area because `bob` belongs to `/dept/finance`
5. Log in as `dave`
6. `dave` should also be blocked because `dave` has no groups

This shows two important product rules:

- access is `deny-by-default`
- area access is controlled by direct user roles and Keycloak group-path mappings

### Which Account Should I Use?

- Use `alice` if you just want to try the app end to end.
- Use `frank` if you want a platform-admin-flavored test identity.
- Use `erin` if you want to test a user with multiple groups.
- Use `dave` if you want to verify that group-less users do not automatically gain access to protected data.

## Environment Variables

Review these groups first:

- Public routing: `PUBLIC_HOST`, `PUBLIC_BASE_URL`, `TLS_ACME_EMAIL`, `KEYCLOAK_EXPOSE_ADMIN`
- Auth: `KEYCLOAK_REALM`, `KEYCLOAK_CLIENT_ID`, `KEYCLOAK_GROUPS_CLAIM`
- Storage and infra: `POSTGRES_*`, `REDIS_PORT`, `MINIO_*`, `STORAGE_BACKEND`
- Ingestion: `PDF_PARSER_PROVIDER`, `LLAMAPARSE_API_KEY`
- Model providers: `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`, `RERANK_PROVIDER`, `RERANK_MODEL`
- Chat and observability: `CHAT_MODEL`, `LANGSMITH_TRACING`

Use [`.env.example`](.env.example) for the common Compose startup variables. For extra runtime-only overrides, see [apps/api/README.md](apps/api/README.md) and [apps/worker/README.md](apps/worker/README.md).

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
- If login fails, re-check `PUBLIC_BASE_URL` and confirm the Keycloak realm redirect URIs still point to `<PUBLIC_BASE_URL>/auth/callback` and `<PUBLIC_BASE_URL>/silent-check-sso.html`.
- If retrieval fails on an existing database, rerun:

```bash
./scripts/compose.sh exec api python -m app.db.migration_runner
```

- If answers are empty or poor, verify that your embedding and rerank provider keys match the configured providers in `.env`.
- If `EMBEDDING_PROVIDER=huggingface` or `RERANK_PROVIDER=huggingface` fails during startup, verify the optional `local-huggingface` dependencies were installed and the model can be downloaded or read from a local path.

## Contact

- Author: Pin-Zhi Zhuo
- Email: `easypinex@gmail.com`
- GitHub: [easypinex/deep-agent-rag-stack](https://github.com/easypinex/deep-agent-rag-stack)

## License

Licensed under `Apache-2.0`. See [LICENSE](LICENSE).
