FROM ubuntu:24.04
WORKDIR /app
RUN <<'SETUP'
set -eu
mkdir -p /var/log && touch -d '40 days ago' /var/log/old.log
SETUP
