#!/usr/bin/env sh
set -eu

mkdir -p "${UPLOAD_DIR:-/tmp/vietsub-live/uploads}" "${OUTPUT_DIR:-/tmp/vietsub-live/outputs}"

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-10000}"
