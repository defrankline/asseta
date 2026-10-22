import { Alert, Box, ToggleButton, ToggleButtonGroup } from '@mui/material';
import { useCallback, useState, type ReactNode } from 'react';
import { PERMISSIONS } from '../../../../access/permissionCodes';
import { useCanMutate } from '../../../../access/useCanMutate';
import { cashService } from '../../../../api/services/cashService';
import type { CashHandoverDto, SettlementStatus, StaffDto } from '../../../../api/types';
import { ServerDataTable, type DataColumn } from '../../../../components/data/ServerDataTable';
import type { FetchPage } from '../../../../components/data/useServerPage';
import { KeyValueGrid } from '../../../../components/display/KeyValueGrid';
import { MoneyText } from '../../../../components/display/MoneyText';
import { StatusChip } from '../../../../components/display/StatusChip';
import { RowActionsMenu } from '../../../../components/lifecycle/RowActionsMenu';
import { useNotify } from '../../../../notifications/useNotify';
import { formatInstantIn } from '../../../../utils/time';
import { DecisionDialog } from '../../shared/DecisionDialog';
import { SETTLEMENT_LABELS, SETTLEMENT_TONES, shortId } from '../../shared/financeDisplay';
import { PersonName } from '../../shared/PersonName';
import { StaffFilter } from '../../shared/financePickers';
import { useMyUserId, useStaffLabels } from '../../shared/useFinanceLabels';
import { ENTITY } from '../../../../realtime/entities';
import { useLiveRefresh } from '../../../../realtime/hooks';

type View = SettlementStatus | 'ALL';

/** Cash handovers from supervisors: claimed vs verified, verify / reject (never your own). */
export function HandoversTab({ timeZone }: { timeZone: string }) {
  const notify = useNotify();
  const me = useMyUserId();
  const staffLabel = useStaffLabels();
  const canVerify = useCanMutate(PERMISSIONS.tenantFinanceVerify);
  const [view, setView] = useState<View>('CLAIMED');
  const [staff, setStaff] = useState<StaffDto | null>(null);
  const [deciding, setDeciding] = useState<CashHandoverDto | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const liveReload = useCallback(() => {
    setReloadKey((k) => k + 1);
  }, []);
  useLiveRefresh([ENTITY.cashHandover], liveReload);
  const fetchPage = useCallback<FetchPage<CashHandoverDto>>(
    (query, signal) => cashService.listHandovers(query, signal),
    [],
  );
  const mine = (h: CashHandoverDto) => h.recorded_by !== null && h.recorded_by === me;
  const columns: DataColumn<CashHandoverDto>[] = [
    { id: 'at', header: 'Handed over', render: (h) => formatInstantIn(h.handed_at, timeZone) },
    { id: 'staff', header: 'Custodian', render: (h) => staffLabel(h.staff_member_id) },
    { id: 'ref', header: 'Reference', render: (h) => h.reference ?? '—' },
    {
      id: 'status',
      header: 'Status',
      render: (h) => (
        <StatusChip
          status={h.status}
          tones={SETTLEMENT_TONES}
          label={SETTLEMENT_LABELS[h.status]}
        />
      ),
    },
    { id: 'by', header: 'Recorded by', render: (h) => <PersonName userId={h.recorded_by} /> },
    {
      id: 'amount',
      header: 'Amount',
      align: 'right',
      render: (h) => <MoneyText amount={h.amount} currency={h.currency} />,
    },
    { id: 'note', header: 'Decision note', render: (h) => h.decision_note ?? '—' },
    {
      id: 'actions',
      header: '',
      align: 'right',
      render: (h) => (
        <RowActionsMenu
          label={`handover ${h.reference ?? shortId(h.id)}`}
          actions={[
            {
              key: 'decide',
              label: mine(h) ? 'Verify / reject (not allowed: you recorded it)' : 'Verify / reject',
              hidden: !canVerify || h.status !== 'CLAIMED',
              disabled: mine(h),
              onClick: () => {
                setDeciding(h);
              },
            },
          ]}
        />
      ),
    },
  ];
  let dialog: ReactNode = null;
  if (deciding !== null) {
    const h = deciding;
    dialog = (
      <DecisionDialog<CashHandoverDto>
        title="Verify cash handover"
        kind="verify"
        summary={
          <KeyValueGrid
            columns={2}
            items={[
              { label: 'Custodian', value: staffLabel(h.staff_member_id) },
              {
                label: 'Amount',
                value: <MoneyText amount={h.amount} currency={h.currency} strong />,
              },
              { label: 'Handed over', value: formatInstantIn(h.handed_at, timeZone) },
              { label: 'Reference', value: h.reference ?? '—' },
            ]}
          />
        }
        explanation="Verify only after counting the cash or seeing the deposit. A verified handover reduces the supervisor's outstanding cash; a rejected one never does."
        onDecide={(approve, note, key) =>
          cashService.decideHandover(h.id, { verified: approve, note }, key)
        }
        onDone={(r) => {
          notify.success(r.status === 'VERIFIED' ? 'Handover verified.' : 'Handover rejected.');
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
      <ToggleButtonGroup
        exclusive
        size="small"
        value={view}
        aria-label="Handover status"
        onChange={(_e, v: View | null) => {
          if (v !== null) setView(v);
        }}
      >
        <ToggleButton value="CLAIMED">Claimed (unverified)</ToggleButton>
        <ToggleButton value="VERIFIED">Verified</ToggleButton>
        <ToggleButton value="REJECTED">Rejected</ToggleButton>
        <ToggleButton value="ALL">All</ToggleButton>
      </ToggleButtonGroup>
      {view === 'CLAIMED' && (
        <Alert severity="warning">
          Claimed handovers do not reduce a supervisor’s outstanding cash until someone other than
          the recorder verifies them.
        </Alert>
      )}
      <ServerDataTable
        columns={columns}
        fetchPage={fetchPage}
        getRowId={(h) => h.id}
        searchable={false}
        reloadKey={reloadKey}
        filters={{ status: view === 'ALL' ? undefined : view, staff_member_id: staff?.id }}
        emptyTitle="No handovers"
        isRowMuted={(h) => h.status === 'REJECTED'}
        toolbar={
          <Box sx={{ minWidth: 240 }}>
            <StaffFilter label="Custodian" supervisorsOnly value={staff} onChange={setStaff} />
          </Box>
        }
      />
      {dialog}
    </Box>
  );
}
