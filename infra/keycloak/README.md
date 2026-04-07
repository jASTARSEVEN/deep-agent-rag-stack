# Keycloak Bootstrap Assets

[繁體中文版本](README.zh-TW.md)

## Purpose

This directory stores the Keycloak realm import assets used for local development so the stack can boot with stable identity test data on first startup.

## How to Start

- Run from the repository root:

```bash
cp .env.example .env
docker compose -f infra/docker-compose.yml --env-file .env up --build
```

- The `keycloak` service reads the realm JSON from `/opt/keycloak/data/import` at startup.
- On the current single-entry deployment, Keycloak is published externally through `https://<PUBLIC_HOST>/auth`.
- The compose runtime pins `KC_HTTP_RELATIVE_PATH=/auth` and derives the public `/auth` URL from `PUBLIC_BASE_URL` so browser-side URLs, issuer metadata, and API JWT validation stay aligned.
- If you change `deep-agent-dev-realm.json` and want the changes applied to an existing local environment, a simple restart is not enough. You must reset Keycloak persistent data first.

## Environment Variables

- `KEYCLOAK_REALM`
- `KEYCLOAK_CLIENT_ID`
- `KEYCLOAK_GROUPS_CLAIM`
- `PUBLIC_BASE_URL`
- `KEYCLOAK_EXPOSE_ADMIN`

## Main Directory Structure

- `deep-agent-dev-realm.json`: local development realm import asset

## Default Identity Data

- realm: `deep-agent-dev`
- client: `deep-agent-web`
- groups claim: `groups`
- groups:
  - `/dept/hr`
  - `/dept/finance`
  - `/dept/rd`
  - `/platform/knowledge-admins`
- users:
  - `alice / alice123`: `/dept/hr`
  - `bob / bob123`: `/dept/finance`
  - `carol / carol123`: `/dept/rd`
  - `dave / dave123`: no groups, used to validate `deny-by-default`
  - `erin / erin123`: `/dept/hr` + `/dept/rd`
  - `frank / frank123`: `/platform/knowledge-admins`

## Redirect and Origin Rules

- Browser-facing Keycloak URLs must use `/auth`.
- The frontend callback URI is `<PUBLIC_BASE_URL>/auth/callback`.
- Silent SSO uses `<PUBLIC_BASE_URL>/silent-check-sso.html`.
- Realm client redirect URIs must explicitly allow both the callback URI and the silent SSO URI.
- `webOrigins` should allow the public web origin `<PUBLIC_BASE_URL>`.

## Group Design Principles

- A Keycloak `group` represents an organizational or functional identity and does not directly equal an area role.
- Area-level `reader`, `maintainer`, and `admin` permissions should be mapped from `group path` to the corresponding role in the API data layer.
- Local development intentionally uses only a small set of department groups to validate:
  - the same group mapping to different roles in different areas
  - multi-group users taking the maximum value between direct role and group role
  - group-less users still being blocked by `deny-by-default`

## Public Interfaces

- `infra/docker-compose.yml` mounts the realm import JSON in this directory into Keycloak's import path.

## Troubleshooting

- If you updated `deep-agent-dev-realm.json`, you must reset Keycloak persistent data before the new realm settings, users, mappers, redirect URIs, or web origins take effect.
- If browser login shows `invalid_redirect_uri`, first verify that the realm client includes both `/auth/callback` and `/silent-check-sso.html`.
- If the frontend callback shows an access token validation error, verify that `PUBLIC_BASE_URL` is correct and that the realm still uses the same `/auth`-scoped public origin for its issuer metadata and redirect URIs.
- `KEYCLOAK_EXPOSE_ADMIN=false` intentionally blocks `/auth/admin*` at the proxy. Set it to `true` only when you explicitly want remote admin console access.
