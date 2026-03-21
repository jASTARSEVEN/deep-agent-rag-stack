# Caddy reverse proxy image for single-entry HTTPS and automatic certificate management.

FROM caddy:2.10.0-alpine

RUN apk add --no-cache gettext

COPY infra/docker/caddy/Caddyfile.template /etc/caddy/Caddyfile.template
COPY infra/docker/caddy/entrypoint.sh /usr/local/bin/render-caddyfile.sh

RUN chmod +x /usr/local/bin/render-caddyfile.sh

ENTRYPOINT ["/usr/local/bin/render-caddyfile.sh"]
