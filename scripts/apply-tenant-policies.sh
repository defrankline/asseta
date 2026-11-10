#!/usr/bin/env bash
# Apply one company's policy settings from a JSON file (the same change as Administration -> Policies -> New override:
# new company policy versions, validated, with a reason and audit events). Keep the company's file on the server; see
# deploy/tenant-policies.example.json for the format.
#
#   scripts/apply-tenant-policies.sh --registration-number 2026/10/0001 --file /home/asseta/mzalendo.json        dry run
#   scripts/apply-tenant-policies.sh --registration-number 2026/10/0001 --file /home/asseta/mzalendo.json --yes  apply
#   (--tenant-id UUID instead of --registration-number)
#
# A second run changes nothing: settings already at the wanted value are skipped.
set -Eeuo pipefail

LOG_TAG=apply-policies
# shellcheck source-path=SCRIPTDIR source=lib/live-common.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/live-common.sh"
cd "$REPO_ROOT"

ARGS=()
FILE=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h | --help)
      sed -n '2,/^set -Eeuo/p' "${BASH_SOURCE[0]}" | sed '$d' | sed -E 's/^# ?//'
      exit 0
      ;;
    --file)
      FILE="${2:-}"
      shift 2
      ;;
    *)
      ARGS+=("$1")
      shift
      ;;
  esac
done
[[ -n "$FILE" && -f "$FILE" ]] || fail "Give the settings file with --file (not found: ${FILE:-none})."
FILE="$(cd "$(dirname "$FILE")" && pwd)/$(basename "$FILE")"

require_cmd docker
require_compose_v2
require_env_file
case "$(service_health api)" in
  healthy | running) ;;
  *) fail "The api service is not running (scripts/compose-live.sh ps); deploy first." ;;
esac

compose run --rm --no-deps -T \
  --user "$(id -u):$(id -g)" \
  --entrypoint python \
  -v "$REPO_ROOT/backend/scripts:/opt/asseta-apply:ro" \
  -v "$FILE:/in/settings.json:ro" \
  -e PYTHONDONTWRITEBYTECODE=1 \
  api /opt/asseta-apply/apply_tenant_policies.py --file /in/settings.json \
  --operator "${SUDO_USER:-${USER:-$(id -un)}}@$(hostname)" ${ARGS[@]+"${ARGS[@]}"}
