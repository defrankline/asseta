import { Alert, Box, Button } from '@mui/material';
import { useCallback, useState, type ReactNode } from 'react';
import { PERMISSIONS } from '../../../../access/permissionCodes';
import { useMutationGuard } from '../../../../access/useCanMutate';
import { custodyService } from '../../../../api/services/custodyService';
import type { CashRetentionDto, CustodianDto } from '../../../../api/custodyTypes';
import { ServerDataTable, type DataColumn } from '../../../../components/data/ServerDataTable';
import type { FetchPage } from '../../../../components/data/useServerPage';
import { KeyValueGrid } from '../../../../components/display/KeyValueGrid';
import { MoneyText } from '../../../../components/display/MoneyText';
import { StatusChip } from '../../../../components/display/StatusChip';
import { StaticSelectFilter } from '../../../../components/forms/StaticSelectFilter';
import { RowActionsMenu } from '../../../../components/lifecycle/RowActionsMenu';
import { useNotify } from '../../../../notifications/useNotify';
import { formatInstantIn } from '../../../../utils/time';
import { DecisionDialog } from '../../shared/DecisionDialog';
import { PersonName } from '../../shared/PersonName';
import { useMyUserId } from '../../shared/useFinanceLabels';
import {
  DECISION_STATUS_LABELS,
  DECISION_STATUS_OPTIONS,
  DECISION_STATUS_TONES,
  OWN_REQUEST_TOOLTIP,
} from './custodyDisplay';
import { RetentionDialog } from './CustodyRequestDialogs';
import { useCashPolicy, useCustodianLabels } from './custodyHooks';
import { CustodianFilter } from './custodyPickers';

/** Requests to keep field cash instead of remitting it: request, approve / reject (never your own). */
export function RetentionsTab({
  timeZone,
  field = false,
  initialStatus,
}: {
  timeZone: string;
  initialStatus?: string | undefined;
  /** Field work: requests are for the caller's own custody unless office cash permission. */
  field?: boolean;
}) {
  const notify = useNotify();
  const me = useMyUserId();
  const can = useMutationGuard();
  const policy = useCashPolicy();
  const custodian = useCustodianLabels();
  const [status, setStatus] = useState(initialStatus ?? (field ? '' : 'PENDING'));
  const [who, setWho] = useState<CustodianDto | null>(null);
  const [deciding, setDeciding] = useState<CashRetentionDto | null>(null);
  const [requesting, setRequesting] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const fetchPage = useCallback<FetchPage<CashRetentionDto>>(
    (query, signal) => custodyService.retentions(query, signal),
    [],
  );
  const canDecide = can(PERMISSIONS.tenantFinanceRetentionApprove);
  const canRequest = can(PERMISSIONS.tenantCollectionRecord) || can(PERMISSIONS.tenantFinanceCash);
  const allowed = policy?.retentionAllowed ?? true;
  const columns: DataColumn<CashRetentionDto>[] = [
    { id: 'at', header: 'Requested', render: (r) => formatInstantIn(r.created_at, timeZone) },
    { id: 'who', header: 'Custodian', render: (r) => custodian(r.staff_member_id) },
    { id: 'reason', header: 'Reason', render: (r) => r.reason },
    {
      id: 'status',
      header: 'Status',
      render: (r) => (
        <StatusChip
          status={r.status}
          tones={DECISION_STATUS_TONES}
          label={DECISION_STATUS_LABELS[r.status]}
        />
      ),
    },
    {
      id: 'until',
      header: 'Valid until',
      render: (r) => (r.valid_until === null ? '—' : formatInstantIn(r.valid_until, timeZone)),
    },
    { id: 'by', header: 'Requested by', render: (r) => <PersonName userId={r.created_by} /> },
    { id: 'note', header: 'Decision note', render: (r) => r.decision_note ?? '—' },
    {
      id: 'amount',
      header: 'Amount',
      align: 'right',
      render: (r) => <MoneyText amount={r.amount} currency={r.currency} />,
    },
    {
      id: 'actions',
      header: '',
      align: 'right',
      render: (r) => {
        const mine = r.created_by !== null && r.created_by === me;
        return (
          <RowActionsMenu
            label={`retention of ${custodian(r.staff_member_id)}`}
            actions={[
              {
                key: 'decide',
                label: mine ? `Approve / reject (${OWN_REQUEST_TOOLTIP})` : 'Approve / reject',
                hidden: !canDecide || r.status !== 'PENDING',
                disabled: mine,
                disabledReason: OWN_REQUEST_TOOLTIP,
                onClick: () => {
                  setDeciding(r);
                },
              },
            ]}
          />
        );
      },
    },
  ];
  let dialog: ReactNode = null;
  if (deciding !== null) {
    const r = deciding;
    dialog = (
      <DecisionDialog<CashRetentionDto>
        title="Decide cash retention"
        kind="approve"
        summary={
          <KeyValueGrid
            columns={2}
            items={[
              { label: 'Custodian', value: custodian(r.staff_member_id) },
              {
                label: 'Amount to keep',
                value: <MoneyText amount={r.amount} currency={r.currency} strong />,
              },
              { label: 'Reason', value: r.reason },
              { label: 'Requested by', value: <PersonName userId={r.created_by} /> },
            ]}
          />
        }
        explanation="An approved retention lets the custodian keep this amount instead of remitting it; the full-remittance check allows for it."
        onDecide={(approve, note, key) =>
          custodyService.decideRetention(r.id, { approve, note }, key)
        }
        onDone={(res) => {
          notify.success(res.status === 'APPROVED' ? 'Retention approved.' : 'Retention rejected.');
          setReloadKey((k) => k + 1);
        }}
        onClose={() => {
          setDeciding(null);
        }}
      />
    );
  }
  return (
    <Box className="flex flex-col gap-3">
      {!allowed && (
        <Alert severity="info">
          Your organisation does not allow keeping cash: everything collected is remitted.
        </Alert>
      )}
      <ServerDataTable
        columns={columns}
        fetchPage={fetchPage}
        getRowId={(r) => r.id}
        searchable={false}
        reloadKey={reloadKey}
        filters={{ status: status || undefined, staff_member_id: who?.staff_member_id }}
        emptyTitle="No retention requests"
        isRowMuted={(r) => r.status === 'REJECTED'}
        toolbar={
          <Box className="flex flex-wrap items-center gap-3">
            <StaticSelectFilter
              label="Status"
              value={status}
              options={DECISION_STATUS_OPTIONS}
              onChange={setStatus}
            />
            <Box sx={{ minWidth: 240 }}>
              <CustodianFilter value={who} onChange={setWho} />
            </Box>
            {canRequest && allowed && (
              <Button
                variant="outlined"
                onClick={() => {
                  setRequesting(true);
                }}
              >
                Request to keep cash
              </Button>
            )}
          </Box>
        }
      />
      {requesting && (
        <RetentionDialog
          ownCustody={
            field &&
            !can(PERMISSIONS.tenantFinanceCash) &&
            policy?.recordersMayRecordForOthers !== true
          }
          timeZone={timeZone}
          onClose={() => {
            setRequesting(false);
          }}
          onRecorded={() => {
            notify.success('Request sent; someone else with the approval permission decides.');
            setReloadKey((k) => k + 1);
          }}
        />
      )}
      {dialog}
    </Box>
  );
}
