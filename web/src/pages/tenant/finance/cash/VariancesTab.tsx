import { Box, Link } from '@mui/material';
import { useCallback, useEffect, useState, type ReactNode } from 'react';
import { Link as RouterLink } from 'react-router';
import { PERMISSIONS } from '../../../../access/permissionCodes';
import { useMutationGuard } from '../../../../access/useCanMutate';
import { custodyService } from '../../../../api/services/custodyService';
import type { CashVarianceDto, CustodianDto } from '../../../../api/custodyTypes';
import { ServerDataTable, type DataColumn } from '../../../../components/data/ServerDataTable';
import type { FetchPage } from '../../../../components/data/useServerPage';
import { KeyValueGrid } from '../../../../components/display/KeyValueGrid';
import { MoneyText } from '../../../../components/display/MoneyText';
import { StatusChip } from '../../../../components/display/StatusChip';
import { StaticSelectFilter } from '../../../../components/forms/StaticSelectFilter';
import { ActionButtons } from '../../../../components/lifecycle/ActionButtons';
import { DetailsDrawer } from '../../../../components/lifecycle/DetailsDrawer';
import { RowActionsMenu } from '../../../../components/lifecycle/RowActionsMenu';
import type { RowAction } from '../../../../components/lifecycle/rowActions';
import { caseDetailPath, cashTabPath } from '../../../../navigation/routes';
import { useNotify } from '../../../../notifications/useNotify';
import { useSession } from '../../../../session/useSession';
import { formatInstantIn } from '../../../../utils/time';
import { DecisionDialog } from '../../shared/DecisionDialog';
import { PersonName } from '../../shared/PersonName';
import { useMyUserId } from '../../shared/useFinanceLabels';
import {
  OWN_REQUEST_TOOLTIP,
  VARIANCE_OUTCOME_LABELS,
  VARIANCE_SOURCE_LABELS,
  VARIANCE_SOURCE_OPTIONS,
  VARIANCE_STATUS_LABELS,
  VARIANCE_STATUS_OPTIONS,
  VARIANCE_STATUS_TONES,
} from './custodyDisplay';
import { ResolveVarianceDialog, WriteOffProposalDialog } from './VarianceDialogs';
import { useCashPolicy, useCustodianLabels } from './custodyHooks';
import { CustodianFilter } from './custodyPickers';

type Open =
  | { kind: 'resolve'; v: CashVarianceDto }
  | { kind: 'propose'; v: CashVarianceDto }
  | { kind: 'decide'; v: CashVarianceDto }
  | null;

const chip = (v: CashVarianceDto) => (
  <StatusChip
    status={v.status}
    tones={VARIANCE_STATUS_TONES}
    label={VARIANCE_STATUS_LABELS[v.status]}
  />
);

/** Where the record that opened a variance is listed. */
const sourcePath = (v: CashVarianceDto) =>
  v.source_type === 'TRANSFER'
    ? cashTabPath('transfers', { id: v.source_id })
    : v.source_type === 'REMITTANCE'
      ? cashTabPath('handovers')
      : cashTabPath('floats');

/** Declared ≠ received differences: resolve, or propose / decide a write-off (never your own). */
export function VariancesTab({
  timeZone,
  initialStatus,
  focusId = null,
}: {
  timeZone: string;
  initialStatus?: string | undefined;
  focusId?: string | null;
}) {
  const notify = useNotify();
  const me = useMyUserId();
  const can = useMutationGuard();
  const { hasPermission } = useSession();
  const policy = useCashPolicy();
  const custodian = useCustodianLabels();
  const [status, setStatus] = useState(initialStatus ?? 'OPEN');
  const [source, setSource] = useState('');
  const [who, setWho] = useState<CustodianDto | null>(null);
  const [viewing, setViewing] = useState<CashVarianceDto | null>(null);
  const [open, setOpen] = useState<Open>(null);
  const [reloadKey, setReloadKey] = useState(0);
  useEffect(() => {
    if (focusId === null) return undefined;
    const controller = new AbortController();
    custodyService.variance(focusId, controller.signal).then(setViewing, () => {
      // The list stays usable when the linked variance cannot be opened.
    });
    return () => {
      controller.abort();
    };
  }, [focusId]);
  const fetchPage = useCallback<FetchPage<CashVarianceDto>>(
    (query, signal) => custodyService.variances(query, signal),
    [],
  );
  const canResolve = can(PERMISSIONS.tenantFinanceVariance);
  const canWriteOff = can(PERMISSIONS.tenantFinanceWriteoff);
  const approvalNeeded = policy?.writeoffRequiresApproval ?? true;
  const actionsFor = (v: CashVarianceDto, inDrawer: boolean): RowAction[] => {
    const go = (kind: 'resolve' | 'propose' | 'decide') => () => {
      setViewing(null);
      setOpen({ kind, v });
    };
    const proposedByMe = v.proposed_by !== null && v.proposed_by === me;
    return [
      ...(inDrawer
        ? []
        : [
            {
              key: 'view',
              label: 'View details',
              onClick: () => {
                setViewing(v);
              },
            },
          ]),
      {
        key: 'resolve',
        label: 'Resolve',
        hidden: !canResolve || v.status !== 'OPEN',
        onClick: go('resolve'),
      },
      {
        key: 'propose',
        label: 'Propose write-off',
        hidden: !canResolve || v.status !== 'OPEN' || !approvalNeeded,
        onClick: go('propose'),
      },
      {
        key: 'decide',
        label: proposedByMe
          ? `Approve / reject write-off (${OWN_REQUEST_TOOLTIP})`
          : 'Approve / reject write-off',
        hidden: !canWriteOff || v.status !== 'WRITE_OFF_PROPOSED',
        disabled: proposedByMe,
        disabledReason: OWN_REQUEST_TOOLTIP,
        onClick: go('decide'),
      },
    ];
  };
  const columns: DataColumn<CashVarianceDto>[] = [
    { id: 'at', header: 'Opened', render: (v) => formatInstantIn(v.opened_at, timeZone) },
    { id: 'source', header: 'From', render: (v) => VARIANCE_SOURCE_LABELS[v.source_type] },
    { id: 'who', header: 'Accountable custodian', render: (v) => custodian(v.staff_member_id) },
    { id: 'status', header: 'Status', render: chip },
    {
      id: 'outcome',
      header: 'Outcome',
      render: (v) => (v.outcome === null ? '—' : VARIANCE_OUTCOME_LABELS[v.outcome]),
    },
    {
      id: 'declared',
      header: 'Declared',
      align: 'right',
      render: (v) => <MoneyText amount={v.declared_amount} currency={v.currency} />,
    },
    {
      id: 'received',
      header: 'Received',
      align: 'right',
      render: (v) => <MoneyText amount={v.received_amount} currency={v.currency} />,
    },
    {
      id: 'difference',
      header: 'Difference',
      align: 'right',
      render: (v) => <MoneyText amount={v.amount} currency={v.currency} strong />,
    },
    {
      id: 'actions',
      header: '',
      align: 'right',
      render: (v) => (
        <RowActionsMenu
          label={`variance of ${custodian(v.staff_member_id)}`}
          actions={actionsFor(v, false)}
        />
      ),
    },
  ];
  const done = (message: string) => {
    notify.success(message);
    setReloadKey((k) => k + 1);
  };
  const close = () => {
    setOpen(null);
  };
  let dialog: ReactNode = null;
  if (open?.kind === 'resolve') {
    dialog = (
      <ResolveVarianceDialog
        variance={open.v}
        custodian={custodian(open.v.staff_member_id)}
        allowWriteOff={!approvalNeeded && canWriteOff}
        onDone={() => {
          done('Variance resolved.');
        }}
        onClose={close}
      />
    );
  } else if (open?.kind === 'propose') {
    dialog = (
      <WriteOffProposalDialog
        variance={open.v}
        custodian={custodian(open.v.staff_member_id)}
        onDone={() => {
          done('Write-off proposed; someone else with the write-off permission decides.');
        }}
        onClose={close}
      />
    );
  } else if (open?.kind === 'decide') {
    const v = open.v;
    dialog = (
      <DecisionDialog<CashVarianceDto>
        title="Decide write-off"
        kind="approve"
        summary={
          <KeyValueGrid
            columns={2}
            items={[
              { label: 'Accountable custodian', value: custodian(v.staff_member_id) },
              {
                label: 'Difference',
                value: <MoneyText amount={v.amount} currency={v.currency} strong />,
              },
              { label: 'Proposed by', value: <PersonName userId={v.proposed_by} /> },
              { label: 'Explanation', value: v.proposal_note ?? '—' },
            ]}
          />
        }
        explanation="Approving resolves the variance as written off and lowers the custodian's expected balance by the difference. Rejecting returns it to open."
        onDecide={(approve, note, key) =>
          custodyService.decideWriteOff(v.id, { approve, note }, key)
        }
        onDone={(r) => {
          done(
            r.status === 'RESOLVED'
              ? 'Write-off approved.'
              : 'Write-off rejected; the variance is open again.',
          );
        }}
        onClose={close}
      />
    );
  }
  return (
    <Box className="flex flex-col gap-3">
      <ServerDataTable
        columns={columns}
        fetchPage={fetchPage}
        getRowId={(v) => v.id}
        searchable={false}
        reloadKey={reloadKey}
        filters={{
          status: status || undefined,
          source_type: source || undefined,
          staff_member_id: who?.staff_member_id,
        }}
        emptyTitle="No variances"
        isRowMuted={(v) => v.status === 'RESOLVED'}
        onRowClick={setViewing}
        toolbar={
          <Box className="flex flex-wrap items-center gap-3">
            <StaticSelectFilter
              label="Status"
              value={status}
              options={VARIANCE_STATUS_OPTIONS}
              onChange={setStatus}
            />
            <StaticSelectFilter
              label="From"
              value={source}
              options={VARIANCE_SOURCE_OPTIONS}
              onChange={setSource}
            />
            <Box sx={{ minWidth: 240 }}>
              <CustodianFilter value={who} onChange={setWho} />
            </Box>
          </Box>
        }
      />
      {viewing !== null && (
        <DetailsDrawer
          title="Cash variance"
          status={chip(viewing)}
          actions={<ActionButtons actions={actionsFor(viewing, true)} />}
          onClose={() => {
            setViewing(null);
          }}
        >
          <KeyValueGrid
            columns={2}
            items={[
              {
                label: 'From',
                value: (
                  <Link component={RouterLink} to={sourcePath(viewing)}>
                    {VARIANCE_SOURCE_LABELS[viewing.source_type]}
                  </Link>
                ),
              },
              { label: 'Accountable custodian', value: custodian(viewing.staff_member_id) },
              {
                label: 'Other custodian',
                value: custodian(viewing.counterparty_staff_id),
              },
              {
                label: 'Declared',
                value: <MoneyText amount={viewing.declared_amount} currency={viewing.currency} />,
              },
              {
                label: 'Received',
                value: <MoneyText amount={viewing.received_amount} currency={viewing.currency} />,
              },
              {
                label: 'Difference',
                value: <MoneyText amount={viewing.amount} currency={viewing.currency} strong />,
              },
              { label: 'Opened', value: formatInstantIn(viewing.opened_at, timeZone) },
              {
                label: 'Opened by',
                value: <PersonName userId={viewing.opened_by} empty="Automatically" />,
              },
              {
                label: 'Investigation',
                value:
                  viewing.case_id === null ? (
                    '—'
                  ) : hasPermission(PERMISSIONS.tenantCaseRead) ? (
                    <Link component={RouterLink} to={caseDetailPath(viewing.case_id)}>
                      Open investigation
                    </Link>
                  ) : (
                    'Opened'
                  ),
              },
              {
                label: 'Write-off proposed by',
                value: <PersonName userId={viewing.proposed_by} />,
              },
              { label: 'Proposal', value: viewing.proposal_note ?? '—' },
              {
                label: 'Outcome',
                value: viewing.outcome === null ? '—' : VARIANCE_OUTCOME_LABELS[viewing.outcome],
              },
              { label: 'Resolved by', value: <PersonName userId={viewing.resolved_by} /> },
              {
                label: 'Resolved at',
                value:
                  viewing.resolved_at === null
                    ? '—'
                    : formatInstantIn(viewing.resolved_at, timeZone),
              },
              { label: 'Resolution note', value: viewing.resolution_note ?? '—' },
            ]}
          />
        </DetailsDrawer>
      )}
      {dialog}
    </Box>
  );
}
