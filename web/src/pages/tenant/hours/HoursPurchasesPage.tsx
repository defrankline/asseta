import Add from '@mui/icons-material/Add';
import { Box, Button, Stack } from '@mui/material';
import { useCallback, useState } from 'react';
import { useNavigate } from 'react-router';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { useCanMutate } from '../../../access/useCanMutate';
import type { HoursPurchaseDto } from '../../../api/hoursTypes';
import { hoursService } from '../../../api/services/hoursService';
import type { CustomerDto, MachineDto } from '../../../api/types';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import type { FetchPage } from '../../../components/data/useServerPage';
import { MoneyText } from '../../../components/display/MoneyText';
import { StatusChip } from '../../../components/display/StatusChip';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { StaticSelectFilter } from '../../../components/forms/StaticSelectFilter';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { hoursPurchasePath } from '../../../navigation/hoursRoutes';
import { useNotify } from '../../../notifications/useNotify';
import { formatInstantIn } from '../../../utils/time';
import { CustomerFilter, MachineFilter } from '../shared/financePickers';
import { useCustomerLabels } from '../shared/useFinanceLabels';
import { useMachineLabels } from '../shared/useMachineLabels';
import { HoursOffNotice } from './HoursDialogs';
import {
  CANCELLED_OPTIONS,
  hoursText,
  PURCHASE_STATUS_LABELS,
  PURCHASE_STATUS_TONES,
} from './hoursDisplay';
import { RecordPurchaseDialog } from './RecordPurchaseDialog';
import { useHoursPolicy } from './useHoursPolicy';

/** Prepaid customer hours purchases: search, filter, record (incl. walk-ins), open a purchase. */
export function HoursPurchasesPage() {
  const notify = useNotify();
  const navigate = useNavigate();
  const timeZone = useDisplayTimeZone();
  const machineName = useMachineLabels();
  const customerName = useCustomerLabels();
  const hours = useHoursPolicy();
  const canRecord = useCanMutate(PERMISSIONS.tenantHoursPurchase) && hours.on;
  const [customer, setCustomer] = useState<CustomerDto | null>(null);
  const [machine, setMachine] = useState<MachineDto | null>(null);
  const [cancelled, setCancelled] = useState('');
  const [recording, setRecording] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const fetchPage = useCallback<FetchPage<HoursPurchaseDto>>(
    (query, signal) => hoursService.listPurchases(query, signal),
    [],
  );
  const columns: DataColumn<HoursPurchaseDto>[] = [
    { id: 'number', header: 'Purchase', render: (p) => <strong>{p.purchase_number}</strong> },
    {
      id: 'customer',
      header: 'Customer',
      render: (p) =>
        `${p.customer_name ?? customerName(p.customer_id)}${p.customer_kind === 'WALK_IN' ? ' (walk-in)' : ''}`,
    },
    { id: 'machine', header: 'Machine', render: (p) => machineName(p.machine_id) },
    { id: 'hours', header: 'Hours', align: 'right', render: (p) => hoursText(p.hours) },
    {
      id: 'remaining',
      header: 'Remaining',
      align: 'right',
      render: (p) => hoursText(p.totals.remaining),
    },
    {
      id: 'amount',
      header: 'Amount',
      align: 'right',
      render: (p) => <MoneyText amount={p.amount} currency={p.currency} />,
    },
    {
      id: 'status',
      header: 'Status',
      render: (p) => (
        <StatusChip
          status={p.status}
          tones={PURCHASE_STATUS_TONES}
          label={PURCHASE_STATUS_LABELS[p.status]}
        />
      ),
    },
    {
      id: 'created',
      header: 'Recorded',
      sortField: 'created_at',
      render: (p) => formatInstantIn(p.created_at, timeZone),
    },
  ];
  return (
    <>
      <PageHeader
        title="Hours purchases"
        subtitle="Prepaid hours bought per customer and machine; they activate from verified money or approved credit"
        actions={
          canRecord && (
            <Button
              variant="contained"
              startIcon={<Add />}
              onClick={() => {
                setRecording(true);
              }}
            >
              New purchase
            </Button>
          )
        }
      />
      <Stack spacing={2}>
        <HoursOffNotice off={hours.status === 'known' && !hours.on} />
        <ServerDataTable
          columns={columns}
          fetchPage={fetchPage}
          getRowId={(p) => p.id}
          searchPlaceholder="Search purchase number"
          reloadKey={reloadKey}
          initialSort="-created_at"
          filters={{
            customer_id: customer?.id,
            machine_id: machine?.id,
            cancelled: cancelled === '' ? undefined : cancelled,
          }}
          emptyTitle="No hours purchases"
          isRowMuted={(p) => p.status === 'CANCELLED'}
          onRowClick={(p) => {
            void navigate(hoursPurchasePath(p.id));
          }}
          toolbar={
            <Box className="flex flex-wrap gap-3">
              <Box sx={{ minWidth: 240 }}>
                <CustomerFilter label="Customer" value={customer} onChange={setCustomer} />
              </Box>
              <Box sx={{ minWidth: 220 }}>
                <MachineFilter label="Machine" value={machine} onChange={setMachine} />
              </Box>
              <StaticSelectFilter
                label="Cancelled"
                value={cancelled}
                options={CANCELLED_OPTIONS}
                allLabel="All purchases"
                onChange={setCancelled}
              />
            </Box>
          }
        />
      </Stack>
      {recording && (
        <RecordPurchaseDialog
          timeZone={timeZone}
          walkInAllowed={hours.policy?.walkInAllowed ?? true}
          onClose={() => {
            setRecording(false);
          }}
          onRecorded={(p) => {
            notify.success(`Hours purchase ${p.purchase_number} recorded.`);
            setReloadKey((k) => k + 1);
            void navigate(hoursPurchasePath(p.id));
          }}
        />
      )}
    </>
  );
}
