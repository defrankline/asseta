import { Box, Button } from '@mui/material';
import { useCallback, useState, type ReactNode } from 'react';
import { PERMISSIONS } from '../../../../access/permissionCodes';
import { useMutationGuard } from '../../../../access/useCanMutate';
import { custodyService } from '../../../../api/services/custodyService';
import type { CustodianDto, CustodyAdjustmentDto } from '../../../../api/custodyTypes';
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
  ADJUSTMENT_KIND_LABELS,
  DECISION_STATUS_LABELS,
  DECISION_STATUS_OPTIONS,
  DECISION_STATUS_TONES,
  entityTypeLabel,
  OWN_REQUEST_TOOLTIP,
} from './custodyDisplay';
import { AdjustmentDialog } from './CustodyRequestDialogs';
import { useCustodianLabels } from './custodyHooks';
import { CustodianFilter } from './custodyPickers';

/** Reversals and adjustments of a custodian's expected balance: propose, approve / reject (never your own). */
export function AdjustmentsTab({
  timeZone,
  initialStatus,
}: {
  timeZone: string;
  initialStatus?: string | undefined;
}) {
  const notify = useNotify();
  const me = useMyUserId();
  const can = useMutationGuard();
  const custodian = useCustodianLabels();
  const [status, setStatus] = useState(initialStatus ?? 'PENDING');
  const [who, setWho] = useState<CustodianDto | null>(null);
  const [deciding, setDeciding] = useState<CustodyAdjustmentDto | null>(null);
  const [proposing, setProposing] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const fetchPage = useCallback<FetchPage<CustodyAdjustmentDto>>(
    (query, signal) => custodyService.adjustments(query, signal),
    [],
  );
  const canDecide = can(PERMISSIONS.tenantFinanceAdjustmentApprove);
  const canPropose = can(PERMISSIONS.tenantFinanceCash);
  const columns: DataColumn<CustodyAdjustmentDto>[] = [
    { id: 'at', header: 'Effective', render: (a) => formatInstantIn(a.occurred_at, timeZone) },
    { id: 'who', header: 'Custodian', render: (a) => custodian(a.staff_member_id) },
    { id: 'kind', header: 'Kind', render: (a) => ADJUSTMENT_KIND_LABELS[a.kind] },
    {
      id: 'reverses',
      header: 'Record reversed',
      render: (a) =>
        a.reverses_entity_type === null ? '—' : entityTypeLabel(a.reverses_entity_type),
    },
    { id: 'reason', header: 'Reason', render: (a) => a.reason },
    {
      id: 'status',
      header: 'Status',
      render: (a) => (
        <StatusChip
          status={a.status}
          tones={DECISION_STATUS_TONES}
          label={DECISION_STATUS_LABELS[a.status]}
        />
      ),
    },
    { id: 'by', header: 'Proposed by', render: (a) => <PersonName userId={a.created_by} /> },
    {
      id: 'amount',
      header: 'Amount',
      align: 'right',
      render: (a) => <MoneyText amount={a.amount} currency={a.currency} />,
    },
    {
      id: 'actions',
      header: '',
      align: 'right',
      render: (a) => {
        const mine = a.created_by !== null && a.created_by === me;
        return (
          <RowActionsMenu
            label={`adjustment of ${custodian(a.staff_member_id)}`}
            actions={[
              {
                key: 'decide',
                label: mine ? `Approve / reject (${OWN_REQUEST_TOOLTIP})` : 'Approve / reject',
                hidden: !canDecide || a.status !== 'PENDING',
                disabled: mine,
                disabledReason: OWN_REQUEST_TOOLTIP,
                onClick: () => {
                  setDeciding(a);
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
    const a = deciding;
    dialog = (
      <DecisionDialog<CustodyAdjustmentDto>
        title="Decide custody adjustment"
        kind="approve"
        summary={
          <KeyValueGrid
            columns={2}
            items={[
              { label: 'Custodian', value: custodian(a.staff_member_id) },
              { label: 'Kind', value: ADJUSTMENT_KIND_LABELS[a.kind] },
              {
                label: 'Amount',
                value: <MoneyText amount={a.amount} currency={a.currency} strong />,
              },
              { label: 'Reason', value: a.reason },
              { label: 'Proposed by', value: <PersonName userId={a.created_by} /> },
              {
                label: 'Record reversed',
                value:
                  a.reverses_entity_type === null
                    ? '—'
                    : `${entityTypeLabel(a.reverses_entity_type)} ${a.reverses_entity_id ?? ''}`,
              },
            ]}
          />
        }
        explanation="An approved adjustment changes the custodian's expected balance by the signed amount; a rejected one never counts."
        onDecide={(approve, note, key) =>
          custodyService.decideAdjustment(a.id, { approve, note }, key)
        }
        onDone={(res) => {
          notify.success(
            res.status === 'APPROVED' ? 'Adjustment approved.' : 'Adjustment rejected.',
          );
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
      <ServerDataTable
        columns={columns}
        fetchPage={fetchPage}
        getRowId={(a) => a.id}
        searchable={false}
        reloadKey={reloadKey}
        filters={{ status: status || undefined, staff_member_id: who?.staff_member_id }}
        emptyTitle="No custody adjustments"
        isRowMuted={(a) => a.status === 'REJECTED'}
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
            {canPropose && (
              <Button
                variant="outlined"
                onClick={() => {
                  setProposing(true);
                }}
              >
                Propose adjustment
              </Button>
            )}
          </Box>
        }
      />
      {proposing && (
        <AdjustmentDialog
          {...(who !== null ? { staffMemberId: who.staff_member_id } : {})}
          timeZone={timeZone}
          onClose={() => {
            setProposing(false);
          }}
          onRecorded={() => {
            notify.success('Adjustment proposed; it counts once someone else approves it.');
            setReloadKey((k) => k + 1);
          }}
        />
      )}
      {dialog}
    </Box>
  );
}
