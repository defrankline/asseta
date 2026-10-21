import { Box, Button } from '@mui/material';
import { useCallback, useState } from 'react';
import { Can } from '../../../access/Can';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { subscriptionService } from '../../../api/services/subscriptionService';
import type { PendingChargeDto } from '../../../api/types';
import type { DataColumn } from '../../../components/data/ServerDataTable';
import { StaticTable } from '../../../components/data/StaticTable';
import { MoneyText } from '../../../components/display/MoneyText';
import { StatusChip } from '../../../components/display/StatusChip';
import { humanize } from '../../../utils/text';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useNotify } from '../../../notifications/useNotify';
import { formatDate } from '../../../utils/dates';
import { PENDING_CHARGE_TONES } from '../shared/billingDisplay';
import { OverrideChargeDialog } from './OverrideChargeDialog';

interface PendingChargesTabProps {
  subscriptionId: string;
  /** Currency of the subscription's current rate (pending charges carry no currency). */
  currency: string;
  reloadKey: number;
}

export function PendingChargesTab({ subscriptionId, currency, reloadKey }: PendingChargesTabProps) {
  const notify = useNotify();
  const [editing, setEditing] = useState<PendingChargeDto | null>(null);
  const load = useCallback(
    (signal: AbortSignal) => subscriptionService.listPendingCharges(subscriptionId, signal),
    [subscriptionId],
  );
  const charges = useAsyncResource(load, [reloadKey]);

  const columns: DataColumn<PendingChargeDto>[] = [
    { id: 'type', header: 'Type', render: (c) => humanize(c.line_type) },
    {
      id: 'service',
      header: 'Service period',
      render: (c) => `${formatDate(c.service_from)} – ${formatDate(c.service_to)}`,
    },
    {
      id: 'days',
      header: 'Days',
      align: 'right',
      render: (c) => `${String(c.days)}/${String(c.period_days)}`,
    },
    {
      id: 'computed',
      header: 'Computed',
      align: 'right',
      render: (c) => <MoneyText amount={c.computed_amount} currency={currency} />,
    },
    {
      id: 'amount',
      header: 'Amount',
      align: 'right',
      render: (c) => <MoneyText amount={c.amount} currency={currency} strong />,
    },
    {
      id: 'status',
      header: 'Status',
      render: (c) => <StatusChip status={c.status} tones={PENDING_CHARGE_TONES} />,
    },
    { id: 'override', header: 'Override reason', render: (c) => c.override_reason ?? '—' },
    {
      id: 'actions',
      header: '',
      align: 'right',
      render: (c) =>
        c.status === 'PENDING' ? (
          <Can permission={PERMISSIONS.platformCreditManage}>
            <Button
              size="small"
              onClick={() => {
                setEditing(c);
              }}
            >
              Override
            </Button>
          </Can>
        ) : null,
    },
  ];

  return (
    <Box>
      <AsyncContent
        resource={charges}
        isEmpty={(r) => r.length === 0}
        emptyTitle="No pending charges"
      >
        {(rows) => (
          <StaticTable
            ariaLabel="Pending charges"
            columns={columns}
            rows={rows}
            getRowId={(c) => c.id}
          />
        )}
      </AsyncContent>
      {editing !== null && (
        <OverrideChargeDialog
          charge={editing}
          currency={currency}
          onClose={() => {
            setEditing(null);
          }}
          onOverridden={() => {
            notify.success('Pending charge overridden.');
            charges.reload();
          }}
        />
      )}
    </Box>
  );
}
