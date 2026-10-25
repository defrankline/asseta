import { Alert, Box, TextField } from '@mui/material';
import { useCallback, useState } from 'react';
import { useNavigate } from 'react-router';
import type { CustodianDto, RemittanceOverdueDto } from '../../../../api/custodyTypes';
import { custodyService } from '../../../../api/services/custodyService';
import { ServerDataTable, type DataColumn } from '../../../../components/data/ServerDataTable';
import type { FetchPage } from '../../../../components/data/useServerPage';
import { RowActionsMenu } from '../../../../components/lifecycle/RowActionsMenu';
import { recordPath } from '../../../../navigation/recordRoutes';
import { cashTabPath } from '../../../../navigation/routes';
import { formatDate } from '../../../../utils/dates';
import { formatInstantIn } from '../../../../utils/time';
import { CustodianFilter } from './custodyPickers';
import { cutoffText, overdueAmounts, overdueCustodian } from './remittanceOverdueRecord';

const isDay = (v: string) => /^\d{4}-\d{2}-\d{2}$/.test(v);

/**
 * Custodians still holding unremitted cash after the tenant's daily remittance cut-off
 * (cash.remittance_cutoff_hour), latest day first; filter by custodian and day range.
 */
export function RemittanceOverdueTab({ timeZone }: { timeZone: string }) {
  const navigate = useNavigate();
  const [who, setWho] = useState<CustodianDto | null>(null);
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const fetchPage = useCallback<FetchPage<RemittanceOverdueDto>>(
    (query, signal) => custodyService.remittanceOverdue(query, signal),
    [],
  );
  const open = (o: RemittanceOverdueDto) => {
    void navigate(recordPath('REMITTANCE_OVERDUE', o.id));
  };
  const badRange = isDay(from) && isDay(to) && from > to;
  const columns: DataColumn<RemittanceOverdueDto>[] = [
    { id: 'day', header: 'Day', render: (o) => formatDate(o.local_day) },
    { id: 'who', header: 'Custodian', render: overdueCustodian },
    { id: 'cutoff', header: 'Cut-off', render: (o) => cutoffText(o.cutoff_hour) },
    { id: 'flagged', header: 'Flagged', render: (o) => formatInstantIn(o.flagged_at, timeZone) },
    {
      id: 'amounts',
      header: 'Cash still held',
      align: 'right',
      render: overdueAmounts,
    },
    {
      id: 'actions',
      header: '',
      align: 'right',
      render: (o) => (
        <RowActionsMenu
          label={`overdue remittance of ${overdueCustodian(o)}`}
          actions={[
            {
              key: 'view',
              label: 'View details',
              onClick: () => {
                open(o);
              },
            },
            {
              key: 'custody',
              label: 'Open custody',
              onClick: () => {
                void navigate(cashTabPath('custody', { staff_member_id: o.staff_member_id }));
              },
            },
          ]}
        />
      ),
    },
  ];
  return (
    <Box className="flex flex-col gap-3">
      <Alert severity="info">
        Custodians still holding cash not remitted after your organisation’s daily cut-off. Flags
        appear only when a remittance cut-off is set in the cash custody policy.
      </Alert>
      {badRange && <Alert severity="error">The “from” day must not be after the “to” day.</Alert>}
      <ServerDataTable
        columns={columns}
        fetchPage={fetchPage}
        getRowId={(o) => o.id}
        searchable={false}
        filters={{
          staff_member_id: who?.staff_member_id,
          day_from: isDay(from) && !badRange ? from : undefined,
          day_to: isDay(to) && !badRange ? to : undefined,
        }}
        emptyTitle="No overdue remittances"
        onRowClick={open}
        toolbar={
          <Box className="flex flex-wrap items-center gap-3">
            <Box sx={{ minWidth: 240 }}>
              <CustodianFilter value={who} onChange={setWho} />
            </Box>
            <TextField
              size="small"
              type="date"
              label="From day"
              value={from}
              onChange={(e) => {
                setFrom(e.target.value);
              }}
              slotProps={{ inputLabel: { shrink: true } }}
            />
            <TextField
              size="small"
              type="date"
              label="To day"
              value={to}
              onChange={(e) => {
                setTo(e.target.value);
              }}
              slotProps={{ inputLabel: { shrink: true } }}
            />
          </Box>
        }
      />
    </Box>
  );
}
