FROM ubuntu:24.04
WORKDIR /app
RUN <<'SETUP'
set -eu
mkdir -p incoming photos && printf 'jpg\n' > incoming/a.jpg
SETUP
