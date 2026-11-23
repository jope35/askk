FROM ubuntu:24.04
WORKDIR /app
RUN <<'SETUP'
set -eu
apt-get update -qq && apt-get install -y -qq --no-install-recommends rsync && mkdir -p data && printf 'x\n' > data/a.txt
SETUP
