# Docker Assets

[繁體中文版本](README.zh-TW.md)

## Purpose

This directory contains the container build definitions used by the local Docker Compose stack.

## How to Start

- These Dockerfiles are built through `infra/docker-compose.yml`.
- Manual per-container builds are only needed when debugging container-specific issues.

## Environment Variables

- App-level variables are injected through Compose rather than hardcoded here.

## Main Directory Structure

- `api`: FastAPI container image
- `worker`: Celery worker container image
- `web`: React frontend container image

## Public Interfaces

- Provides container images consumed by the local Compose stack.

## Troubleshooting

- If a build fails, rebuild an individual service with `docker compose -f infra/docker-compose.yml build <service>`.
