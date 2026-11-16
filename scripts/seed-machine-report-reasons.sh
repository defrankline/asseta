#!/usr/bin/env bash
# Add the starting machine-report reasons (ADR-008: Transit between sites, Breakdown / repair, Servicing, Idle on site,
# Waiting for customer, Weather) to companies created before machine reports existed, with audit events. Entries a
# company already has are skipped; nothing existing is changed. A second run adds nothing. New companies get the list
# at onboarding.
#
#   scripts/seed-machine-report-reasons.sh                                          dry run, every company not closed
#   scripts/seed-machine-report-reasons.sh --yes                                    add them
#   scripts/seed-machine-report-reasons.sh --registration-number 2026/10/0001 --yes one company
#   (--tenant-id UUID instead of --registration-number)
set -Eeuo pipefail

LOG_TAG=seed-machine-report-reasons
# shellcheck source-path=SCRIPTDIR source=lib/live-common.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/live-common.sh"
cd "$REPO_ROOT"

case "${1:-}" in
  -h | --help)
    sed -n '2,/^set -Eeuo/p' "${BASH_SOURCE[0]}" | sed '$d' | sed -E 's/^# ?//'
    exit 0
    ;;
esac

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
  -e PYTHONDONTWRITEBYTECODE=1 \
  api /opt/asseta-seed/seed_machine_report_reasons.py \
  --operator "${SUDO_USER:-${USER:-$(id -un)}}@$(hostname)" "$@"
