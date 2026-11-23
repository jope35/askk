FROM ubuntu:24.04
WORKDIR /app
RUN <<'SETUP'
set -eu
mkdir -p bin && printf '#!/bin/sh\n' > bin/run && chmod +x bin/run
SETUP
