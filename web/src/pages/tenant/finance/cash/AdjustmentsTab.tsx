import { Box, Button } from '@mui/material';
import { useCallback, useState } from 'react';
import { useNavigate } from 'react-router';
import { PERMISSIONS } from '../../../../access/permissionCodes';
import { useMutationGuard } from '../../../../access/useCanMutate';
import { custodyService } from '../../../../api/services/custodyService';
import type { CustodianDto, CustodyAdjustmentDto } from '../../../../api/custodyTypes';
import { ServerDataTable, type DataColumn } from '../../../../components/data/ServerDataTable';
import type { FetchPage } from '../../../../components/data/useServerPage';
import { MoneyText } from '../../../../components/display/MoneyText';
import { StaticSelectFilter } from '../../../../components/forms/StaticSelectFilter';
import { RowActionsMenu } from '../../../../components/lifecycle/RowActionsMenu';
import { recordPath } from '../../../../navigation/recordRoutes';
import { useNotify } from '../../../../notifications/useNotify';
import { formatInstantIn } from '../../../../utils/time';
import { PersonName } from '../../shared/PersonName';
import { adjustmentChip, adjustmentCustodian, useAdjustmentActions } from './adjustmentRecord';
import { ADJUSTMENT_KIND_LABELS, DECISION_STATUS_OPTIONS, entityTypeLabel } from './custodyDisplay';
import { AdjustmentDialog } from './CustodyRequestDialogs';
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
  const navigate = useNavigate();
  const can = useMutationGuard();
  const [status, setStatus] = useState(initialStatus ?? 'PENDING');
  const [who, setWho] = useState<CustodianDto | null>(null);
  const [proposing, setProposing] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const fetchPage = useCallback<FetchPage<CustodyAdjustmentDto>>(
    (query, signal) => custodyService.adjustments(query, signal),
    [],
  );
  const canPropose = can(PERMISSIONS.tenantFinanceCash);
  const reload = () => {
    setReloadKey((k) => k + 1);
  };
  const { actionsFor, dialog } = useAdjustmentActions(reload);
  const open = (a: CustodyAdjustmentDto) => {
    void navigate(recordPath('CUSTODY_ADJUSTMENT', a.id));
  };
  const columns: DataColumn<CustodyAdjustmentDto>[] = [
    { id: 'at', header: 'Effective', render: (a) => formatInstantIn(a.occurred_at, timeZone) },
    { id: 'who', header: 'Custodian', render: adjustmentCustodian },
    { id: 'kind', header: 'Kind', render: (a) => ADJUSTMENT_KIND_LABELS[a.kind] },
    {
      id: 'reverses',
      header: 'Record reversed',
      render: (a) =>
        a.reverses_entity_type === null ? '—' : entityTypeLabel(a.reverses_entity_type),
    },
    { id: 'reason', header: 'Reason', render: (a) => a.reason },
    { id: 'status', header: 'Status', render: adjustmentChip },
    {
      id: 'by',
      header: 'Proposed by',
      render: (a) => <PersonName userId={a.created_by} name={a.created_by_name} />,
    },
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
      render: (a) => (
        <RowActionsMenu
          label={`adjustment of ${adjustmentCustodian(a)}`}
          actions={[
            {
              key: 'view',
              label: 'View details',
              onClick: () => {
                open(a);
              },
            },
            ...actionsFor(a),
          ]}
        />
      ),
    },
  ];
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
        onRowClick={open}
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
