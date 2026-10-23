#!/usr/bin/env bash
# Restores a backup written by scripts/backup-live.sh INTO THE LIVE STACK (docs/operating-runbook.md §6.2).
# Destructive: the asseta, keycloak and mlflow databases are dropped and recreated from the dumps, and the MinIO
# buckets are mirrored back (objects are content-addressed, so existing ones are overwritten with identical bytes;
# objects newer than the backup are kept). Asks for confirmation twice and offers a safety backup first.
#
#   scripts/restore-live.sh /home/asseta/backups/<UTC timestamp> [--skip-objects]
#
# Order (runbook §6.2): stop writers -> databases -> objects -> Keycloak -> migrate (no-op at head) -> api/workers
# -> readiness -> Traccar last (it re-forwards what it buffered meanwhile).
set -Eeuo pipefail

LOG_TAG=restore
# shellcheck source-path=SCRIPTDIR source=lib/live-common.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/live-common.sh"
cd "$REPO_ROOT"

BUCKETS=(asseta-evidence asseta-mlflow)
declare -A DB_OWNER=([asseta]=asseta_owner [keycloak]=keycloak [mlflow]=mlflow)

[[ $# -ge 1 ]] || fail "Usage: $0 BACKUP_DIR [--skip-objects]"
DIR="$(cd "$1" && pwd)"
SKIP_OBJECTS=0
[[ "${2:-}" == "--skip-objects" ]] && SKIP_OBJECTS=1

require_cmd docker
require_cmd sha256sum
require_compose_v2
require_env_file

[[ -f "$DIR/SHA256SUMS" && -f "$DIR/MANIFEST" ]] || fail "$DIR is not a complete backup (no SHA256SUMS/MANIFEST)"
log "Verifying checksums in $DIR"
(cd "$DIR" && sha256sum --quiet -c SHA256SUMS) || fail "Checksum verification failed; not restoring."
for db in "${!DB_OWNER[@]}"; do
  [[ -s "$DIR/$db.dump" ]] || fail "Missing $DIR/$db.dump"
done

DOMAIN="$(cfg DOMAIN asseta.co.tz)"
printf '\nBackup manifest:\n'
sed 's/^/  /' "$DIR/MANIFEST"
printf '\nThis REPLACES all live data of %s (project %s): databases %s' "$DOMAIN" "$COMPOSE_PROJECT_NAME" \
  "${!DB_OWNER[*]}"
[[ "$SKIP_OBJECTS" == "1" ]] || printf ' and buckets %s' "${BUCKETS[*]}"
printf '.\nUsers will be signed out and the site is unavailable until the restore finishes.\n\n'

if [[ "${RESTORE_ASSUME_YES:-0}" != "1" ]]; then
  read -r -p "Type RESTORE to continue: " answer
  [[ "$answer" == "RESTORE" ]] || fail "Aborted."
  read -r -p "Type the domain name ($DOMAIN) to confirm: " answer
  [[ "$answer" == "$DOMAIN" ]] || fail "Aborted."
  read -r -p "Take a safety backup of the current state first? [Y/n] " answer
  if [[ ! "$answer" =~ ^[Nn] ]]; then
    "$REPO_ROOT/scripts/backup-live.sh"
  fi
fi

started=$SECONDS
log "Stopping writers: ${WRITER_SERVICES[*]} keycloak"
compose stop "${WRITER_SERVICES[@]}" keycloak
if mlflow_enabled; then compose stop mlflow; fi

[[ "$(service_health postgres)" == "healthy" ]] || {
  compose up -d postgres
  wait_healthy postgres 300
}
# Roles: asseta_owner/asseta_app/keycloak exist on any volume initialised by infra/postgres/init; mlflow is created
# idempotently by the mlflow-db-init one-shot.
DBS=(asseta keycloak)
if [[ -f "$DIR/mlflow.dump" ]]; then
  compose run --rm --no-deps mlflow-db-init >/dev/null
  DBS+=(mlflow)
fi

for db in "${DBS[@]}"; do
  log "Recreating database $db (owner ${DB_OWNER[$db]})"
  compose exec -T postgres psql -U postgres -d postgres -v ON_ERROR_STOP=1 -q \
    -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$db' AND pid <> pg_backend_pid()" \
    -c "DROP DATABASE IF EXISTS $db" \
    -c "CREATE DATABASE $db OWNER ${DB_OWNER[$db]} TEMPLATE template0" >/dev/null
  log "pg_restore $db"
  compose exec -T postgres pg_restore -U postgres -d "$db" --exit-on-error <"$DIR/$db.dump"
done

alembic_now="$(compose exec -T postgres psql -U postgres -d asseta -qAt -c 'SELECT version_num FROM alembic_version')"
unforced="$(compose exec -T postgres psql -U postgres -d asseta -qAt -c \
  "SELECT count(*) FROM pg_class WHERE relrowsecurity AND NOT relforcerowsecurity AND relkind IN ('r','p')")"
log "Restored alembic_version=$alembic_now (backup: $(cat "$DIR/alembic_version.txt")); tables with RLS not forced: $unforced"
[[ "$unforced" == "0" ]] || fail "RLS check failed after restore ($unforced tables without FORCE ROW LEVEL SECURITY)"

if [[ "$SKIP_OBJECTS" != "1" ]]; then
  # shellcheck disable=SC2016 # expanded by sh inside the container (credentials never leave it)
  restore_cmd='mc alias set dst http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null'
  for bucket in "${BUCKETS[@]}"; do
    [[ -d "$DIR/objects/$bucket" ]] || continue
    restore_cmd+=" && mc mb -p dst/$bucket >/dev/null && mc mirror --overwrite --quiet /backup/$bucket dst/$bucket"
  done
  # shellcheck disable=SC2016
  restore_cmd+='; rc=$?; mc alias rm dst >/dev/null 2>&1; exit $rc'
  log "Mirroring objects back into MinIO"
  compose up -d minio
  wait_healthy minio 180
  compose run --rm --no-deps -T -e HOME=/tmp -v "$DIR/objects:/backup:ro" --entrypoint sh minio -c "$restore_cmd" \
    </dev/null
fi

log "Starting Keycloak"
compose up -d --no-deps keycloak
wait_healthy keycloak 600
log "Running migrate (no-op when the schema is at head)"
compose run --rm --no-deps migrate
if mlflow_enabled; then compose up -d --no-deps mlflow; fi
compose up -d --no-deps "${APP_SERVICES[@]}"
wait_for_api 300
compose up -d --no-deps traccar
log "Restore complete in $((SECONDS - started)) s. Verify: a known user signs in; the fleet map shows last positions;"
log "evidence photos open (runbook §6.2 step 5)."
