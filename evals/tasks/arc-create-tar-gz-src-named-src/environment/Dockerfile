FROM ubuntu:24.04
WORKDIR /app
RUN <<'SETUP'
set -eu
mkdir -p src && printf 'x\n' > src/main.c
SETUP
