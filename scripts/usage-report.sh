#!/usr/bin/env bash
# Read-only usage report for the live server: which features have actually been used, so a menu or module is judged by
# evidence before anyone removes it. It runs inside one READ ONLY transaction as the postgres superuser (row-level
# security would otherwise hide tenant rows). It changes nothing and prints counts only, never record contents.
#
#   scripts/usage-report.sh              activity over the last 30 days
#   scripts/usage-report.sh --days 90
#   scripts/usage-report.sh > usage.txt
set -Eeuo pipefail

LOG_TAG=usage
# shellcheck source-path=SCRIPTDIR source=lib/live-common.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/live-common.sh"
cd "$REPO_ROOT"

DAYS=30
while [[ $# -gt 0 ]]; do
  case "$1" in
    --days)
      DAYS="${2:-}"
      shift 2
      ;;
    *) fail "Unknown option: $1 (usage: scripts/usage-report.sh [--days N])" ;;
  esac
done
[[ "$DAYS" =~ ^[0-9]+$ && "$DAYS" -ge 1 ]] || fail "--days must be a whole number of at least 1"

require_cmd docker
require_compose_v2
require_env_file

compose exec -T postgres psql -U postgres -d asseta -q -v ON_ERROR_STOP=1 -v days="$DAYS" <<'SQL'
BEGIN READ ONLY;

\echo
\echo === Actions people performed in the period (from the audit log), most used first ===
SELECT split_part(action, '.', 1) || '.' || split_part(action, '.', 2) AS feature,
       count(*) AS actions,
       count(DISTINCT actor_user_id) AS people,
       count(DISTINCT tenant_id) AS companies,
       max(occurred_at)::date AS last_used
FROM audit_event
WHERE occurred_at >= now() - make_interval(days => :days)
GROUP BY 1
ORDER BY 2 DESC, 1;

\echo
\echo === Tables by number of rows (row_count 0 at the end = never used) ===
WITH t AS (
  SELECT c.table_name,
         (SELECT x.column_name FROM information_schema.columns x
           WHERE x.table_schema = 'public' AND x.table_name = c.table_name
             AND x.column_name IN ('updated_at', 'occurred_at', 'created_at')
           ORDER BY x.column_name DESC LIMIT 1) AS ts,
         EXISTS (SELECT 1 FROM information_schema.columns y
                  WHERE y.table_schema = 'public' AND y.table_name = c.table_name
                    AND y.column_name = 'tenant_id') AS scoped
    FROM information_schema.tables c
   WHERE c.table_schema = 'public' AND c.table_type = 'BASE TABLE'
)
SELECT table_name,
       (xpath('/row/c/text()', query_to_xml(format('select count(*) c from %I', table_name), false, true, '')))[1]::text::bigint AS row_count,
       CASE WHEN scoped THEN (xpath('/row/c/text()', query_to_xml(format('select count(distinct tenant_id) c from %I', table_name), false, true, '')))[1]::text::bigint END AS companies,
       CASE WHEN ts IS NOT NULL THEN left((xpath('/row/m/text()', query_to_xml(format('select max(%I) m from %I', ts, table_name), false, true, '')))[1]::text, 10) END AS last_activity
  FROM t
 ORDER BY row_count DESC, last_activity DESC NULLS LAST, table_name;

\echo
\echo === Company policy settings saved, by type ===
SELECT policy_type, count(DISTINCT tenant_id) AS companies, max(created_at)::date AS last_changed
  FROM policy_version WHERE tenant_id IS NOT NULL
 GROUP BY 1 ORDER BY 1;

\echo
\echo === Saved notifications still linking to old pages ===
SELECT split_part(link, '?', 1) AS link, count(*) AS notifications, max(created_at)::date AS newest
  FROM notification
 WHERE link LIKE '/tenant/cash%' OR link LIKE '/tenant/finance?tab=%' OR link LIKE '/tenant/finance/cash?%id=%'
 GROUP BY 1 ORDER BY 2 DESC;

ROLLBACK;
SQL
