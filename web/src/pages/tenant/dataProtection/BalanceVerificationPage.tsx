import PlayArrow from '@mui/icons-material/PlayArrow';
import { Alert, Button, Typography } from '@mui/material';
import { useCallback, useState } from 'react';
import { Can } from '../../../access/Can';
import { PERMISSIONS } from '../../../access/permissionCodes';
import {
  dataProtectionService,
  type VerificationFindingDto,
  type VerificationRunSummaryDto,
} from '../../../api/services/dataProtectionService';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import { StaticTable } from '../../../components/data/StaticTable';
import type { FetchPage } from '../../../components/data/useServerPage';
import { StatusChip, type StatusTone } from '../../../components/display/StatusChip';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { useNotify } from '../../../notifications/useNotify';
import { formatInstantIn } from '../../../utils/time';

const TONES: Readonly<Record<string, StatusTone>> = { MATCHED: 'success', MISMATCHES: 'error' };
const CHECK_LABELS: Readonly<Record<string, string>> = {
  CUSTOMER_HOURS_LOT: 'Customer hours per lot',
  ENGINE_HOURS: 'Engine hours per machine',
  DAILY_REPORT: 'Daily report figures',
  CASH_CUSTODY: 'Cash per custodian',
  CUSTOMER_RECEIVABLE: 'Customer receivables',
  INVOICE_TOTAL: 'Invoice totals',
  // DEC-033: each fund's balance recomputed and compared with its last count and adjustment.
  PETTY_CASH_FUND: 'Petty cash per fund',
};

const FINDING_COLUMNS: DataColumn<VerificationFindingDto>[] = [
  { id: 'check', header: 'Balance', render: (f) => CHECK_LABELS[f.check] ?? f.check },
  { id: 'subject', header: 'Record', render: (f) => f.label },
  { id: 'ledger', header: 'From the records', align: 'right', render: (f) => f.ledger_value },
  { id: 'stored', header: 'Stored figure', align: 'right', render: (f) => f.stored_value },
  { id: 'diff', header: 'Difference', align: 'right', render: (f) => f.difference },
  { id: 'source', header: 'Which figure', render: (f) => f.source },
];

function RunFindings({ runId }: { runId: string }) {
  const load = useCallback(
    (signal: AbortSignal) => dataProtectionService.getRun(runId, signal),
    [runId],
  );
  const run = useAsyncResource(load, [runId]);
  return (
    <AsyncContent resource={run}>
      {(data) =>
        data.findings.length === 0 ? (
          <Typography variant="body2">
            Every stored figure matches its underlying records.
          </Typography>
        ) : (
          <>
            <Alert severity="warning" className="mb-2">
              The records are the source of truth: the figures below were not changed.
              {data.findings_truncated ? ' Only the first findings are listed.' : ''}
            </Alert>
            <StaticTable
              columns={FINDING_COLUMNS}
              rows={data.findings}
              ariaLabel="Balance verification findings"
              getRowId={(f) => `${f.check}-${f.subject_id}-${f.source}`}
            />
          </>
        )
      }
    </AsyncContent>
  );
}

/**
 * Recomputes every balance (customer hours per lot, engine hours per machine, cash per custodian,
 * customer receivables, petty cash per fund) from its records and lists any stored figure that differs.
 * The records prevail: nothing is changed here.
 */
export function BalanceVerificationPage() {
  const notify = useNotify();
  const timeZone = useDisplayTimeZone();
  const [reloadKey, setReloadKey] = useState(0);
  const [running, setRunning] = useState(false);
  const fetchPage = useCallback<FetchPage<VerificationRunSummaryDto>>(
    (query, signal) => dataProtectionService.listRuns(query, signal),
    [],
  );
  const runNow = () => {
    setRunning(true);
    dataProtectionService
      .runNow()
      .then((run) => {
        notify.success(
          run.mismatch_count === 0
            ? 'All balances match their records.'
            : `${String(run.mismatch_count)} difference(s) found.`,
        );
        setReloadKey((k) => k + 1);
      })
      .catch(() => {
        notify.error('The verification could not be run.');
      })
      .finally(() => {
        setRunning(false);
      });
  };
  const columns: DataColumn<VerificationRunSummaryDto>[] = [
    { id: 'at', header: 'When', render: (r) => formatInstantIn(r.started_at, timeZone) },
    { id: 'trigger', header: 'Started by', render: (r) => TRIGGER_LABELS[r.trigger] ?? r.trigger },
    {
      id: 'outcome',
      header: 'Result',
      render: (r) => <StatusChip status={r.outcome} tones={TONES} />,
    },
    { id: 'checked', header: 'Balances checked', align: 'right', render: (r) => r.checked_count },
    { id: 'mismatches', header: 'Differences', align: 'right', render: (r) => r.mismatch_count },
  ];
  return (
    <>
      <PageHeader
        title="Balance verification"
        subtitle="Compare every balance with the records it comes from"
        actions={
          <Can permission={PERMISSIONS.tenantBalanceVerify}>
            <Button
              variant="contained"
              startIcon={<PlayArrow />}
              onClick={runNow}
              disabled={running}
            >
              Verify now
            </Button>
          </Can>
        }
      />
      <ServerDataTable
        columns={columns}
        fetchPage={fetchPage}
        getRowId={(r) => r.id}
        reloadKey={reloadKey}
        renderDetail={(r) => <RunFindings runId={r.id} />}
        detailLabel={() => 'Show findings'}
        emptyTitle="No verification has been run"
        emptyDescription="Run a verification to compare every balance with its records."
      />
    </>
  );
}

const TRIGGER_LABELS: Readonly<Record<string, string>> = {
  MANUAL: 'A person',
  SCHEDULED: 'Scheduled check',
  PLATFORM: 'Platform support',
};
