import Add from '@mui/icons-material/Add';
import SwapHoriz from '@mui/icons-material/SwapHoriz';
import { Alert, Box, Button, Stack } from '@mui/material';
import { useCallback, useState } from 'react';
import { useNavigate } from 'react-router';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { useCanMutate } from '../../../access/useCanMutate';
import type { HoursPurchaseDto } from '../../../api/hoursTypes';
import { hoursService } from '../../../api/services/hoursService';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import type { FetchPage } from '../../../components/data/useServerPage';
import { MoneyText } from '../../../components/display/MoneyText';
import { StatusChip } from '../../../components/display/StatusChip';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { hoursPurchasePath } from '../../../navigation/hoursRoutes';
import { useNotify } from '../../../notifications/useNotify';
import { useSession } from '../../../session/useSession';
import { formatInstantIn } from '../../../utils/time';
import { machineText, nameOr } from '../shared/names';
import { HoursOffNotice } from './HoursDialogs';
import { hoursText, PURCHASE_STATUS_LABELS, PURCHASE_STATUS_TONES } from './hoursDisplay';
import { RequestTransferDialog } from './PurchaseActionDialogs';
import { RecordPurchaseDialog } from './RecordPurchaseDialog';
import { useHoursPolicy } from './useHoursPolicy';

type Open = 'purchase' | 'transfer' | null;

/**
 * Field work: record a customer's (or a walk-in's) hours purchase with the cash collected and an
 * evidence photo, and request hours transfers between machines. Same actions as the field app.
 */
export function FieldHoursPage() {
  const notify = useNotify();
  const navigate = useNavigate();
  const timeZone = useDisplayTimeZone();
  const { hasPermission } = useSession();
  const hours = useHoursPolicy();
  const canRecord = useCanMutate(PERMISSIONS.tenantHoursPurchase) && hours.on;
  const canTransfer = useCanMutate(PERMISSIONS.tenantHoursTransfer) && hours.on;
  const canRead = hasPermission(PERMISSIONS.tenantHoursRead);
  const [open, setOpen] = useState<Open>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const fetchPage = useCallback<FetchPage<HoursPurchaseDto>>(
    (query, signal) => hoursService.listPurchases(query, signal),
    [],
  );
  const columns: DataColumn<HoursPurchaseDto>[] = [
    { id: 'number', header: 'Purchase', render: (p) => <strong>{p.purchase_number}</strong> },
    { id: 'customer', header: 'Customer', render: (p) => nameOr(p.customer_name, p.customer_id) },
    {
      id: 'machine',
      header: 'Machine',
      render: (p) => machineText(p.machine_code, p.machine_name, p.machine_id),
    },
    { id: 'hours', header: 'Hours', align: 'right', render: (p) => hoursText(p.hours) },
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
    { id: 'at', header: 'Recorded', render: (p) => formatInstantIn(p.created_at, timeZone) },
  ];
  const close = () => {
    setOpen(null);
  };
  return (
    <>
      <PageHeader
        title="Customer hours"
        subtitle="Record hours a customer buys (with the cash you collect) and request transfers"
        actions={
          <Box className="flex flex-wrap gap-2">
            {canTransfer && canRead && (
              <Button
                variant="outlined"
                startIcon={<SwapHoriz />}
                onClick={() => {
                  setOpen('transfer');
                }}
              >
                Request transfer
              </Button>
            )}
            {canRecord && (
              <Button
                variant="contained"
                startIcon={<Add />}
                onClick={() => {
                  setOpen('purchase');
                }}
              >
                Record customer hours
              </Button>
            )}
          </Box>
        }
      />
      <Stack spacing={2}>
        <HoursOffNotice off={hours.status === 'known' && !hours.on} />
        <Alert severity="info">
          Cash you record stays in your custody as claimed until the office verifies it; only then
          do the customer’s hours activate.
        </Alert>
        {canRead && (
          <ServerDataTable
            columns={columns}
            fetchPage={fetchPage}
            getRowId={(p) => p.id}
            searchPlaceholder="Search purchase number"
            initialSort="-created_at"
            reloadKey={reloadKey}
            emptyTitle="No hours purchases yet"
            onRowClick={(p) => {
              void navigate(hoursPurchasePath(p.id));
            }}
          />
        )}
      </Stack>
      {open === 'purchase' && (
        <RecordPurchaseDialog
          field
          timeZone={timeZone}
          walkInAllowed={hours.policy?.walkInAllowed ?? true}
          onClose={close}
          onRecorded={(p) => {
            notify.success(`Hours purchase ${p.purchase_number} recorded.`);
            setReloadKey((k) => k + 1);
          }}
        />
      )}
      {open === 'transfer' && (
        <RequestTransferDialog
          reasonCodeRequired={hours.policy?.reasonCodeRequired ?? false}
          onClose={close}
          onDone={() => {
            notify.success('Transfer requested; someone else decides it.');
          }}
        />
      )}
    </>
  );
}
