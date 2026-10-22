import Send from '@mui/icons-material/Send';
import { Button, Typography } from '@mui/material';
import { useCallback, useMemo, useState } from 'react';
import { Link as RouterLink } from 'react-router';
import { object, string } from 'yup';
import { PERMISSIONS } from '../../access/permissionCodes';
import { SMS_DELIVERY_STATUSES } from '../../api/services/notificationSchemas';
import type { NotificationTestSendIn, SmsDeliveryDto } from '../../api/types';
import { ServerDataTable, type DataColumn } from '../../components/data/ServerDataTable';
import type { ServerQuery } from '../../components/data/useServerPage';
import { StatusChip, type StatusTone } from '../../components/display/StatusChip';
import { PageHeader } from '../../components/feedback/PageHeader';
import { FormDialog } from '../../components/forms/FormDialog';
import { FormikTextField } from '../../components/forms/FormikTextField';
import type { SelectOption } from '../../components/forms/FormikSelectField';
import { StaticSelectFilter } from '../../components/forms/StaticSelectFilter';
import { useIdempotencyKey } from '../../hooks/useIdempotencyKey';
import { ROUTES } from '../../navigation/routes';
import { useNotificationCenter } from '../../notifications/center/NotificationCenterContext';
import { useNotify } from '../../notifications/useNotify';
import { useSession } from '../../session/useSession';
import { formatInstant } from '../../utils/dates';
import { humanize } from '../../utils/text';

const STATUS_TONES: Readonly<Record<string, StatusTone>> = {
  PENDING: 'info',
  SENT: 'success',
  FAILED: 'error',
  REFUSED_NO_CREDIT: 'warning',
  INVALID_NUMBER: 'warning',
};

const STATUS_OPTIONS: readonly SelectOption[] = SMS_DELIVERY_STATUSES.map((s) => ({
  value: s,
  label: humanize(s),
}));

const COLUMNS: DataColumn<SmsDeliveryDto>[] = [
  { id: 'created', header: 'Queued', render: (d) => formatInstant(d.created_at) },
  { id: 'type', header: 'Notification', render: (d) => humanize(d.notification_type) },
  { id: 'msisdn', header: 'Number', render: (d) => d.msisdn },
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
  { id: 'segments', header: 'Segments', align: 'right', render: (d) => String(d.segments) },
  { id: 'attempts', header: 'Attempts', align: 'right', render: (d) => String(d.attempts) },
  { id: 'billable', header: 'Wallet-billed', render: (d) => (d.billable ? 'Yes' : 'No') },
  {
    id: 'sent',
    header: 'Sent',
    render: (d) => (d.sent_at === null ? '—' : formatInstant(d.sent_at)),
  },
];

const testSchema = object({
  title: string().trim().required('Title is required').max(120, 'At most 120 characters'),
  body: string().trim().required('Message is required').max(300, 'At most 300 characters'),
  msisdn: string().trim().max(32, 'At most 32 characters').ensure(),
});

function TestSendDialog({ onClose, onSent }: { onClose: () => void; onSent: () => void }) {
  const { service } = useNotificationCenter();
  const notify = useNotify();
  const keyFor = useIdempotencyKey();
  return (
    <FormDialog
      open
      title="Send a test notification"
      initialValues={{
        title: 'Asseta test notification',
        body: 'If you can read this, notifications reach you.',
        msisdn: '',
      }}
      validationSchema={testSchema}
      submitLabel="Send test"
      onClose={onClose}
      onSubmit={async (v) => {
        if (service.testSend === undefined) return;
        const body: NotificationTestSendIn = {
          title: v.title.trim(),
          body: v.body.trim(),
          msisdn: v.msisdn.trim() === '' ? null : v.msisdn.trim(),
        };
        const result = await service.testSend(body, keyFor(body));
        notify.success(
          result.delivery === null
            ? 'Test notification sent to your inbox.'
            : `Test notification sent; SMS ${humanize(result.delivery.status).toLowerCase()}.`,
        );
        onSent();
      }}
    >
      <FormikTextField name="title" label="Title" required />
      <FormikTextField name="body" label="Message" required multiline minRows={2} />
      <FormikTextField
        name="msisdn"
        label="Also send an SMS to (optional)"
        helperText="Uses the configured SMS provider (the console provider in development)."
      />
    </FormDialog>
  );
}

/** SMS delivery log of the current console (`*.notification.manage`), with platform test-send. */
export function SmsDeliveriesPage() {
  const { service } = useNotificationCenter();
  const { hasPermission } = useSession();
  const canTest =
    service.testSend !== undefined && hasPermission(PERMISSIONS.platformNotificationManage);
  const [status, setStatus] = useState('');
  const [reloadKey, setReloadKey] = useState(0);
  const [testing, setTesting] = useState(false);
  const filters = useMemo(() => ({ status: status === '' ? undefined : status }), [status]);
  const fetchPage = useCallback(
    (q: ServerQuery, signal: AbortSignal) => {
      const st = SMS_DELIVERY_STATUSES.find((s) => s === q.filters.status);
      return service.listDeliveries(
        {
          page: q.page,
          page_size: q.page_size,
          ...(q.q !== undefined && q.q !== '' ? { q: q.q } : {}),
          ...(st !== undefined ? { status: st } : {}),
        },
        signal,
      );
    },
    [service],
  );
  return (
    <>
      <PageHeader
        title="SMS delivery log"
        subtitle="SMS notifications sent from this console: status, segments and wallet billing"
        actions={
          <>
            <Button component={RouterLink} to={ROUTES.notifications}>
              Back to notifications
            </Button>
            {canTest && (
              <Button
                variant="contained"
                startIcon={<Send />}
                onClick={() => {
                  setTesting(true);
                }}
              >
                Send test
              </Button>
            )}
          </>
        }
      />
      <ServerDataTable<SmsDeliveryDto>
        columns={COLUMNS}
        fetchPage={fetchPage}
        getRowId={(d) => d.id}
        filters={filters}
        searchPlaceholder="Search number or type"
        reloadKey={reloadKey}
        emptyTitle="No SMS deliveries"
        toolbar={
          <StaticSelectFilter
            label="Status"
            value={status}
            options={STATUS_OPTIONS}
            onChange={setStatus}
          />
        }
      />
      {testing && (
        <TestSendDialog
          onClose={() => {
            setTesting(false);
          }}
          onSent={() => {
            setReloadKey((k) => k + 1);
          }}
        />
      )}
    </>
  );
}
