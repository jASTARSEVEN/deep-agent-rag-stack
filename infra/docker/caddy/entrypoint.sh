#!/bin/sh
# Render the runtime Caddyfile from environment variables before starting Caddy.

set -eu

if [ "${TLS_ACME_STAGING:-false}" = "true" ]; then
  CADDY_ACME_CA_LINE='acme_ca https://acme-staging-v02.api.letsencrypt.org/directory'
else
  CADDY_ACME_CA_LINE=''
fi

if [ "${KEYCLOAK_EXPOSE_ADMIN:-false}" = "true" ]; then
  CADDY_KEYCLOAK_ADMIN_HANDLE=''
else
  CADDY_KEYCLOAK_ADMIN_HANDLE='handle /auth/admin* {|respond 404|}'
fi

export CADDY_ACME_CA_LINE
export CADDY_KEYCLOAK_ADMIN_HANDLE

envsubst < /etc/caddy/Caddyfile.template | tr '|' '\n' > /etc/caddy/Caddyfile

exec caddy run --config /etc/caddy/Caddyfile --adapter caddyfile
