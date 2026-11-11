#!/usr/bin/env bash
# Add one company's starter reason lists (customer hours, engine hours, cash, revenue) from a JSON file, with audit
# events. Entries already there are skipped; nothing existing is changed.
# Keep the company's file on the server; deploy/reason-lists.example.json is a starting list.
#
#   scripts/seed-reason-lists.sh --registration-number 2026/10/0001 --file /home/asseta/mzalendo-reasons.json        dry run
#   scripts/seed-reason-lists.sh --registration-number 2026/10/0001 --file /home/asseta/mzalendo-reasons.json --yes  add
#   (--tenant-id UUID instead of --registration-number)
set -Eeuo pipefail

LOG_TAG=seed-reasons
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
[[ -n "$FILE" && -f "$FILE" ]] || fail "Give the reason lists file with --file (not found: ${FILE:-none})."
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
  -v "$FILE:/in/reasons.json:ro" \
  -e PYTHONDONTWRITEBYTECODE=1 \
  api /opt/asseta-seed/seed_reason_lists.py --file /in/reasons.json \
  --operator "${SUDO_USER:-${USER:-$(id -un)}}@$(hostname)" ${ARGS[@]+"${ARGS[@]}"}
