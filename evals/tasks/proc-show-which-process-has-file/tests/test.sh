#!/bin/bash
set -u
mkdir -p /logs/verifier
cd /app
cmd="$(cat /tests/command.txt)"
timeout 30 bash -c "$cmd" >/tmp/askk-stdout 2>/tmp/askk-stderr
rc=$?
prefix=''
if [ -n "$prefix" ] && [ "$rc" -eq 1 ] && [ "$(head -c ${#prefix} /tmp/askk-stderr)" = "$prefix" ]; then
  echo 1 > /logs/verifier/reward.txt
elif [ -z "$prefix" ] && [ "$rc" -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
