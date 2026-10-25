import { Alert, Box, ToggleButton, ToggleButtonGroup } from '@mui/material';
import { useCallback, useState } from 'react';
import { useNavigate } from 'react-router';
import { CAPABILITY, useCapabilityEnabled } from '../../../../access/capabilities';
import { custodyService } from '../../../../api/services/custodyService';
import type { CashCustodyEntryDto } from '../../../../api/types';
import type { CustodianDto } from '../../../../api/custodyTypes';
import { ServerDataTable, type DataColumn } from '../../../../components/data/ServerDataTable';
import type { FetchPage } from '../../../../components/data/useServerPage';
import { MoneyText } from '../../../../components/display/MoneyText';
import { RowActionsMenu } from '../../../../components/lifecycle/RowActionsMenu';
import { recordPath } from '../../../../navigation/recordRoutes';
import { formatInstantIn } from '../../../../utils/time';
import { PersonName } from '../../shared/PersonName';
import { useCashPolicy } from './custodyHooks';
import { CustodianFilter } from './custodyPickers';
import { floatChip, floatCustodian, floatKind, useFloatActions } from './floatRecord';

type View = 'awaiting' | 'all';

const receivedColumn: DataColumn<CashCustodyEntryDto> = {
  id: 'received',
  header: 'Received',
  align: 'right',
  render: (e) =>
    e.amount_received === null || e.amount_received === undefined ? (
      '—'
    ) : (
      <MoneyText amount={e.amount_received} currency={e.currency} />
    ),
};

/** Floats (and opening balances) issued to custodians, with the receiver's acknowledgement. */
export function FloatsTab({ timeZone }: { timeZone: string }) {
  const navigate = useNavigate();
  const policy = useCashPolicy();
  /** Off: floats are the basics only (issued and listed, never acknowledged). */
  const ackOn = useCapabilityEnabled(CAPABILITY.cashCustody);
  const [chosenView, setView] = useState<View>('awaiting');
  const view: View = ackOn ? chosenView : 'all';
  const [who, setWho] = useState<CustodianDto | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const fetchPage = useCallback<FetchPage<CashCustodyEntryDto>>(
    (query, signal) => custodyService.floats(query, signal),
    [],
  );
  const reload = () => {
    setReloadKey((k) => k + 1);
  };
  const { actionsFor, dialog } = useFloatActions(reload);
  const open = (e: CashCustodyEntryDto) => {
    void navigate(recordPath('CASH_FLOAT', e.id));
  };
  const columns: DataColumn<CashCustodyEntryDto>[] = [
    { id: 'at', header: 'Issued', render: (e) => formatInstantIn(e.occurred_at, timeZone) },
    { id: 'to', header: 'Custodian', render: floatCustodian },
    { id: 'kind', header: 'Entry', render: floatKind },
    { id: 'ref', header: 'Reference', render: (e) => e.reference ?? '—' },
    ...(ackOn
      ? [
          {
            id: 'ack',
            header: 'Acknowledgement',
            render: floatChip,
          } as DataColumn<CashCustodyEntryDto>,
        ]
      : []),
    {
      id: 'by',
      header: 'Issued by',
      render: (e) => <PersonName userId={e.created_by ?? null} name={e.created_by_name} />,
    },
    {
      id: 'amount',
      header: 'Amount',
      align: 'right',
      render: (e) => <MoneyText amount={e.amount} currency={e.currency} />,
    },
    ...(ackOn ? [receivedColumn] : []),
    {
      id: 'actions',
      header: '',
      align: 'right',
      render: (e) => (
        <RowActionsMenu
          label={`float to ${floatCustodian(e)}`}
          actions={[
            {
              key: 'view',
              label: 'View details',
              onClick: () => {
                open(e);
              },
            },
            ...actionsFor(e),
          ]}
        />
      ),
    },
  ];
  return (
    <Box className="flex flex-col gap-3">
      {ackOn && policy?.floatAckRequired === false && (
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
        onRowClick={open}
        toolbar={
          <Box className="flex flex-wrap items-center gap-3">
            {ackOn && (
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
            )}
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
