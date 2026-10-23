#!/usr/bin/env bash
# Demo data for ONE existing tenant on the live stack (docs/deployment-live.md, "Demo tenant data").
#
#   scripts/seed-demo-tenant.sh seed     [--region dar-es-salaam|dodoma|arusha|mwanza] [--demo-domain DOMAIN]
#   scripts/seed-demo-tenant.sh feed     [--minutes 90] [--interval 30]
#   scripts/seed-demo-tenant.sh status   [--quick]
#   scripts/seed-demo-tenant.sh retire   --yes
#
# Defaults target "Wambura & Sons Ltd" (registration number 2026/10/0001); --registration-number, --tenant-name and
# --slug select another tenant. The tenant is changed only under a temporary managed-service mandate that the
# script grants and ends itself (DEC-018); its throwaway platform user and Keycloak client are deleted at the end.
#
# Runs backend/scripts/demo_tenant_live.py in a throwaway container of the deployed API image on the compose network
# (`compose run --rm --no-deps api`), as the calling user, so the files it writes to DEMO_DIR (default .deploy/)
# belong to you: demo-<slug>-credentials.json (demo passwords, mode 600) and demo-<slug>-state.json. The Keycloak
# admin credentials and the Traccar gateway key are read from .env.production and reach the container as
# environment variables only, never on a command line or in the output.
#
# Knobs (environment): DEMO_DIR, DEMO_API_URL (http://api:8000), DEMO_KEYCLOAK_URL (http://keycloak:8080/auth),
# DEMO_OSMAND_URL (http://traccar:5055), DEMO_TRACCAR_API_URL (http://traccar:8082), DEMO_WEB_URL;
# TRACCAR_ADMIN_EMAIL to register the simulated devices in Traccar (the password is asked for); plus the knobs of
# lib/live-common.sh (ENV_FILE, COMPOSE_FILE, STATE_FILE, ...), which the local rehearsal uses.
set -Eeuo pipefail

LOG_TAG=demo-tenant
# shellcheck source-path=SCRIPTDIR source=lib/live-common.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/live-common.sh"
cd "$REPO_ROOT"

usage() {
  sed -n '2,/^set -Eeuo/p' "${BASH_SOURCE[0]}" | sed '$d' | sed -E 's/^# ?//'
  exit "${1:-0}"
}

[[ $# -ge 1 ]] || usage 1
command="$1"
shift
case "$command" in
  seed | feed | status | retire) ;;
  -h | --help | help) usage 0 ;;
  *) usage 1 ;;
esac

require_cmd docker
require_compose_v2
require_env_file
case "$(service_health api)" in
  healthy | running) ;;
  *) fail "The api service is not running (scripts/compose-live.sh ps); deploy first." ;;
esac

DEMO_DIR="${DEMO_DIR:-$REPO_ROOT/.deploy}"
[[ -d "$DEMO_DIR" ]] || mkdir -m 700 "$DEMO_DIR"

# Secrets reach the container as environment variables only (`-e NAME`, value taken from this process). Empty values
# are never exported: compose interpolates the same names from the env file and refuses empty ones.
SECRET_ENV=()
pass_env() {
  if [[ -n "$2" ]]; then
    export "$1=$2"
    SECRET_ENV+=(-e "$1")
  fi
}
if [[ "$command" != "feed" ]]; then # the feed needs no Keycloak access at all
  admin_user="$(cfg KEYCLOAK_ADMIN_USER)"
  admin_password="$(cfg KEYCLOAK_ADMIN_PASSWORD)"
  [[ -n "$admin_user" && -n "$admin_password" ]] || fail "KEYCLOAK_ADMIN_USER / KEYCLOAK_ADMIN_PASSWORD missing in $ENV_FILE"
  pass_env KEYCLOAK_ADMIN_USER "$admin_user"
  pass_env KEYCLOAK_ADMIN_PASSWORD "$admin_password"
fi
pass_env ASSETA_TRACCAR_GATEWAY_KEY "$(cfg ASSETA_TRACCAR_GATEWAY_KEY)"
traccar_password="${TRACCAR_ADMIN_PASSWORD:-}"
if [[ -n "${TRACCAR_ADMIN_EMAIL:-}" && -z "$traccar_password" ]]; then
  [[ -t 0 ]] || fail "TRACCAR_ADMIN_PASSWORD is not set and there is no terminal to ask for it"
  read -rsp "Traccar password for $TRACCAR_ADMIN_EMAIL: " traccar_password
  printf '\n'
fi
pass_env TRACCAR_ADMIN_EMAIL "${TRACCAR_ADMIN_EMAIL:-}"
pass_env TRACCAR_ADMIN_PASSWORD "$traccar_password"

log "Running '$command' in a throwaway API container (files in $DEMO_DIR)"
compose run --rm --no-deps -T \
  --user "$(id -u):$(id -g)" \
  --entrypoint python \
  -v "$REPO_ROOT/backend/scripts:/opt/asseta-demo:ro" \
  -v "$DEMO_DIR:/out" \
  ${SECRET_ENV[@]+"${SECRET_ENV[@]}"} \
  -e "ASSETA_DEMO_API_URL=${DEMO_API_URL:-http://api:8000}" \
  -e "ASSETA_DEMO_KEYCLOAK_URL=${DEMO_KEYCLOAK_URL:-http://keycloak:8080/auth}" \
  -e "ASSETA_DEMO_OSMAND_URL=${DEMO_OSMAND_URL:-http://traccar:5055}" \
  -e "ASSETA_DEMO_TRACCAR_API_URL=${DEMO_TRACCAR_API_URL:-http://traccar:8082}" \
  -e "ASSETA_DEMO_WEB_URL=${DEMO_WEB_URL:-$(cfg ASSETA_WEB_URL https://asseta.co.tz)}" \
  -e PYTHONDONTWRITEBYTECODE=1 \
  api /opt/asseta-demo/demo_tenant_live.py "$command" --out-dir /out "$@"
