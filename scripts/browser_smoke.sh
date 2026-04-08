#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${QA_FRONTEND_URL:-http://localhost:3000}"
export CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
PWCLI="${PWCLI:-$CODEX_HOME/skills/playwright/scripts/playwright_cli.sh}"
SESSION="${PLAYWRIGHT_CLI_SESSION:-accqa}"

if [[ ! -f "$PWCLI" ]]; then
  echo "Playwright CLI wrapper not found at $PWCLI" >&2
  exit 1
fi

pwcli() {
  bash "$PWCLI" "$@"
}

cleanup() {
  pwcli --session "$SESSION" close >/dev/null 2>&1 || true
}
trap cleanup EXIT

snapshot_text() {
  pwcli --session "$SESSION" snapshot
}

click_tab_by_text() {
  local label="$1"
  local snapshot
  local ref
  snapshot="$(snapshot_text)"
  ref="$(grep -F "tab \"$label\"" <<<"$snapshot" | sed -E 's/.*\[ref=(e[0-9]+)\].*/\1/' | head -n 1)"
  if [[ -z "$ref" ]]; then
    echo "Unable to find tab ref for $label" >&2
    exit 1
  fi
  pwcli --session "$SESSION" click "$ref" >/dev/null
}

pwcli --session "$SESSION" open "$BASE_URL"
SNAPSHOT="$(snapshot_text)"
grep -q "Input workspace" <<<"$SNAPSHOT"

click_tab_by_text "Upload"
SNAPSHOT="$(snapshot_text)"
grep -Eq "Upload CSV / Excel|Drop a file here or click to browse" <<<"$SNAPSHOT"

click_tab_by_text "Scan"
SNAPSHOT="$(snapshot_text)"
grep -Eq "Scan network|Discovered devices" <<<"$SNAPSHOT"

click_tab_by_text "Manual"
SNAPSHOT="$(snapshot_text)"
grep -Eq "Manual entry|Add camera" <<<"$SNAPSHOT"

echo "Browser smoke passed."
