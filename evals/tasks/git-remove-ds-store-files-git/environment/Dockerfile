FROM ubuntu:24.04
WORKDIR /app
RUN <<'SETUP'
set -eu
apt-get update && apt-get install -y --no-install-recommends git && git config --global user.email eval@example.com && git config --global user.name Eval && mkdir -p src && printf 'line one\n' > src/main.c && git init -q && git add -A && git commit -qm one && printf 'line two\n' >> src/main.c && git commit -qam two && printf 'tracked\n' > tracked.txt && git add tracked.txt && git commit -qm tracked && printf 'secret\n' > .DS_Store && git add .DS_Store && git commit -qm store && printf 'work\n' >> src/main.c && git stash push -q && printf 'staged again\n' > staged2.txt && git add staged2.txt && git remote add origin https://example.com/repo.git
SETUP
