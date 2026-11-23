FROM ubuntu:24.04
WORKDIR /app
RUN <<'SETUP'
set -eu
mkdir -p /var/log/nginx && touch /var/log/nginx/access.log && chmod 700 /var/log/nginx
SETUP
