# Web Module

[繁體中文版本](README.zh-TW.md)

## Purpose

This module contains the project's React + Tailwind frontend. It currently provides the anonymous landing page, the full Keycloak login / callback flow, and the signed-in Areas / Files management UI.

## How to Start

- Local Node run:
  - `npm install`
  - `npm run dev`
- Validate the real login flow locally:
  - Make sure Keycloak and the API are available
  - Open `http://localhost:3000` or the compose-exposed URL
  - Start login from the landing page and confirm you return to `/areas`
- Run Playwright E2E locally:
  - `npm install`
  - `npx playwright install chromium`
  - `npm run test:e2e`
- Run the real Keycloak smoke test locally:
  - Confirm the compose stack for `web`, `api`, and `keycloak` is already running
  - `npm install`
  - `npx playwright install chromium`
  - `npm run test:smoke:keycloak`
- Docker Compose:
  - `docker compose -f ../../infra/docker-compose.yml --env-file ../../.env up web`

## Environment Variables

- `VITE_APP_NAME`
- `VITE_API_BASE_URL`
- `VITE_AUTH_MODE`
- `VITE_KEYCLOAK_URL`
- `VITE_KEYCLOAK_REALM`
- `VITE_KEYCLOAK_CLIENT_ID`

## Main Directory Structure

- `src/main.tsx`: application bootstrap entry
- `src/app/App.tsx`: router and auth provider entry
- `src/auth`: Keycloak / test auth mode, session persistence, and protected-route logic
- `src/pages`: landing, callback, and Areas pages
- `src/components`: reusable UI blocks
- `src/lib`: environment and API helpers
- `tests/e2e`: Playwright E2E tests, bootstrap scripts, and local test-mode API startup helpers
- `playwright.config.ts`: Playwright runtime configuration

## Public Interfaces

- Browser route: `/`
- Browser route: `/auth/callback`
- Browser route: `/areas`
- Uses `VITE_API_BASE_URL + /health` to display API health
- Uses `VITE_API_BASE_URL + /auth/context` to establish the signed-in principal
- Uses `VITE_API_BASE_URL + /areas*` for area create/list/detail, access management, and file upload/list
- Uses `VITE_API_BASE_URL + /documents/*` and `/ingest-jobs/*` to display document status, chunk summaries, reindex, delete, and job stage
- `npm run test:e2e`: runs Playwright with the web dev server and the test-mode API for automated verification
- `npm run test:smoke:keycloak`: smoke-tests the real Keycloak / callback / logout flow against the compose stack

## Troubleshooting

- If the page shows API errors, make sure the API container is healthy and `VITE_API_BASE_URL` is correct.
- If the Areas page shows `Failed to fetch` or cannot reach the API, make sure `API_CORS_ORIGINS` includes the current frontend origin. Local defaults should include at least `http://localhost:3000` and `http://localhost:13000`.
- If callback cannot return to the frontend after login, verify the redirect URI for the Keycloak client `deep-agent-web` matches `VITE_KEYCLOAK_URL` and `VITE_KEYCLOAK_CLIENT_ID`.
- If area APIs keep returning `401`, verify the Keycloak token still contains the `groups` claim and that the API issuer / JWKS settings are correct.
- `VITE_AUTH_MODE=test` is only for Playwright and local testing. It must not be treated as evidence of a production login flow.
- `npm run test:e2e` uses test auth mode and does not validate real Keycloak issuer, callback, logout, or SSO behavior. Use `npm run test:smoke:keycloak` for that coverage.
- Files are currently integrated into the `/areas` page. Activity, chat, and citations pages are not implemented yet.
- If `npm run test:e2e` fails because the browser is missing, run `npx playwright install chromium` first.
- If `npm run test:smoke:keycloak` fails, make sure the compose stack is fully started and the `deep-agent-dev` realm still accepts `alice / alice123`.
- If E2E startup fails, confirm `python`, `uvicorn`, and the `apps/api` dependencies are available in the local shell.
