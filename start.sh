#!/usr/bin/env bash
#
# start.sh - bring importrr up.
#
# Usage:
#   ./start.sh              Build the image from source, then start the container
#   ./start.sh --pull       Pull the published image instead of building, then start
#   ./start.sh --no-build   Start the local image only (no build, no pull)
#   ./start.sh --logs       Follow the container logs once it is healthy
#
#   -h, --help              Show this help
#
# Default is build-from-source so you run exactly what is in your tree. --pull is
# the explicit opt-in to running a prebuilt image you did not build (the server
# passes it on every start). IMPORTRR_TAG pins which tag --pull fetches.
#
# canonical-run-script: v1  (reference: curfew-marathon/hivemind)
# Everything except this header block and the sections fenced
# "# >>> project-specific" ... "# <<< project-specific" is byte-identical across
# hivemind / importrr / uploadrr / prometheus. Edit the reference first, then propagate.
#
set -euo pipefail
cd "$(dirname "$0")"

log()  { printf '\033[1;36m> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m! %s\033[0m\n' "$*"; }
err()  { printf '\033[1;31mx %s\033[0m\n' "$*" >&2; }

# >>> project-specific
PROJECT_NAME="importrr"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-120}"
LOGS_CMD=(docker compose logs -f)
# <<< project-specific

# ── args ─────────────────────────────────────────────────────────────────────
MODE="build"        # build | pull | nobuild
FOLLOW_LOGS=0
MODE_SET=""

_set_mode() {
  [ -z "$MODE_SET" ] || { err "choose one of --pull / --no-build (not both)"; exit 2; }
  MODE="$1"; MODE_SET=1
}

for arg in "$@"; do
  case "$arg" in
    --pull)      _set_mode pull ;;
    --no-build)  _set_mode nobuild ;;
    --logs)      FOLLOW_LOGS=1 ;;
    -h|--help)   sed -n '3,15p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) err "unknown option '$arg' (try --help)"; exit 2 ;;
  esac
done

# ── helpers ──────────────────────────────────────────────────────────────────
# True when the resolved compose config declares at least one build context.
# Capture first, then grep the variable: `docker compose config | grep -q` lets
# grep close the pipe on the first match, `config` can then exit 141 (SIGPIPE),
# and `set -o pipefail` would turn a repo that HAS a build context into "no
# build context here".
_has_build_services() {
  local cfg
  cfg="$(docker compose config 2>/dev/null || true)"
  grep -qE '^[[:space:]]+context:[[:space:]]' <<<"$cfg"
}

# Poll every configured compose service to one shared deadline. A service passes
# only while its container is "running" AND (it has no healthcheck, or reports
# "healthy"). Missing / exited / still coming up keeps the stack pending until
# the deadline, then fails with the pending list.
#
# Uses `config --services` (every configured service) not `ps --services` (only
# services with a live container): a service whose container exits right after
# `up` would otherwise drop off the list and let a half-up stack read as healthy.
wait_for_health() {
  local timeout="$HEALTH_TIMEOUT" deadline services
  deadline=$(( $(date +%s) + timeout ))
  services="$(docker compose config --services 2>/dev/null || true)"
  [ -n "$services" ] || { err "no services in docker-compose.yml?"; return 1; }

  log "Waiting up to ${timeout}s for services to report healthy..."
  while :; do
    local all_ok=1 pending="" svc cid snap status health
    for svc in $services; do
      cid="$(docker compose ps -aq "$svc" 2>/dev/null | head -n1 || true)"
      if [ -z "$cid" ]; then all_ok=0; pending="$pending ${svc}(no-container)"; continue; fi
      # One inspect snapshot. Two calls would let the container exit between them:
      # call 1 sees "running", call 2 returns the retained "healthy" - exactly the
      # crash this guard rejects. Inspect failure -> "unknown|none" -> not-ready.
      snap="$(docker inspect -f '{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$cid" 2>/dev/null || echo 'unknown|none')"
      status="${snap%%|*}"; health="${snap##*|}"
      # "running" is required regardless of the health value: Docker keeps the
      # last .State.Health.Status ("healthy") after a container exits, so a
      # crash right after going healthy would otherwise pass. created / restarting
      # / exited / dead / paused all keep the stack pending; a crash-looper is
      # almost never "running" when polled, so the deadline still catches it.
      if [ "$status" != "running" ]; then
        all_ok=0; pending="$pending ${svc}(${status})"
      else
        case "$health" in
          healthy|none) ;;
          *) all_ok=0; pending="$pending ${svc}(${health})" ;;   # starting | unhealthy
        esac
      fi
    done

    if [ "$all_ok" = "1" ]; then log "All services healthy."; return 0; fi
    if [ "$(date +%s)" -ge "$deadline" ]; then
      err "Timed out after ${timeout}s; still waiting on:${pending}"
      err "Inspect with: docker compose ps  |  docker compose logs"
      return 1
    fi
    sleep 2
  done
}

# >>> project-specific
print_status() {
  echo
  docker compose ps
  # The compose mapping is HOST:METRICS_PORT:METRICS_PORT, so the host port is
  # just METRICS_PORT. Read both back from the running container.
  local port enabled line
  port="$(docker compose exec -T importrr printenv METRICS_PORT 2>/dev/null | tr -d '\r' || true)"
  enabled="$(docker compose exec -T importrr printenv METRICS_ENABLED 2>/dev/null | tr -d '\r' || true)"
  case "$(printf '%s' "${enabled:-true}" | tr '[:upper:]' '[:lower:]')" in
    1|true|yes) line="http://localhost:${port:-9130}/metrics" ;;
    *)          line="disabled (METRICS_ENABLED=${enabled})" ;;
  esac
  cat <<EOF

  Metrics    ${line}

  Follow logs:     docker compose logs -f
  Stop:            ./stop.sh
EOF
}
# <<< project-specific

# ── preflight ────────────────────────────────────────────────────────────────
command -v docker >/dev/null 2>&1        || { err "docker is not installed or not on PATH."; exit 1; }
docker info >/dev/null 2>&1              || { err "Docker daemon is not running. Start Docker and retry."; exit 1; }
docker compose version >/dev/null 2>&1   || { err "'docker compose' v2 is required. Update Docker."; exit 1; }

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

# ── build / pull / up ────────────────────────────────────────────────────────
UP_ARGS=(up -d --remove-orphans)
case "$MODE" in
  pull)
    log "Pulling published images..."
    if ! docker compose pull; then
      warn "pull failed for one or more images - using what is present."
      docker compose pull --ignore-pull-failures || true
      # the pull phase is done; don't let `up` retry the registry on its own.
      UP_ARGS+=(--pull never)
    fi
    UP_ARGS+=(--no-build)
    ;;
  nobuild)
    # --no-build means run what is here: no build AND no pull.
    UP_ARGS+=(--no-build --pull never)
    ;;
  build)
    if _has_build_services; then
      UP_ARGS+=(--build)
    else
      warn "no build context here - starting the published image (use --pull to refresh it)."
    fi
    ;;
esac

log "Bringing ${PROJECT_NAME} up..."
docker compose "${UP_ARGS[@]}"

if ! wait_for_health; then
  err "${PROJECT_NAME} did not come up cleanly."
  docker compose ps
  exit 1
fi
print_status

if [ "$FOLLOW_LOGS" = "1" ]; then
  echo
  log "Following logs (Ctrl+C detaches; the container keeps running)..."
  exec "${LOGS_CMD[@]}"
fi
