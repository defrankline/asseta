import { Typography } from '@mui/material';
import { useCallback, useMemo, useState } from 'react';
import {
  CHANNEL_DELIVERY_STATUSES,
  notificationChannelService,
  type ChannelConsole,
} from '../../api/services/notificationChannelService';
import type { NotificationChannelDeliveryDto } from '../../api/types';
import { ServerDataTable, type DataColumn } from '../../components/data/ServerDataTable';
import type { ServerQuery } from '../../components/data/useServerPage';
import { StatusChip, type StatusTone } from '../../components/display/StatusChip';
import type { SelectOption } from '../../components/forms/FormikSelectField';
import { StaticSelectFilter } from '../../components/forms/StaticSelectFilter';
import { formatInstant } from '../../utils/dates';
import { humanize } from '../../utils/text';

const STATUS_TONES: Readonly<Record<string, StatusTone>> = {
  PENDING: 'info',
  SENT: 'success',
  FAILED: 'error',
  UNDELIVERABLE: 'warning',
};

const CHANNEL_FILTER_OPTIONS: readonly SelectOption[] = [
  { value: 'PUSH', label: 'Push' },
  { value: 'EMAIL', label: 'E-mail' },
];

const STATUS_OPTIONS: readonly SelectOption[] = CHANNEL_DELIVERY_STATUSES.map((s) => ({
  value: s,
  label: humanize(s),
}));

const COLUMNS: DataColumn<NotificationChannelDeliveryDto>[] = [
  { id: 'created', header: 'Queued', render: (d) => formatInstant(d.created_at) },
  {
    id: 'channel',
    header: 'Channel',
    render: (d) => (d.channel === 'EMAIL' ? 'E-mail' : humanize(d.channel)),
  },
  { id: 'type', header: 'Notification', render: (d) => humanize(d.notification_type) },
  { id: 'severity', header: 'Severity', render: (d) => humanize(d.severity) },
  {
    id: 'status',
    header: 'Status',
    render: (d) => (
      <>
        <StatusChip status={d.status} tones={STATUS_TONES} />
        {d.last_error !== null && (
          <Typography variant="caption" color="text.secondary" component="div">
            {d.last_error}
          </Typography>
        )}
      </>
    ),
  },
  { id: 'attempts', header: 'Attempts', align: 'right', render: (d) => String(d.attempts) },
  { id: 'provider', header: 'Provider', render: (d) => d.provider ?? '—' },
  {
    id: 'sent',
    header: 'Sent',
    render: (d) => (d.sent_at === null ? '—' : formatInstant(d.sent_at)),
  },
];

/** PUSH and E-MAIL delivery log of the console (`/{console}/notification-deliveries`). */
export function ChannelDeliveriesTable({ console }: { console: ChannelConsole }) {
  const [channel, setChannel] = useState('');
  const [status, setStatus] = useState('');
  const filters = useMemo(
    () => ({ channel: channel || undefined, status: status || undefined }),
    [channel, status],
  );
  const fetchPage = useCallback(
    (q: ServerQuery, signal: AbortSignal) =>
      notificationChannelService.listDeliveries(
        console,
        { page: q.page, page_size: q.page_size, ...q.filters },
        signal,
      ),
    [console],
  );
  return (
    <ServerDataTable<NotificationChannelDeliveryDto>
      columns={COLUMNS}
      fetchPage={fetchPage}
      getRowId={(d) => d.id}
      filters={filters}
      searchable={false}
      emptyTitle="No push or e-mail deliveries"
      toolbar={
        <>
          <StaticSelectFilter
            label="Channel"
            value={channel}
            options={CHANNEL_FILTER_OPTIONS}
            onChange={setChannel}
            allLabel="Push and e-mail"
          />
          <StaticSelectFilter
            label="Delivery status"
            value={status}
            options={STATUS_OPTIONS}
            onChange={setStatus}
          />
        </>
      }
    />
  );
}
