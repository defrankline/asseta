import { Alert, Box, ToggleButton, ToggleButtonGroup } from '@mui/material';
import { useCallback, useState, type ReactNode } from 'react';
import { PERMISSIONS } from '../../../../access/permissionCodes';
import { useMutationGuard } from '../../../../access/useCanMutate';
import { custodyService } from '../../../../api/services/custodyService';
import type { CashCustodyEntryDto } from '../../../../api/types';
import type { CustodianDto } from '../../../../api/custodyTypes';
import { ServerDataTable, type DataColumn } from '../../../../components/data/ServerDataTable';
import type { FetchPage } from '../../../../components/data/useServerPage';
import { KeyValueGrid } from '../../../../components/display/KeyValueGrid';
import { MoneyText } from '../../../../components/display/MoneyText';
import { StatusChip } from '../../../../components/display/StatusChip';
import { RowActionsMenu } from '../../../../components/lifecycle/RowActionsMenu';
import { useNotify } from '../../../../notifications/useNotify';
import { formatInstantIn } from '../../../../utils/time';
import { PersonName } from '../../shared/PersonName';
import { useMyUserId } from '../../shared/useFinanceLabels';
import { FLOAT_ACK_LABELS, FLOAT_ACK_TONES } from './custodyDisplay';
import { AcknowledgeDialog } from './CustodyDialogs';
import { useCashPolicy, useCustodianLabels } from './custodyHooks';
import { CustodianFilter } from './custodyPickers';

type View = 'awaiting' | 'all';

/** Floats (and opening balances) issued to custodians, with the receiver's acknowledgement. */
export function FloatsTab({ timeZone }: { timeZone: string }) {
  const notify = useNotify();
  const me = useMyUserId();
  const can = useMutationGuard();
  const policy = useCashPolicy();
  const custodian = useCustodianLabels();
  const [view, setView] = useState<View>('awaiting');
  const [who, setWho] = useState<CustodianDto | null>(null);
  const [answering, setAnswering] = useState<CashCustodyEntryDto | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const fetchPage = useCallback<FetchPage<CashCustodyEntryDto>>(
    (query, signal) => custodyService.floats(query, signal),
    [],
  );
  const canAnswer = can(PERMISSIONS.tenantCollectionRecord);
  const columns: DataColumn<CashCustodyEntryDto>[] = [
    { id: 'at', header: 'Issued', render: (e) => formatInstantIn(e.occurred_at, timeZone) },
    { id: 'to', header: 'Custodian', render: (e) => custodian(e.staff_member_id) },
    {
      id: 'kind',
      header: 'Entry',
      render: (e) => (e.entry_type === 'FLOAT_ISSUED' ? 'Float issued' : 'Opening balance'),
    },
    { id: 'ref', header: 'Reference', render: (e) => e.reference ?? '—' },
    {
      id: 'ack',
      header: 'Acknowledgement',
      render: (e) => (
        <StatusChip
          status={e.ack_status}
          tones={FLOAT_ACK_TONES}
          label={FLOAT_ACK_LABELS[e.ack_status]}
        />
      ),
    },
    { id: 'by', header: 'Issued by', render: (e) => <PersonName userId={e.created_by ?? null} /> },
    {
      id: 'amount',
      header: 'Amount',
      align: 'right',
      render: (e) => <MoneyText amount={e.amount} currency={e.currency} />,
    },
    {
      id: 'received',
      header: 'Received',
      align: 'right',
      render: (e) =>
        e.amount_received === null || e.amount_received === undefined ? (
          '—'
        ) : (
          <MoneyText amount={e.amount_received} currency={e.currency} />
        ),
    },
    {
      id: 'actions',
      header: '',
      align: 'right',
      render: (e) => (
        <RowActionsMenu
          label={`float to ${custodian(e.staff_member_id)}`}
          actions={[
            {
              key: 'answer',
              label: 'Acknowledge / dispute',
              hidden: !canAnswer || e.ack_status !== 'PENDING',
              disabled: e.created_by !== null && e.created_by === me,
              disabledReason: 'You issued this float; the receiver must answer it.',
              onClick: () => {
                setAnswering(e);
              },
            },
          ]}
        />
      ),
    },
  ];
  let dialog: ReactNode = null;
  if (answering !== null) {
    const e = answering;
    dialog = (
      <AcknowledgeDialog<CashCustodyEntryDto>
        title="Acknowledge cash float"
        declared={e.amount}
        summary={
          <KeyValueGrid
            columns={2}
            items={[
              { label: 'Custodian', value: custodian(e.staff_member_id) },
              {
                label: 'Amount issued',
                value: <MoneyText amount={e.amount} currency={e.currency} strong />,
              },
              { label: 'Issued', value: formatInstantIn(e.occurred_at, timeZone) },
              { label: 'Reference', value: e.reference ?? '—' },
            ]}
          />
        }
        onAnswer={(body, key) => custodyService.acknowledgeFloat(e.id, body, key)}
        onDone={(r) => {
          notify.success(r.ack_status === 'DISPUTED' ? 'Float disputed.' : 'Float acknowledged.');
          setReloadKey((k) => k + 1);
        }}
        onClose={() => {
          setAnswering(null);
        }}
      />
    );
  }
  return (
    <Box className="flex flex-col gap-3">
      {policy?.floatAckRequired === false && (
        <Alert severity="info">
          Your organisation does not require floats to be acknowledged: a float counts in the
          receiver’s custody when issued.
        </Alert>
      )}
      <ServerDataTable
        columns={columns}
        fetchPage={fetchPage}
        getRowId={(e) => e.id}
        searchable={false}
        reloadKey={reloadKey}
        filters={{
          awaiting_acknowledgement: view === 'awaiting' ? 'true' : undefined,
          staff_member_id: who?.staff_member_id,
        }}
        emptyTitle={view === 'awaiting' ? 'No floats awaiting acknowledgement' : 'No floats'}
        isRowMuted={(e) => e.ack_status === 'DISPUTED'}
        toolbar={
          <Box className="flex flex-wrap items-center gap-3">
            <ToggleButtonGroup
              exclusive
              size="small"
              value={view}
              aria-label="Floats shown"
              onChange={(_e, v: View | null) => {
                if (v !== null) setView(v);
              }}
            >
              <ToggleButton value="awaiting">Awaiting acknowledgement</ToggleButton>
              <ToggleButton value="all">All</ToggleButton>
            </ToggleButtonGroup>
            <Box sx={{ minWidth: 240 }}>
              <CustodianFilter value={who} onChange={setWho} />
            </Box>
          </Box>
        }
      />
      {dialog}
    </Box>
  );
}
