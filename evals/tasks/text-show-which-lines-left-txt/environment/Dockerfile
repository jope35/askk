FROM ubuntu:24.04
WORKDIR /app
RUN <<'SETUP'
set -eu
printf 'a\nb\n' > left.txt && printf 'b\n' > right.txt
SETUP
