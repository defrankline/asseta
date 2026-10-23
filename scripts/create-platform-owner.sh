#!/usr/bin/env bash
# Creates the first platform owner in Keycloak (realm asseta, group /platform/platform-owner). Production has no demo
# data and no seeded users; this is the only supported way to create the first human account.
#
#   scripts/create-platform-owner.sh EMAIL "First" "Last" [--no-totp]
#
# Runs kcadm.sh inside the keycloak container with the admin credentials already in that container's environment
# (nothing secret goes on a command line or into logs). The user gets a generated temporary password plus the
# required actions UPDATE_PASSWORD and CONFIGURE_TOTP (authenticator app; skip with --no-totp). The temporary
# password is printed once, to this terminal only. If a user with that e-mail already exists nothing is changed.
set -Eeuo pipefail

LOG_TAG=platform-owner
# shellcheck source-path=SCRIPTDIR source=lib/live-common.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/live-common.sh"
cd "$REPO_ROOT"

usage() {
  fail "Usage: $0 EMAIL \"First\" \"Last\" [--no-totp]"
}

[[ $# -ge 3 ]] || usage
EMAIL="$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')"
FIRST_NAME="$2"
LAST_NAME="$3"
REQUIRE_TOTP=1
[[ "${4:-}" == "--no-totp" ]] && REQUIRE_TOTP=0
[[ $# -le 3 || "${4:-}" == "--no-totp" ]] || usage
[[ "$EMAIL" =~ ^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$ ]] || fail "Not an e-mail address: $EMAIL"
[[ -n "$FIRST_NAME" && -n "$LAST_NAME" ]] || usage

require_cmd docker
require_compose_v2
require_env_file
[[ "$(service_health keycloak)" == "healthy" ]] || fail "Keycloak is not healthy; deploy first (scripts/deploy-live.sh)."

# 24 characters from [A-Za-z0-9] (~143 bits); the realm policy needs >= 12 and not the username/e-mail.
TEMP_PASSWORD="$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 24 || true)"
[[ ${#TEMP_PASSWORD} -eq 24 ]] || fail "Could not generate a password"

if [[ "$REQUIRE_TOTP" == "1" ]]; then
  ACTIONS='["UPDATE_PASSWORD","CONFIGURE_TOTP"]'
else
  ACTIONS='["UPDATE_PASSWORD"]'
fi

# The script runs inside the container from stdin, so the password never appears in any process argument list.
# Every kcadm call except the one fed through a pipe reads /dev/null, so none of them can swallow this script.
inner_script() {
  printf 'EMAIL=%q\nFIRST_NAME=%q\nLAST_NAME=%q\nACTIONS=%q\nTEMP_PASSWORD=%q\n' \
    "$EMAIL" "$FIRST_NAME" "$LAST_NAME" "$ACTIONS" "$TEMP_PASSWORD"
  cat <<'INNER'
set -euo pipefail
KCADM=/opt/keycloak/bin/kcadm.sh
CFG="$(mktemp /tmp/kcadm.XXXXXX)"
trap 'rm -f "$CFG"' EXIT
kc() { "$KCADM" "$@" --config "$CFG"; }
KC_CLI_PASSWORD="$KC_BOOTSTRAP_ADMIN_PASSWORD" "$KCADM" config credentials --config "$CFG" \
  --server http://localhost:8080/auth --realm master --user "$KC_BOOTSTRAP_ADMIN_USERNAME" </dev/null >/dev/null 2>&1 \
  || { echo "RESULT=ADMIN_LOGIN_FAILED"; exit 0; }
existing="$(kc get users -r asseta -q email="$EMAIL" -q exact=true --fields id --format csv --noquotes </dev/null)"
if [ -z "$existing" ]; then
  existing="$(kc get users -r asseta -q username="$EMAIL" -q exact=true --fields id --format csv --noquotes </dev/null)"
fi
if [ -n "$existing" ]; then echo "RESULT=EXISTS"; exit 0; fi
group_id="$(kc get group-by-path/platform/platform-owner -r asseta --fields id --format csv --noquotes </dev/null 2>/dev/null || true)"
if [ -z "$group_id" ]; then echo "RESULT=NO_GROUP"; exit 0; fi
user_id="$(kc create users -r asseta -s username="$EMAIL" -s email="$EMAIL" -s firstName="$FIRST_NAME" \
  -s lastName="$LAST_NAME" -s enabled=true -s emailVerified=true -s "requiredActions=$ACTIONS" -i </dev/null)"
printf '{"type":"password","value":"%s","temporary":true}' "$TEMP_PASSWORD" |
  kc update "users/$user_id/reset-password" -r asseta -f - >/dev/null
kc update "users/$user_id/groups/$group_id" -r asseta -s realm=asseta -s "userId=$user_id" -s "groupId=$group_id" -n \
  </dev/null >/dev/null
echo "RESULT=CREATED"
echo "USER_ID=$user_id"
INNER
}

log "Creating platform owner $EMAIL in realm asseta"
output="$(inner_script | compose exec -T keycloak bash -s 2>&1)" || {
  printf '%s\n' "$output" | grep -v -i password >&2 || true
  fail "kcadm failed inside the keycloak container"
}

case "$output" in
  *RESULT=EXISTS*)
    log "A user with e-mail/username $EMAIL already exists; nothing was changed."
    log "To reset it: Keycloak admin console (SSH tunnel, docs/deployment-live.md) -> Users -> Credentials."
    exit 0
    ;;
  *RESULT=NO_GROUP*) fail "Group /platform/platform-owner not found in realm asseta (was the realm imported?)." ;;
  *RESULT=ADMIN_LOGIN_FAILED*) fail "kcadm could not log in to the master realm with the bootstrap admin credentials." ;;
  *RESULT=CREATED*) ;;
  *) fail "Unexpected kcadm output; check 'scripts/compose-live.sh logs keycloak'." ;;
esac

user_id="$(printf '%s\n' "$output" | sed -n 's/^USER_ID=//p')"
log "Created user $user_id in /platform/platform-owner (required actions: $ACTIONS)"

# The password goes to the controlling terminal only (not to stdout, so it never lands in a redirected log).
if { : >/dev/tty; } 2>/dev/null; then
  {
    printf '\n  Sign in at %s as %s\n' "$(cfg ASSETA_WEB_URL https://asseta.co.tz)" "$EMAIL"
    printf '  Temporary password (shown once, not stored anywhere): %s\n' "$TEMP_PASSWORD"
    printf '  Keycloak asks for a new password%s at the first sign-in.\n\n' \
      "$([[ "$REQUIRE_TOTP" == "1" ]] && printf ' and an authenticator app (TOTP)')"
  } >/dev/tty
else
  warn "No terminal attached: the temporary password was NOT shown. Reset it in the Keycloak admin console,"
  warn "or delete the user there and run this script again from an interactive SSH session."
fi
