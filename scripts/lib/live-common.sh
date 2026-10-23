# shellcheck shell=bash
# Shared helpers for the production scripts (deploy-live, backup-live, restore-live, create-platform-owner,
# compose-live). Sourced, never executed. Secrets are read from .env.production by key and never echoed.
#
# Knobs (environment overrides .env.production; used by local rehearsals):
#   ENV_FILE (.env.production), COMPOSE_FILE (compose.prod.yaml), COMPOSE_PROJECT_NAME (asseta),
#   DOCKER_IMAGE_PREFIX (asseta), STATE_FILE (.deploy/state.env)

REPO_ROOT="${REPO_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
ENV_FILE="${ENV_FILE:-$REPO_ROOT/.env.production}"
COMPOSE_FILE="${COMPOSE_FILE:-$REPO_ROOT/compose.prod.yaml}"
COMPOSE_LOCAL_FILE="${COMPOSE_LOCAL_FILE:-$REPO_ROOT/compose.prod.local.yaml}"
COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-asseta}"
DOCKER_IMAGE_PREFIX="${DOCKER_IMAGE_PREFIX:-asseta}"
STATE_FILE="${STATE_FILE:-$REPO_ROOT/.deploy/state.env}"
LOG_TAG="${LOG_TAG:-asseta}"

# No default provenance attestations: they only add a per-build manifest to this project's local images.
BUILDX_NO_DEFAULT_ATTESTATIONS=1
export COMPOSE_PROJECT_NAME DOCKER_IMAGE_PREFIX BUILDX_NO_DEFAULT_ATTESTATIONS

# shellcheck disable=SC2034 # APP_SERVICES / WRITER_SERVICES are used by the scripts that source this file
# The services that run the app image; recreated on every deploy. Infra services are only ever `up -d`'d.
APP_SERVICES=(api outbox-relay billing-scheduler timeline-worker connectivity-worker intelligence-worker
  notification-worker notification-scheduler)
# shellcheck disable=SC2034
WRITER_SERVICES=("${APP_SERVICES[@]}" traccar)

log() {
  printf '[%s] %s\n' "$LOG_TAG" "$*"
}

warn() {
  printf '[%s:warn] %s\n' "$LOG_TAG" "$*" >&2
}

fail() {
  printf '[%s:error] %s\n' "$LOG_TAG" "$*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "Missing required command: $1"
}

sudo_cmd() {
  if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
    "$@"
  else
    sudo "$@"
  fi
}

# Value of KEY from an env file (last assignment wins; surrounding single/double quotes stripped). No sourcing, so
# a value is never executed and never needs shell quoting.
env_file_get() {
  local file="$1" key="$2" line value
  [[ -f "$file" ]] || return 0
  line="$(grep -E "^${key}=" "$file" | tail -n 1 || true)"
  [[ -n "$line" ]] || return 0
  value="${line#*=}"
  value="${value%$'\r'}"
  if [[ "$value" =~ ^\"(.*)\"$ ]] || [[ "$value" =~ ^\'(.*)\'$ ]]; then
    value="${BASH_REMATCH[1]}"
  fi
  printf '%s' "$value"
}

# cfg KEY [default]: environment variable, else .env.production, else default.
cfg() {
  local key="$1" default="${2:-}" value
  if [[ -n "${!key+x}" && -n "${!key}" ]]; then
    printf '%s' "${!key}"
    return 0
  fi
  value="$(env_file_get "$ENV_FILE" "$key")"
  printf '%s' "${value:-$default}"
}

require_compose_v2() {
  docker compose version >/dev/null 2>&1 || fail "Docker Compose v2 is required (the 'docker compose' plugin)."
  local version major
  version="$(docker compose version --short 2>/dev/null || true)"
  major="${version#v}"
  major="${major%%.*}"
  [[ "$major" =~ ^[0-9]+$ && "$major" -ge 2 ]] || fail "Docker Compose v2+ required (found '${version:-unknown}')."
}

compose_args() {
  COMPOSE_ARGS=(-f "$COMPOSE_FILE")
  if [[ -f "$COMPOSE_LOCAL_FILE" ]]; then
    COMPOSE_ARGS+=(-f "$COMPOSE_LOCAL_FILE")
  fi
  COMPOSE_ARGS+=(-p "$COMPOSE_PROJECT_NAME" --env-file "$ENV_FILE")
  if [[ -f "$STATE_FILE" ]]; then
    COMPOSE_ARGS+=(--env-file "$STATE_FILE")
  fi
}

compose() {
  compose_args
  docker compose "${COMPOSE_ARGS[@]}" "$@"
}

require_env_file() {
  [[ -f "$ENV_FILE" ]] || fail "Missing $ENV_FILE. Run scripts/generate-production-secrets.sh first."
}

# Deploy state (image tag, proxy gateway, device-port bind) written by deploy-live.sh, read by compose().
state_get() {
  env_file_get "$STATE_FILE" "$1"
}

state_write() {
  local dir tmp
  dir="$(dirname "$STATE_FILE")"
  mkdir -p "$dir"
  tmp="$(mktemp "$dir/.state.XXXXXX")"
  {
    printf '# Written by scripts/deploy-live.sh; read by every scripts/*-live.sh. Not a secret file.\n'
    printf 'DEPLOY_IMAGE_TAG=%s\n' "$1"
    printf 'PREVIOUS_IMAGE_TAG=%s\n' "$2"
    printf 'ASSETA_PROXY_TRUSTED_IP=%s\n' "$3"
    printf 'ASSETA_TRACCAR_DEVICE_BIND=%s\n' "$4"
  } >"$tmp"
  mv "$tmp" "$STATE_FILE"
}

# Health status of a compose service's container: healthy | unhealthy | starting | running (no healthcheck) | missing
service_health() {
  local id
  id="$(compose ps -q "$1" 2>/dev/null | head -n 1)"
  [[ -n "$id" ]] || {
    printf 'missing'
    return 0
  }
  docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$id" 2>/dev/null ||
    printf 'missing'
}

wait_healthy() {
  local service="$1" timeout="${2:-300}" waited=0 status
  log "Waiting for $service to be healthy (up to ${timeout}s)"
  while ((waited < timeout)); do
    status="$(service_health "$service")"
    case "$status" in
      healthy | running) return 0 ;;
      exited | dead) break ;;
    esac
    sleep 5
    waited=$((waited + 5))
  done
  warn "$service is '$status' after ${waited}s. Recent logs:"
  compose logs --tail=80 "$service" >&2 || true
  fail "$service did not become healthy."
}

api_ready_url() {
  printf 'http://%s:%s/api/v1/health/ready' "$(cfg LOCAL_UPSTREAM_HOST 127.0.0.1)" "$(cfg ASSETA_API_HOST_PORT 5020)"
}

api_ready_body() {
  curl -fsS --max-time 10 "$(api_ready_url)" 2>/dev/null || true
}

# Waits until /api/v1/health/ready reports every dependency ok.
wait_for_api() {
  local timeout="${1:-300}" waited=0 body=""
  log "Waiting for $(api_ready_url) (up to ${timeout}s)"
  while ((waited < timeout)); do
    body="$(api_ready_body)"
    if [[ "$body" == *'"status":"ok","checks"'* ]]; then
      log "API ready: $body"
      return 0
    fi
    sleep 5
    waited=$((waited + 5))
  done
  warn "Readiness: ${body:-no response}. Recent API logs:"
  compose logs --tail=150 api >&2 || true
  fail "API did not become ready."
}
