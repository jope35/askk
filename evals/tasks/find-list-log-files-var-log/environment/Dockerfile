FROM ubuntu:24.04
WORKDIR /app
RUN <<'SETUP'
set -eu
mkdir -p /var/log && printf 'recent\n' > /var/log/recent.log && touch /var/log/recent.log
SETUP
