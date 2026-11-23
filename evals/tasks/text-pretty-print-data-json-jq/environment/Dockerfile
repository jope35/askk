FROM ubuntu:24.04
WORKDIR /app
RUN <<'SETUP'
set -eu
apt-get update -qq && apt-get install -y -qq --no-install-recommends jq && printf '{"items":[{"name":"a"}]}' > data.json && printf '{"version":"1.0"}' > package.json
SETUP
