#!/usr/bin/env bash
set -euo pipefail
# read WEBHOOK_AUTH_TOKEN from .env and export it for this shell
if grep -q '^WEBHOOK_AUTH_TOKEN=' .env; then
  export WEBHOOK_AUTH_TOKEN="$(grep -m1 '^WEBHOOK_AUTH_TOKEN=' .env | cut -d= -f2-)"
else
  echo "ERROR: WEBHOOK_AUTH_TOKEN not found in .env" >&2
  exit 1
fi
echo "SHELL WEBHOOK_AUTH_TOKEN = [$WEBHOOK_AUTH_TOKEN]"
