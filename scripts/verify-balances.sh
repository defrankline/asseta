#!/usr/bin/env bash
# Read-only balance verification on the live server: recomputes every balance of a tenant (customer hours per lot,
# engine hours per machine, cash per custodian, customer receivables) from its underlying records and prints the
# mismatches against every stored figure. The ledger prevails: nothing is changed, nothing is written.
#
#   scripts/verify-balances.sh --all
#   scripts/verify-balances.sh --registration-number 2026/10/0001
#   scripts/verify-balances.sh --tenant-id <uuid> [--json]
#
# Exit code 0: no mismatch. 1: at least one mismatch. 2: it could not run.
# Runs backend/scripts/verify_balances.py in a throwaway container of the deployed API image (READ ONLY transactions
# under the application's own database role, tenant by tenant).
set -Eeuo pipefail

LOG_TAG=verify-balances
# shellcheck source-path=SCRIPTDIR source=lib/live-common.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/live-common.sh"
cd "$REPO_ROOT"

[[ $# -ge 1 ]] || fail "Say which tenant: --all, --registration-number N or --tenant-id UUID (see the header of this script)"
require_cmd docker
require_compose_v2
require_env_file
case "$(service_health postgres)" in
  healthy) ;;
  *) fail "postgres is not healthy (scripts/compose-live.sh ps)" ;;
esac

status=0
compose run --rm --no-deps -T \
  --entrypoint python \
  -v "$REPO_ROOT/backend/scripts:/opt/asseta-verify:ro" \
  -e PYTHONDONTWRITEBYTECODE=1 \
  api /opt/asseta-verify/verify_balances.py "$@" || status=$?
exit "$status"
