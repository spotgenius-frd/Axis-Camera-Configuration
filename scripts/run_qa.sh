#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
API_URL="${QA_API_URL:-http://localhost:8000}"

cd "$ROOT_DIR"

echo "==> Python compile"
python3 -m py_compile axis_bulk_config/*.py api/main.py

echo "==> Backend tests"
python3 -m unittest discover -s tests

echo "==> Frontend lint"
(cd web && npm run lint)

echo "==> Frontend build"
(cd web && npm run build)

echo "==> Runtime reachability"
curl -fsS "$API_URL/openapi.json" > /tmp/axis-camera-config-openapi.json
curl -fsS "${QA_FRONTEND_URL:-http://localhost:3000}" >/dev/null

echo "==> OpenAPI route check"
python3 scripts/check_openapi.py \
  --file /tmp/axis-camera-config-openapi.json \
  --require /api/read-config \
  --require /api/read-config/upload \
  --require /api/write-config \
  --require /api/stream-profiles/apply \
  --require /api/firmware/action \
  --require /api/firmware/upload-upgrade \
  --require /api/network-config \
  --require /api/password-change \
  --require /api/network-scan \
  --require /api/network-scan/options \
  --require /api/network-scan/onboard \
  --require /api/camera-preview

echo "==> Browser smoke"
bash scripts/browser_smoke.sh

echo "==> Live camera smoke"
python3 scripts/live_camera_smoke.py --read-only

echo "QA passed."
