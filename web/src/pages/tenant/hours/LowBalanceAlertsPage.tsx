import { Box, Button, Chip, Link, Stack } from '@mui/material';
import { useCallback, useState } from 'react';
import { Link as RouterLink, useNavigate, useParams, useSearchParams } from 'react-router';
import type { HoursPurchaseDto, LowBalanceAlertDto } from '../../../api/hoursTypes';
import { hoursStatementService } from '../../../api/services/hoursStatementService';
import type { CustomerDto, MachineDto } from '../../../api/types';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import type { FetchPage } from '../../../components/data/useServerPage';
import { StatusChip } from '../../../components/display/StatusChip';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { StaticSelectFilter } from '../../../components/forms/StaticSelectFilter';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import {
  HOURS_ROUTES,
  hoursPurchasePath,
  lowBalanceAlertPath,
} from '../../../navigation/hoursRoutes';
import { customerDetailPath } from '../../../navigation/routes';
import { initialFilter } from '../../../navigation/urlFilters';
import { formatInstantIn } from '../../../utils/time';
import { CustomerFilter, MachineFilter } from '../shared/financePickers';
import { machineText, nameOr } from '../shared/names';
import { RecordDetail } from '../shared/RecordDetail';
import { useRecordById } from '../shared/useRecordById';
import { HoursOffNotice } from './HoursDialogs';
import { hoursText, LOW_BALANCE_SMS_LABELS, LOW_BALANCE_STATE_OPTIONS } from './hoursDisplay';
import { PurchaseFilter } from './hoursPickers';
import { useHoursPolicy } from './useHoursPolicy';

const STATE_TONES = { LOW: 'warning', TOPPED_UP: 'default' } as const;

/** Still low (armed) until the balance goes back above the threshold. */
function stateChip(a: LowBalanceAlertDto) {
  return a.rearmed_at === null ? (
    <StatusChip status="LOW" tones={STATE_TONES} label="Still low" />
  ) : (
    <StatusChip status="TOPPED_UP" tones={STATE_TONES} label="Topped up since" />
  );
}

const purchaseText = (a: LowBalanceAlertDto) => nameOr(a.purchase_number, a.purchase_id);
const machineOf = (a: LowBalanceAlertDto) =>
  machineText(a.machine_code, a.machine_name, a.machine_id);

/**
 * Low-balance warnings (DEC-031 P2): one per time a purchase's remaining hours fell to the tenant's
 * threshold while the customer had no more than that on the machine.
 */
export function LowBalanceAlertsPage() {
  const timeZone = useDisplayTimeZone();
  const navigate = useNavigate();
  const hours = useHoursPolicy();
  const [params, setParams] = useSearchParams();
  const urlPurchase = params.get('purchase_id') ?? undefined;
  const urlCustomer = params.get('customer_id') ?? undefined;
  const [purchase, setPurchase] = useState<HoursPurchaseDto | null>(null);
  const [customer, setCustomer] = useState<CustomerDto | null>(null);
  const [machine, setMachine] = useState<MachineDto | null>(null);
  const [armed, setArmed] = useState(() =>
    initialFilter(params, 'armed', LOW_BALANCE_STATE_OPTIONS, ''),
  );
  const fetchPage = useCallback<FetchPage<LowBalanceAlertDto>>(
    (query, signal) => hoursStatementService.listLowBalanceAlerts(query, signal),
    [],
  );
  const clear = (key: string) => {
    const next = new URLSearchParams(params);
    next.delete(key);
    setParams(next);
  };
  const open = (a: LowBalanceAlertDto) => {
    void navigate(lowBalanceAlertPath(a.id));
  };
  const columns: DataColumn<LowBalanceAlertDto>[] = [
    { id: 'at', header: 'When', render: (a) => formatInstantIn(a.crossed_at, timeZone) },
    { id: 'customer', header: 'Customer', render: (a) => nameOr(a.customer_name, a.customer_id) },
    { id: 'machine', header: 'Machine', render: machineOf },
    { id: 'purchase', header: 'Purchase', render: purchaseText },
    {
      id: 'remaining',
      header: 'Left on the purchase',
      align: 'right',
      render: (a) => hoursText(a.remaining_hours),
    },
    {
      id: 'available',
      header: 'Left on the machine',
      align: 'right',
      render: (a) => hoursText(a.available_hours),
    },
    {
      id: 'threshold',
      header: 'Threshold',
      align: 'right',
      render: (a) => hoursText(a.threshold_hours),
    },
    { id: 'state', header: 'State', render: stateChip },
  ];
  return (
    <>
      <PageHeader
        title="Low-balance warnings"
        subtitle="Prepaid hours that fell to the company's low-balance threshold"
      />
      <HoursOffNotice off={hours.status === 'known' && !hours.on} />
      <Stack spacing={2}>
        {(urlPurchase !== undefined || urlCustomer !== undefined) && (
          <Box className="flex flex-wrap gap-2">
            {urlPurchase !== undefined && (
              <Chip
                label="One purchase"
                onDelete={() => {
                  clear('purchase_id');
                }}
              />
            )}
            {urlCustomer !== undefined && (
              <Chip
                label="One customer"
                onDelete={() => {
                  clear('customer_id');
                }}
              />
            )}
          </Box>
        )}
        <ServerDataTable
          columns={columns}
          fetchPage={fetchPage}
          getRowId={(a) => a.id}
          searchable={false}
          filters={{
            purchase_id: purchase?.id ?? urlPurchase,
            customer_id: customer?.id ?? urlCustomer,
            machine_id: machine?.id,
            armed: armed === '' ? undefined : armed,
          }}
          emptyTitle="No low-balance warnings"
          emptyDescription="Warnings appear when the company sets a low-balance threshold for customer hours."
          isRowMuted={(a) => a.rearmed_at !== null}
          onRowClick={open}
          toolbar={
            <Box className="flex flex-wrap gap-3">
              <Box sx={{ minWidth: 220 }}>
                <PurchaseFilter label="Purchase" value={purchase} onChange={setPurchase} />
              </Box>
              <Box sx={{ minWidth: 240 }}>
                <CustomerFilter label="Customer" value={customer} onChange={setCustomer} />
              </Box>
              <Box sx={{ minWidth: 220 }}>
                <MachineFilter label="Machine" value={machine} onChange={setMachine} />
              </Box>
              <StaticSelectFilter
                label="State"
                value={armed}
                options={LOW_BALANCE_STATE_OPTIONS}
                allLabel="All warnings"
                onChange={setArmed}
              />
            </Box>
          }
        />
      </Stack>
    </>
  );
}

const loadAlert = (id: string, signal: AbortSignal) =>
  hoursStatementService.getLowBalanceAlert(id, signal);

/** One low-balance warning: the figures when it was raised, who was told, and the purchase. */
export function LowBalanceAlertDetailPage() {
  const { id } = useParams();
  const timeZone = useDisplayTimeZone();
  const res = useRecordById(loadAlert, id);
  return (
    <RecordDetail
      resource={res}
      what="low-balance warning"
      back={{ label: 'Low-balance warnings', to: HOURS_ROUTES.lowBalanceAlerts }}
      timeZone={timeZone}
      title={(a) => `Low balance · ${purchaseText(a)}`}
      subtitle={(a) => `${nameOr(a.customer_name, a.customer_id)} · ${machineOf(a)}`}
      status={stateChip}
      links={(a) => (
        <Button component={RouterLink} to={hoursPurchasePath(a.purchase_id)} variant="outlined">
          Open the purchase
        </Button>
      )}
      items={(a) => [
        {
          label: 'Customer',
          value: (
            <Link component={RouterLink} to={customerDetailPath(a.customer_id)}>
              {nameOr(a.customer_name, a.customer_id)}
            </Link>
          ),
        },
        { label: 'Machine', value: machineOf(a) },
        {
          label: 'Purchase',
          value: (
            <Link component={RouterLink} to={hoursPurchasePath(a.purchase_id)}>
              {purchaseText(a)}
            </Link>
          ),
        },
        { label: 'Threshold', value: hoursText(a.threshold_hours) },
        { label: 'Left on the purchase', value: hoursText(a.remaining_hours) },
        { label: 'Left for the customer on this machine', value: hoursText(a.available_hours) },
        { label: 'Warning number', value: String(a.sequence) },
        {
          label: 'Customer SMS',
          value: a.notify_customer
            ? LOW_BALANCE_SMS_LABELS[a.customer_sms_status]
            : LOW_BALANCE_SMS_LABELS.NOT_REQUESTED,
        },
        { label: 'Policy version', value: a.policy_version },
      ]}
      history={(a) => [
        { key: 'crossed', label: 'Fell to the threshold', at: a.crossed_at },
        ...(a.rearmed_at === null
          ? []
          : [{ key: 'rearmed', label: 'Back above the threshold', at: a.rearmed_at }]),
      ]}
    />
  );
}
