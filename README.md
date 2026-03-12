# Deep Agent RAG Stack

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
- Plans a `SQL gate + vector recall + FTS recall + RRF + rerank` retrieval path that balances authorization, quality, and cost
- Builds a locally reproducible vertical slice with `FastAPI + PostgreSQL + Celery + Redis + MinIO + React`

## What I Personally Owned

- Project scoping, module boundaries, and phase-by-phase implementation planning
- Authentication and authorization design, including JWT claims, group-based access, and area access management
- Local integration across API, worker, web, and Docker Compose
- Document upload and ingest state transitions, test strategy, and E2E testing foundations
- Project documentation, architecture notes, and long-term repo governance docs

## Current Status

The initial vertical slice listed below was assembled within one day of off-hours work through a multi-agent collaborative development workflow. The point was not to maximize feature completeness in a single burst, but to test how quickly a reasonably structured enterprise knowledge system prototype could be composed when task decomposition, implementation ownership, and integration flow were explicitly coordinated.

- Monorepo structure, Docker Compose, and the local development stack
- Basic wiring across the `FastAPI` API, `Celery` worker, and `React + Tailwind` web app
- `Keycloak` OAuth2 login flow, JWT claim parsing, and auth context verification
- Area-level `RBAC` based on merged user roles and group roles
- `deny-by-default` protection for area and document access with consistent `404` behavior
- Knowledge Area create/list/detail/access-management MVP
- Document upload, object storage, ingest job creation, and `uploaded -> processing -> ready|failed` transitions
- Core Areas / Files workflows in the web app plus baseline E2E coverage

## Not Yet Implemented

- Full indexing pipeline, including chunking, embeddings, and FTS persistence
- Retrieval pipeline, including SQL gate, vector recall, FTS recall, `RRF`, and rerank
- Chat answers, citations, and the full knowledge-chat experience
- Document delete, reindex, and richer ingest / retrieval observability
- Area rename / delete and related management hardening

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

- `apps/api`: FastAPI API, JWT auth, RBAC, and services/routes for areas, documents, and ingest jobs
- `apps/worker`: Celery background jobs for ingest and status transitions
- `apps/web`: React + Tailwind frontend, login flow, and Areas / Files UI
- `infra`: Docker Compose assets and container build definitions
- `packages/shared`: Reserved space for shared types and configuration

## How to Start

1. Copy the environment file:
   - `cp .env.example .env`
2. Optionally install local Python dependencies:
   - `python -m venv .venv && source .venv/bin/activate`
   - `pip install -e ./apps/api -e ./apps/worker`
3. Build and start the local stack:
   - `docker compose -f infra/docker-compose.yml --env-file .env up --build`
4. Open the local services:
   - Web: `http://localhost:13000`
   - API: `http://localhost:18000`
   - API health: `http://localhost:18000/health`
   - Keycloak: `http://localhost:18080`
   - MinIO API: `http://localhost:19000`
   - MinIO Console: `http://localhost:19001`

## Environment Variables

See `.env.example` for the full local default configuration.

## Verification

- API health:
  - `curl http://localhost:18000/health`
- Auth context:
  - `curl -H "Authorization: Bearer <access-token>" http://localhost:18000/auth/context`
- Worker ping task:
  - `docker compose -f infra/docker-compose.yml exec worker python -m worker.scripts.healthcheck`
- Web / Areas / Files:
  - Open `http://localhost:13000`, sign in, and verify area listing, file upload, and document status behavior
- Phase 1 auth verification guide:
  - `docs/phase1-auth-verification.md`

## Troubleshooting

- If Docker image builds fail, confirm Docker Desktop is running and can reach package registries.
- If Keycloak starts slowly, wait until the `keycloak` health check passes before opening the UI.
- If the web app cannot reach the API, verify `VITE_API_BASE_URL` in `.env`.
