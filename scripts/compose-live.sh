#!/usr/bin/env bash
# `docker compose` for the production stack with the same files, project name, .env.production and deploy state
# (image tag, trusted proxy address) that scripts/deploy-live.sh uses, so manual commands never drift from it:
#
#   scripts/compose-live.sh ps
#   scripts/compose-live.sh logs -f --tail=200 api
#   scripts/compose-live.sh exec postgres psql -U postgres -d asseta
#
# Do not use it for `down -v` (destroys all data) or to `up` the app on another tag: use deploy-live.sh.
set -Eeuo pipefail
# shellcheck source-path=SCRIPTDIR source=lib/live-common.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/live-common.sh"
cd "$REPO_ROOT"
require_env_file
for arg in "$@"; do
  [[ "$arg" != "-v" && "$arg" != "--volumes" ]] || [[ "${1:-}" != "down" ]] ||
    fail "Refusing 'down $arg': it deletes every database, object and Kafka volume."
done
compose "$@"
