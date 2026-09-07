#!/usr/bin/env bash
#
# start.sh - bring importrr up.
#
# Usage:
#   ./start.sh              Start the stack
#   ./start.sh --pull       Pull the latest image before starting
#   ./start.sh --logs       Follow container logs once it is up
#
# Flags may be combined, e.g. ./start.sh --pull --logs
#
set -euo pipefail
cd "$(dirname "$0")"

log()  { printf '\033[1;36m> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m! %s\033[0m\n' "$*"; }
err()  { printf '\033[1;31mx %s\033[0m\n' "$*" >&2; }

# ── args ─────────────────────────────────────────────────────────────────────
PULL=0
FOLLOW_LOGS=0

for arg in "$@"; do
  case "$arg" in
    --pull)     PULL=1 ;;
    --logs)     FOLLOW_LOGS=1 ;;
    -h|--help)  sed -n '3,10p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) err "unknown option '$arg' (try --help)"; exit 2 ;;
  esac
done

# ── preflight ────────────────────────────────────────────────────────────────
command -v docker >/dev/null 2>&1      || { err "docker is not installed or not on PATH."; exit 1; }
docker info >/dev/null 2>&1            || { err "Docker daemon is not running."; exit 1; }
docker compose version >/dev/null 2>&1 || { err "'docker compose' v2 is required."; exit 1; }

if [ ! -f .env ]; then
  if [ -f .env.example ]; then
    warn ".env not found - creating it from .env.example. Set your real paths in it."
    cp .env.example .env
  else
    warn ".env and .env.example both missing - creating an empty .env (compose defaults apply)."
    touch .env
  fi
fi

docker compose config --quiet || { err "docker-compose.yml failed validation."; exit 1; }

# ── up ───────────────────────────────────────────────────────────────────────
[ "$PULL" = "1" ] && { log "Pulling latest image..."; docker compose pull; }

log "Bringing importrr up..."
docker compose up -d --remove-orphans

# ── verify it stays up (no healthcheck; catch a startup crash loop) ─────────
log "Checking the container starts cleanly..."
_state()    { docker inspect -f '{{.State.Status}}' importrr 2>/dev/null || echo missing; }
_restarts() { docker inspect -f '{{.RestartCount}}' importrr 2>/dev/null || echo 0; }

sleep 3
if [ "$(_state)" != "running" ]; then
  err "container is '$(_state)' just after start - check 'docker compose logs'"
  exit 1
fi
r1="$(_restarts)"
sleep 7
if [ "$(_restarts)" -gt "$r1" ] || [ "$(_state)" != "running" ]; then
  err "container is restart-looping (crash on startup) - check 'docker compose logs'"
  exit 1
fi
log "Container up."

# ── status ──────────────────────────────────────────────────────────────────
echo
docker compose ps
metrics_port="$(docker compose exec -T importrr printenv METRICS_PORT 2>/dev/null | tr -d '\r' || true)"
metrics_enabled="$(docker compose exec -T importrr printenv METRICS_ENABLED 2>/dev/null | tr -d '\r' || true)"
case "$(printf '%s' "${metrics_enabled:-true}" | tr '[:upper:]' '[:lower:]')" in
  1|true|yes) metrics_line="http://localhost:${metrics_port:-9130}/metrics" ;;
  *)          metrics_line="disabled (METRICS_ENABLED=${metrics_enabled})" ;;
esac
cat <<EOF

  Metrics    ${metrics_line}

  Follow logs:     docker compose logs -f
  Stop:            ./stop.sh
EOF

if [ "$FOLLOW_LOGS" = "1" ]; then
  echo
  log "Following logs (Ctrl+C detaches; the container keeps running)..."
  exec docker compose logs -f
fi
