#!/usr/bin/env bash
#
# stop.sh - take importrr down.
#
# Usage:
#   ./stop.sh              Stop and remove the container
#   ./stop.sh --images     Also remove the image pulled for this project
#
set -euo pipefail
cd "$(dirname "$0")"

log()  { printf '\033[1;36m> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m! %s\033[0m\n' "$*"; }
err()  { printf '\033[1;31mx %s\033[0m\n' "$*" >&2; }

DROP_IMAGES=0

for arg in "$@"; do
  case "$arg" in
    --images)   DROP_IMAGES=1 ;;
    -h|--help)  sed -n '3,8p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) err "unknown option '$arg' (try --help)"; exit 2 ;;
  esac
done

command -v docker >/dev/null 2>&1      || { err "docker is not installed or not on PATH."; exit 1; }
docker info >/dev/null 2>&1            || { err "Docker daemon is not running."; exit 1; }
docker compose version >/dev/null 2>&1 || { err "'docker compose' v2 is required."; exit 1; }

DOWN_ARGS=(down --remove-orphans)
# --rmi all, not local: the service image is tagged (curfewmarathon/importrr:TAG),
# and `--rmi local` only removes images that have no tag.
[ "$DROP_IMAGES" = "1" ] && DOWN_ARGS+=(--rmi all)

log "Stopping importrr..."
docker compose "${DOWN_ARGS[@]}"

log "Done. Any tar files left in the archive dirs are retried on the next ./start.sh."
