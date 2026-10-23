#!/usr/bin/env bash
# One-time (idempotent): serve Keycloak's master realm — the admin console's own login — at the SSH-tunnel address
# instead of the public hostname. nginx blocks /auth/admin and the master realm publicly, so without this the admin
# console opened through `ssh -L 5021:127.0.0.1:5021 …` times out ("3rd party check iframe"). The tenant-facing
# `asseta` realm keeps the public https://asseta.co.tz/auth issuer.
#
# Usage (on the server, from /home/asseta): scripts/keycloak-admin-tunnel.sh
# Then: ssh -L 5021:127.0.0.1:5021 <server> and open http://localhost:5021/auth/admin/
set -Eeuo pipefail

# shellcheck source-path=SCRIPTDIR source=lib/live-common.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/live-common.sh"
cd "$REPO_ROOT"
require_env_file

port="$(cfg ASSETA_KEYCLOAK_HOST_PORT 5021)"
url="http://localhost:${port}/auth"
# Credentials come from the keycloak container's own environment; nothing is echoed or written outside /tmp in it.
# shellcheck disable=SC2016  # the script below expands inside the container, on purpose
compose exec -T -e ADMIN_FRONTEND_URL="$url" keycloak bash -c '
  K=/opt/keycloak/bin/kcadm.sh; C="$(mktemp /tmp/kcadm.XXXXXX)"
  trap "rm -f \"$C\"" EXIT
  "$K" config credentials --config "$C" --server http://localhost:8080/auth --realm master \
    --user "$KC_BOOTSTRAP_ADMIN_USERNAME" --password "$KC_BOOTSTRAP_ADMIN_PASSWORD" >/dev/null
  "$K" update realms/master --config "$C" -s "attributes.frontendUrl=$ADMIN_FRONTEND_URL"
' </dev/null
log "Master realm (admin console login) now served at $url — open it through the SSH tunnel."
