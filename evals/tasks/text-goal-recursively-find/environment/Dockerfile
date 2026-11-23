FROM ubuntu:24.04
WORKDIR /app
RUN <<'SETUP'
set -eu
mkdir -p logs && printf 'error[42]\n' > logs/a.log
SETUP
