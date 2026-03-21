# Docker Assets

[繁體中文版本](README.zh-TW.md)

## Purpose

This directory contains the container build definitions used by the Compose stack, including the new `Caddy` reverse proxy image.

## How to Start

- These Dockerfiles are built through `infra/docker-compose.yml`.
- Manual per-container builds are usually only needed while debugging image-specific issues.

## Environment Variables

- Runtime variables are injected through Compose.
- The `caddy` image relies on `PUBLIC_HOST`, `TLS_ACME_EMAIL`, `TLS_ACME_STAGING`, and `KEYCLOAK_EXPOSE_ADMIN`.

## Main Directory Structure

- `api`: FastAPI container image
- `worker`: Celery worker container image
- `web`: React frontend container image
- `caddy`: single-entry reverse proxy and TLS bootstrap image

## Public Interfaces

- Provides the container images consumed by the Compose stack.

## Troubleshooting

- If an image build fails, rebuild an individual service with `docker compose -f infra/docker-compose.yml build <service>`.
