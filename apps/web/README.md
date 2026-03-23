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
  - Open `http://localhost:3000` for local Node dev, or `https://<PUBLIC_HOST>` for the compose-backed public entry
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
- `WEB_ALLOWED_HOSTS`

## Main Directory Structure

- `src/main.tsx`: application bootstrap entry
- `src/app/App.tsx`: router and auth provider entry
- `src/auth`: Keycloak / test auth mode, session persistence, and protected-route logic
- `src/pages`: landing, callback, and Areas pages
- `src/features/chat`: LangGraph SDK transport, chat state, and chat/debug UI
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
- Uses `VITE_API_BASE_URL + /areas*` for area create/list/detail/update/delete, access management, and file upload/list
- Uses `VITE_API_BASE_URL + /documents/*` and `/ingest-jobs/*` to display document status, chunk summaries, reindex, delete, and job stage
- `npm run test:e2e`: runs Playwright with the web dev server and the test-mode API for automated verification
- `npm run test:smoke:keycloak`: smoke-tests the real Keycloak / callback / logout flow against the compose stack

## Troubleshooting

- If the page shows API errors, make sure the API container is healthy and `VITE_API_BASE_URL` is correct.
- If the Areas page shows `Failed to fetch` or cannot reach the API, make sure `API_CORS_ORIGINS` includes the current frontend origin. The compose default is the public `https://<PUBLIC_HOST>` origin; local Node dev should explicitly allow `http://localhost:3000`.
- If callback cannot return to the frontend after login, verify the redirect URI for the Keycloak client `deep-agent-web` matches `VITE_KEYCLOAK_URL` and `VITE_KEYCLOAK_CLIENT_ID`.
- If Vite shows `Blocked request. This host is not allowed.`, add the public hostname to `WEB_ALLOWED_HOSTS` so the dev server accepts the incoming Host header.
- If the browser warns that Web Crypto is unavailable and PKCE was disabled, use `https://<PUBLIC_HOST>` or `http://localhost` instead of a non-secure custom host so Keycloak can keep PKCE enabled.
- If area APIs keep returning `401`, verify the Keycloak token still contains the `groups` claim and that the API issuer / JWKS settings are correct.
- `VITE_AUTH_MODE=test` is only for Playwright and local testing. It must not be treated as evidence of a production login flow.
- `npm run test:e2e` uses test auth mode and does not validate real Keycloak issuer, callback, logout, or SSO behavior. Use `npm run test:smoke:keycloak` for that coverage.
- Files remain integrated into `/areas`; chat is mounted there through `src/features/chat`. Chat uses LangGraph SDK default thread/run endpoints, consumes Deep Agents task progress, and shows assembled contexts rather than child-level citations.
- Admins can now edit area name/description and hard-delete areas from the dashboard header; deleting an area also removes its document assets server-side.
- If `npm run test:e2e` fails because the browser is missing, run `npx playwright install chromium` first.
- If `npm run test:smoke:keycloak` fails, make sure the compose stack is fully started and the `deep-agent-dev` realm still accepts `alice / alice123`.
- If E2E startup fails, confirm `python`, `uvicorn`, and the `apps/api` dependencies are available in the local shell.
