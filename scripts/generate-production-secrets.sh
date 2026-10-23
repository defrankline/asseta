#!/usr/bin/env bash
# Writes .env.production from .env.production.example with strong random values for every generated secret.
# The file is created with mode 600 and is never overwritten; no secret value is printed. External values
# (LETSENCRYPT_EMAIL, SMTP, NextSMS, FCM/APNs) stay as placeholders for the owner to fill in.
#
#   scripts/generate-production-secrets.sh [target-file]      (default: .env.production in the repo root)
set -Eeuo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXAMPLE="$REPO_ROOT/.env.production.example"
TARGET="${1:-$REPO_ROOT/.env.production}"

GENERATED_KEYS=(POSTGRES_SUPERUSER_PASSWORD ASSETA_OWNER_DB_PASSWORD ASSETA_APP_DB_PASSWORD KEYCLOAK_DB_PASSWORD
  MLFLOW_DB_PASSWORD KEYCLOAK_ADMIN_PASSWORD ASSETA_API_CLIENT_SECRET REDIS_PASSWORD MINIO_ROOT_PASSWORD
  ASSETA_TRACCAR_GATEWAY_KEY)

fail() {
  printf '[secrets:error] %s\n' "$*" >&2
  exit 1
}

# 48 hex characters (192 bits): safe in URLs, shell, compose env files and Keycloak placeholders without quoting.
random_secret() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 24
  else
    od -An -N24 -tx1 /dev/urandom | tr -d ' \n'
  fi
}

is_generated() {
  local key="$1" k
  for k in "${GENERATED_KEYS[@]}"; do
    [[ "$k" == "$key" ]] && return 0
  done
  return 1
}

[[ -f "$EXAMPLE" ]] || fail "Missing $EXAMPLE"
[[ ! -e "$TARGET" ]] || fail "$TARGET already exists; refusing to overwrite it (move it away first if you really mean to)."

umask 077
tmp="$(mktemp "$(dirname "$TARGET")/.env.production.XXXXXX")"
trap 'rm -f "$tmp"' EXIT

while IFS= read -r line || [[ -n "$line" ]]; do
  key="${line%%=*}"
  if [[ "$line" != \#* && "$line" == *=CHANGE_ME ]] && is_generated "$key"; then
    printf '%s=%s\n' "$key" "$(random_secret)"
  else
    printf '%s\n' "$line"
  fi
done <"$EXAMPLE" >"$tmp"

chmod 600 "$tmp"
mv "$tmp" "$TARGET"
trap - EXIT

printf '[secrets] Wrote %s (mode 600) with generated values for:\n' "$TARGET"
printf '  %s\n' "${GENERATED_KEYS[@]}"
remaining="$(grep -E '^[A-Z0-9_]+=CHANGE_ME$' "$TARGET" | cut -d= -f1 || true)"
if [[ -n "$remaining" ]]; then
  printf '[secrets] Fill in before deploying (deploy-live.sh refuses CHANGE_ME):\n'
  printf '%s\n' "$remaining" | sed 's/^/  /'
fi
printf '[secrets] Optional external providers (SMS, SMTP, push) stay on console until you set them.\n'
printf '[secrets] Keep an encrypted copy of this file off the server: it is not in git and not in the backups.\n'
