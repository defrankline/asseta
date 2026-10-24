import { Alert, Box, ToggleButton, ToggleButtonGroup } from '@mui/material';
import { useCallback, useState, type ReactNode } from 'react';
import { PERMISSIONS } from '../../../../access/permissionCodes';
import { useCanMutate } from '../../../../access/useCanMutate';
import { cashService } from '../../../../api/services/cashService';
import type { CashHandoverDto, SettlementStatus } from '../../../../api/types';
import type { CustodianDto } from '../../../../api/custodyTypes';
import { ServerDataTable, type DataColumn } from '../../../../components/data/ServerDataTable';
import type { FetchPage } from '../../../../components/data/useServerPage';
import { MoneyText } from '../../../../components/display/MoneyText';
import { StatusChip } from '../../../../components/display/StatusChip';
import { RowActionsMenu } from '../../../../components/lifecycle/RowActionsMenu';
import { useNotify } from '../../../../notifications/useNotify';
import { formatInstantIn } from '../../../../utils/time';
import { SETTLEMENT_LABELS, SETTLEMENT_TONES, shortId } from '../../shared/financeDisplay';
import { PersonName } from '../../shared/PersonName';
import { useMyUserId } from '../../shared/useFinanceLabels';
import { ENTITY } from '../../../../realtime/entities';
import { useLiveRefresh } from '../../../../realtime/hooks';
import { RemittanceDecisionDialog } from './CustodyDialogs';
import { useCustodianLabels } from './custodyHooks';
import { CustodianFilter } from './custodyPickers';

type View = SettlementStatus | 'ALL';

/**
 * Remittances (cash handed to the company): claimed vs confirmed; the office confirms with the amount
 * actually received (a difference opens a variance) or rejects. Never your own.
 */
export function HandoversTab({ timeZone }: { timeZone: string }) {
  const notify = useNotify();
  const me = useMyUserId();
  const staffLabel = useCustodianLabels();
  const canVerify = useCanMutate(PERMISSIONS.tenantFinanceVerify);
  const [view, setView] = useState<View>('CLAIMED');
  const [staff, setStaff] = useState<CustodianDto | null>(null);
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
      header: 'Declared',
      align: 'right',
      render: (h) => <MoneyText amount={h.amount} currency={h.currency} />,
    },
    {
      id: 'received',
      header: 'Received',
      align: 'right',
      render: (h) =>
        h.amount_received === null || h.amount_received === undefined ? (
          '—'
        ) : (
          <MoneyText amount={h.amount_received} currency={h.currency} />
        ),
    },
    {
      id: 'shortfall',
      header: 'Short of full balance',
      align: 'right',
      render: (h) =>
        h.partial_shortfall === null || h.partial_shortfall === undefined ? (
          '—'
        ) : (
          <MoneyText amount={h.partial_shortfall} currency={h.currency} />
        ),
    },
    { id: 'note', header: 'Decision note', render: (h) => h.decision_note ?? '—' },
    {
      id: 'actions',
      header: '',
      align: 'right',
      render: (h) => (
        <RowActionsMenu
          label={`remittance ${h.reference ?? shortId(h.id)}`}
          actions={[
            {
              key: 'decide',
              label: mine(h)
                ? 'Confirm / reject (not allowed: you recorded it)'
                : 'Confirm / reject',
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
      <RemittanceDecisionDialog
        handover={h}
        custodianName={staffLabel(h.staff_member_id)}
        timeZone={timeZone}
        onDone={(r) => {
          notify.success(
            r.status === 'VERIFIED' ? 'Remittance confirmed.' : 'Remittance rejected.',
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
      <ToggleButtonGroup
        exclusive
        size="small"
        value={view}
        aria-label="Remittance status"
        onChange={(_e, v: View | null) => {
          if (v !== null) setView(v);
        }}
      >
        <ToggleButton value="CLAIMED">Awaiting confirmation</ToggleButton>
        <ToggleButton value="VERIFIED">Confirmed</ToggleButton>
        <ToggleButton value="REJECTED">Rejected</ToggleButton>
        <ToggleButton value="ALL">All</ToggleButton>
      </ToggleButtonGroup>
      {view === 'CLAIMED' && (
        <Alert severity="warning">
          Remittances awaiting confirmation do not reduce a custodian’s outstanding cash until
          someone other than the recorder confirms the amount received.
        </Alert>
      )}
      <ServerDataTable
        columns={columns}
        fetchPage={fetchPage}
        getRowId={(h) => h.id}
        searchable={false}
        reloadKey={reloadKey}
        filters={{
          status: view === 'ALL' ? undefined : view,
          staff_member_id: staff?.staff_member_id,
        }}
        emptyTitle="No remittances"
        isRowMuted={(h) => h.status === 'REJECTED'}
        toolbar={
          <Box sx={{ minWidth: 240 }}>
            <CustodianFilter value={staff} onChange={setStaff} />
          </Box>
        }
      />
      {dialog}
    </Box>
  );
}
