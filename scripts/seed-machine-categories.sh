#!/usr/bin/env bash
# Add one company's machine types (categories) from a JSON file, with audit events. Names that already exist are skipped.
# Keep the company's file on the server; deploy/machine-categories.example.json is a starting list. No rates are created.
#
#   scripts/seed-machine-categories.sh --registration-number 2026/10/0001 --file /home/asseta/mzalendo-categories.json        dry run
#   scripts/seed-machine-categories.sh --registration-number 2026/10/0001 --file /home/asseta/mzalendo-categories.json --yes  add
#   (--tenant-id UUID instead of --registration-number)
set -Eeuo pipefail

LOG_TAG=seed-categories
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
[[ -n "$FILE" && -f "$FILE" ]] || fail "Give the machine types file with --file (not found: ${FILE:-none})."
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
  -v "$REPO_ROOT/backend/scripts:/opt/asseta-seed:ro" \
  -v "$FILE:/in/categories.json:ro" \
  -e PYTHONDONTWRITEBYTECODE=1 \
  api /opt/asseta-seed/seed_machine_categories.py --file /in/categories.json \
  --operator "${SUDO_USER:-${USER:-$(id -un)}}@$(hostname)" ${ARGS[@]+"${ARGS[@]}"}
