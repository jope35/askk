FROM ubuntu:24.04
WORKDIR /app
RUN <<'SETUP'
set -eu
printf 'same\n' > a.txt && printf 'same\n' > b.txt
SETUP
