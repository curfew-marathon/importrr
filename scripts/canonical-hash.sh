#!/usr/bin/env bash
#
# canonical-hash.sh - guard the shared parts of start.sh / stop.sh.
#
# hivemind, importrr, uploadrr, prometheus and grafana ship a copy-pasted
# "canonical run interface". The blocks hashed below MUST be byte-identical in
# every one of them (the "# >>> project-specific" fences and the header / --help
# / .env text are allowed to differ). hivemind is the reference.
#
#   ./scripts/canonical-hash.sh          print the current hash
#   ./scripts/canonical-hash.sh --check  exit 1 if it differs from EXPECTED
#
# CI runs --check (.github/workflows/canonical-scripts.yml). To change the shared
# block: edit it in hivemind, run this script to get the new hash, set EXPECTED
# below, then copy start.sh + stop.sh + this file to the other four repos.
#
set -euo pipefail
cd "$(dirname "$0")/.."

EXPECTED=e312e9ccf4430c31fb1eb521bb17a7f1318e3b786d2976dab69613688c1fd286

canonical_blocks() {
  grep -hE '^(log|warn|err)\(\)' start.sh stop.sh || true
  sed -n '/^_has_build_services() {/,/^}/p' start.sh
  sed -n '/^wait_for_health() {/,/^}/p' start.sh
  sed -n '/^UP_ARGS=(up -d/,/^esac/p' start.sh
  sed -n '/^FIRST_PARTY=/p; /^rm_failed=0/,/^fi$/p; /^if \[ "\$rm_failed" = "1" \]/,/^fi$/p' stop.sh
}

hash="$(canonical_blocks | { command -v sha256sum >/dev/null 2>&1 && sha256sum || shasum -a 256; } | cut -d' ' -f1)"

if [ "${1:-}" = "--check" ]; then
  if [ "$hash" != "$EXPECTED" ]; then
    echo "canonical start.sh/stop.sh block drifted:" >&2
    echo "  got      $hash" >&2
    echo "  expected $EXPECTED" >&2
    echo "If intentional: set EXPECTED=$hash in scripts/canonical-hash.sh and copy" >&2
    echo "start.sh + stop.sh + scripts/canonical-hash.sh to every curfew-marathon repo." >&2
    exit 1
  fi
  echo "canonical block in sync ($hash)"
else
  echo "$hash"
fi
