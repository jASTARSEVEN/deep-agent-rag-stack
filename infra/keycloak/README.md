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
- If the `keycloak-db` volume is brand new, Keycloak creates the `deep-agent-dev` realm and the default identity dataset.
- If the `keycloak-db` volume already exists, normal restarts do not overwrite the existing realm content.
- If you change `deep-agent-dev-realm.json` and want the changes applied to an existing local environment, a simple `docker compose restart` or `up` on existing containers is not enough. You must reset Keycloak persistent data first.
- Compose pins `KC_HOSTNAME` to `http://localhost:${KEYCLOAK_PORT}` so browser-side and container-side requests use the same issuer and do not break API JWT validation.

## Environment Variables

- `KEYCLOAK_REALM`
- `KEYCLOAK_CLIENT_ID`
- `KEYCLOAK_GROUPS_CLAIM`

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

- If you already created or modified other realms, normal restarts will not reset the data back to defaults.
- If you updated `deep-agent-dev-realm.json`, you must delete the `keycloak-db` volume and restart Keycloak for the new realm settings, users, or mappers to take effect.
- Prefer resetting only the Keycloak-specific volume to avoid wiping unrelated service data:

```bash
docker compose -f infra/docker-compose.yml --env-file .env down
docker volume rm deep-agent-rag-stack_keycloak-db-data
docker compose -f infra/docker-compose.yml --env-file .env up --build -d keycloak-db keycloak
```

- If the frontend callback shows a "cannot validate access token" error, rebuild the Keycloak container with the latest `KC_HOSTNAME` setting, sign in again, and clear stale tokens from `sessionStorage` if needed.

- Use `down -v` only when you intentionally want to rebuild the entire development stack:

```bash
docker compose -f infra/docker-compose.yml --env-file .env down -v
docker compose -f infra/docker-compose.yml --env-file .env up --build
```

- API JWT validation currently assumes a stable `groups` claim exists in the access token. If the token is missing `groups`, verify that the `groups` protocol mapper still exists in `deep-agent-dev-realm.json`.
