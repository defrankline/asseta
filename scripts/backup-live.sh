#!/usr/bin/env bash
# Production backup (docs/operating-runbook.md §6.1; the same commands the backup/restore drill verified):
#   pg_dump -Fc of asseta, keycloak, mlflow  ->  Keycloak realm config record  ->  MinIO mirror (AFTER the dumps:
#   evidence is content-addressed and write-once, so every key the dumps reference is in the mirror).
# Writes BACKUP_ROOT/<UTC timestamp>/ (default /home/asseta/backups), keeps BACKUP_RETENTION_DAYS (7) days, and
# copies the new backup to BACKUP_REMOTE with rsync when set. Secrets stay inside the containers; nothing secret
# is printed. .env.production is NOT part of the backup: keep an encrypted copy of it elsewhere.
#
#   scripts/backup-live.sh
#   cron: 15 2 * * * cd /home/asseta && scripts/backup-live.sh >> /home/asseta/backups/backup.log 2>&1
set -Eeuo pipefail

LOG_TAG=backup
# shellcheck source-path=SCRIPTDIR source=lib/live-common.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/live-common.sh"
cd "$REPO_ROOT"

BUCKETS=(asseta-evidence asseta-mlflow)
DATABASES=(asseta keycloak mlflow)

require_cmd docker
require_cmd sha256sum
require_compose_v2
require_env_file

BACKUP_ROOT="$(cfg BACKUP_ROOT /home/asseta/backups)"
BACKUP_RETENTION_DAYS="$(cfg BACKUP_RETENTION_DAYS 7)"
BACKUP_REMOTE="$(cfg BACKUP_REMOTE "")"
[[ "$BACKUP_RETENTION_DAYS" =~ ^[0-9]+$ && "$BACKUP_RETENTION_DAYS" -ge 1 ]] || fail "BACKUP_RETENTION_DAYS must be >= 1"

umask 077
mkdir -p "$BACKUP_ROOT"
LOCK_DIR="$BACKUP_ROOT/.backup.lock"
mkdir "$LOCK_DIR" 2>/dev/null || fail "Another backup is running (remove $LOCK_DIR if it is stale)."
TS="$(date -u +%Y%m%dT%H%M%SZ)"
DIR="$BACKUP_ROOT/$TS"
COMPLETE=0
cleanup() {
  rmdir "$LOCK_DIR" 2>/dev/null || true
  if [[ "$COMPLETE" != "1" && -d "$DIR" ]]; then
    mv "$DIR" "$DIR.failed" 2>/dev/null || true
    warn "Backup incomplete; partial files kept at $DIR.failed"
  fi
}
trap cleanup EXIT
mkdir -p "$DIR/objects"
started=$SECONDS

[[ "$(service_health postgres)" == "healthy" ]] || fail "postgres is not healthy"

for db in "${DATABASES[@]}"; do
  if [[ "$db" == mlflow ]] && [[ "$(compose exec -T postgres psql -U postgres -qAt -c \
    "SELECT 1 FROM pg_database WHERE datname = 'mlflow'" </dev/null)" != "1" ]]; then
    log "pg_dump mlflow: skipped (MLflow never enabled)"
    continue
  fi
  compose exec -T postgres pg_dump -U postgres -Fc "$db" >"$DIR/$db.dump"
  [[ -s "$DIR/$db.dump" ]] || fail "pg_dump $db produced an empty file"
  log "pg_dump $db: $(du -h "$DIR/$db.dump" | cut -f1)"
done
compose exec -T postgres psql -U postgres -d asseta -qAt -c 'SELECT version_num FROM alembic_version' \
  >"$DIR/alembic_version.txt"

# Keycloak config record (clients, groups, roles; secrets masked). The keycloak dump above is what gets restored.
if [[ "$(service_health keycloak)" == "healthy" ]]; then
  # shellcheck disable=SC2016 # expanded inside the container
  if compose exec -T keycloak bash -c 'set -e; CFG="$(mktemp /tmp/kcadm.XXXXXX)"; trap "rm -f \"$CFG\"" EXIT
      KC_CLI_PASSWORD="$KC_BOOTSTRAP_ADMIN_PASSWORD" /opt/keycloak/bin/kcadm.sh config credentials --config "$CFG" \
        --server http://localhost:8080/auth --realm master --user "$KC_BOOTSTRAP_ADMIN_USERNAME" >/dev/null 2>&1
      /opt/keycloak/bin/kcadm.sh create "realms/asseta/partial-export?exportClients=true&exportGroupsAndRoles=true" \
        --config "$CFG" -b "{}" -o' </dev/null >"$DIR/realm-asseta-partial-export.json" 2>/dev/null; then
    log "Keycloak realm config record: $(du -h "$DIR/realm-asseta-partial-export.json" | cut -f1)"
  else
    rm -f "$DIR/realm-asseta-partial-export.json"
    warn "Keycloak realm partial export failed (the keycloak database dump is still complete)"
  fi
fi

# MinIO mirror with the mc bundled in the pinned minio image, written straight into the backup directory.
# shellcheck disable=SC2016 # expanded by sh inside the container (credentials never leave it)
mirror_cmd='mc alias set src http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null'
for bucket in "${BUCKETS[@]}"; do
  mkdir -p "$DIR/objects/$bucket"
  # A bucket that was never created (asseta-mlflow while MLflow is disabled) is skipped, not an error.
  mirror_cmd+=" && if mc stat src/$bucket >/dev/null 2>&1; then mc mirror --quiet src/$bucket /backup/$bucket; fi"
done
# shellcheck disable=SC2016
mirror_cmd+='; rc=$?; mc alias rm src >/dev/null 2>&1; exit $rc'
compose run --rm --no-deps -T --user "$(id -u):$(id -g)" -e HOME=/tmp -v "$DIR/objects:/backup" \
  --entrypoint sh minio -c "$mirror_cmd" </dev/null
log "MinIO mirror: $(find "$DIR/objects" -type f | wc -l | tr -d ' ') objects, $(du -sh "$DIR/objects" | cut -f1)"

{
  printf 'created_utc=%s\n' "$TS"
  printf 'deploy_image_tag=%s\n' "$(state_get DEPLOY_IMAGE_TAG)"
  printf 'git_commit=%s\n' "$(git -C "$REPO_ROOT" rev-parse HEAD 2>/dev/null || echo unknown)"
  printf 'alembic_version=%s\n' "$(cat "$DIR/alembic_version.txt")"
  printf 'databases=%s\n' "${DATABASES[*]}"
  printf 'buckets=%s\n' "${BUCKETS[*]}"
} >"$DIR/MANIFEST"
sums="$(cd "$DIR" && find . -type f -print0 | sort -z | xargs -0 sha256sum)"
printf '%s\n' "$sums" >"$DIR/SHA256SUMS"
COMPLETE=1
log "Backup complete: $DIR ($(du -sh "$DIR" | cut -f1), $((SECONDS - started)) s)"

# Retention: only directories this script created (UTC timestamp names), never anything else under BACKUP_ROOT.
find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d \( -name '20[0-9][0-9][01][0-9][0-3][0-9]T[0-9][0-9][0-9][0-9][0-9][0-9]Z' \
  -o -name '20*Z.failed' \) -mmin "+$((BACKUP_RETENTION_DAYS * 1440))" -print | while IFS= read -r old; do
  rm -rf "$old"
  log "Removed expired backup $old"
done

if [[ -n "$BACKUP_REMOTE" ]]; then
  require_cmd rsync
  log "Copying to $BACKUP_REMOTE"
  rsync -a --partial "$DIR" "$BACKUP_REMOTE/" || fail "rsync to $BACKUP_REMOTE failed (local backup is complete)"
fi
