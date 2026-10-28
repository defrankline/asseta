#!/usr/bin/env bash
# Reset ONE tenant's business data before go-live (docs/operating-runbook.md, "Reset a tenant's data before go-live").
#
#   scripts/reset-tenant-data.sh --registration-number 2026/10/0001          dry run: prints what would be deleted/kept
#   scripts/reset-tenant-data.sh --registration-number 2026/10/0001 --yes    real run: asks you to type the tenant name
#   (--tenant-id UUID instead of --registration-number)
#
# Options: --yes (really reset), --backup-confirmed (skip the recent-backup check), --operator WHO (recorded in the
# audit event; default <your user>@<host>), --remove-traccar-devices (also delete the trackers' Traccar devices; needs
# TRACCAR_ADMIN_EMAIL, the password is asked for), --no-objects (leave the object store alone).
#
# Keeps the tenant, its Asseta subscription and platform billing, Keycloak accounts and their groups, memberships,
# staff and the platform audit; deletes every other business record of the tenant and its object-store files, and
# revokes its phones so they wipe and bootstrap afresh (details: backend/scripts/reset_tenant_data.py). A real run
# refuses without a backup by scripts/backup-live.sh younger than RESET_BACKUP_MAX_AGE_MIN (120) minutes under
# BACKUP_ROOT (/home/asseta/backups), unless --backup-confirmed is given.
#
# Runs backend/scripts/reset_tenant_data.py in a throwaway container of the deployed API image on the compose network
# (`compose run --rm --no-deps api`), as the calling user: the database (schema owner, as the migrations) and object
# store settings come from that container's environment, never from a command line. Demo seeder state files in
# DEMO_DIR (.deploy/) of the tenant are moved aside. Knobs: DEMO_DIR, TRACCAR_API_URL (http://traccar:8082), plus
# those of lib/live-common.sh.
set -Eeuo pipefail

LOG_TAG=reset-tenant
# shellcheck source-path=SCRIPTDIR source=lib/live-common.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/live-common.sh"
cd "$REPO_ROOT"

usage() {
  sed -n '2,/^set -Eeuo/p' "${BASH_SOURCE[0]}" | sed '$d' | sed -E 's/^# ?//'
  exit "${1:-0}"
}

[[ $# -ge 1 ]] || usage 1
real=0 backup_confirmed=0 operator_given=0 traccar=0
for arg in "$@"; do
  case "$arg" in
    -h | --help) usage 0 ;;
    --yes) real=1 ;;
    --backup-confirmed) backup_confirmed=1 ;;
    --operator | --operator=*) operator_given=1 ;;
    --remove-traccar-devices) traccar=1 ;;
  esac
done

require_cmd docker
require_compose_v2
require_env_file
case "$(service_health api)" in
  healthy | running) ;;
  *) fail "The api service is not running (scripts/compose-live.sh ps); deploy first." ;;
esac

DEMO_DIR="${DEMO_DIR:-$REPO_ROOT/.deploy}"
[[ -d "$DEMO_DIR" ]] || mkdir -m 700 "$DEMO_DIR"

EXTRA=()
if [[ "$operator_given" == 0 ]]; then
  EXTRA+=(--operator "${SUDO_USER:-${USER:-$(id -un)}}@$(hostname)")
fi

if [[ "$real" == 1 ]]; then
  [[ -t 0 ]] || fail "A real reset asks you to type the tenant name: run it from an interactive terminal."
  if [[ "$backup_confirmed" == 0 ]]; then
    root="$(cfg BACKUP_ROOT /home/asseta/backups)"
    max_age="${RESET_BACKUP_MAX_AGE_MIN:-120}"
    latest=""
    if [[ -d "$root" ]]; then # only directories backup-live.sh completed (it writes MANIFEST last but one)
      while IFS= read -r dir; do
        if [[ -f "$dir/MANIFEST" && -f "$dir/SHA256SUMS" ]]; then
          latest="$dir"
          break
        fi
      done < <(find "$root" -mindepth 1 -maxdepth 1 -type d -mmin "-$max_age" \
        -name '20[0-9][0-9][01][0-9][0-3][0-9]T[0-9][0-9][0-9][0-9][0-9][0-9]Z' | sort -r)
    fi
    [[ -n "$latest" ]] || fail "No complete backup younger than $max_age min under $root. Run scripts/backup-live.sh first
  (or pass --backup-confirmed if you have a fresh backup elsewhere)."
    log "Recent backup: $latest"
    EXTRA+=(--backup-confirmed --backup-ref "$latest")
  fi
fi

# Secrets reach the container as environment variables only (`-e NAME`, value taken from this process).
SECRET_ENV=()
if [[ "$traccar" == 1 ]]; then
  [[ -n "${TRACCAR_ADMIN_EMAIL:-}" ]] || fail "--remove-traccar-devices needs TRACCAR_ADMIN_EMAIL (a Traccar admin)"
  traccar_password="${TRACCAR_ADMIN_PASSWORD:-}"
  if [[ -z "$traccar_password" ]]; then
    [[ -t 0 ]] || fail "TRACCAR_ADMIN_PASSWORD is not set and there is no terminal to ask for it"
    read -rsp "Traccar password for $TRACCAR_ADMIN_EMAIL: " traccar_password
    printf '\n'
  fi
  export TRACCAR_ADMIN_EMAIL TRACCAR_ADMIN_PASSWORD="$traccar_password"
  SECRET_ENV+=(-e TRACCAR_ADMIN_EMAIL -e TRACCAR_ADMIN_PASSWORD)
fi

TTY_ARGS=(-T)
[[ "$real" == 1 ]] && TTY_ARGS=() # the name prompt needs a terminal inside the container

log "Running the tenant data reset ($([[ "$real" == 1 ]] && echo 'REAL RUN' || echo 'dry run')) in a throwaway API container"
compose run --rm --no-deps ${TTY_ARGS[@]+"${TTY_ARGS[@]}"} \
  --user "$(id -u):$(id -g)" \
  --entrypoint python \
  -v "$REPO_ROOT/backend/scripts:/opt/asseta-reset:ro" \
  -v "$DEMO_DIR:/out" \
  ${SECRET_ENV[@]+"${SECRET_ENV[@]}"} \
  -e "ASSETA_TRACCAR_API_URL=${TRACCAR_API_URL:-http://traccar:8082}" \
  -e PYTHONDONTWRITEBYTECODE=1 \
  api /opt/asseta-reset/reset_tenant_data.py --state-dir /out "$@" ${EXTRA[@]+"${EXTRA[@]}"}
