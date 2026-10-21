import {
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Paper,
  Stack,
  Typography,
} from '@mui/material';
import { useCallback, useState } from 'react';
import { tenantBillingService } from '../../../api/services/tenantBillingService';
import type { InvoiceDto, SubscriptionDto } from '../../../api/types';
import type { DataColumn } from '../../../components/data/ServerDataTable';
import { StaticTable } from '../../../components/data/StaticTable';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { MoneyText } from '../../../components/display/MoneyText';
import { StatusChip } from '../../../components/display/StatusChip';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { formatDate } from '../../../utils/dates';
import { humanize } from '../../../utils/text';
import { InvoiceSummary } from '../../platform/invoices/InvoiceSummary';
import { INVOICE_TONES, SUBSCRIPTION_TONES } from '../../platform/shared/billingDisplay';

function SubscriptionSummary({ subscription: s }: { subscription: SubscriptionDto }) {
  const rate = s.current_rate;
  return (
    <Paper variant="outlined" className="p-4">
      <Stack spacing={2}>
        <Typography variant="h6" component="h2">
          Agreement {s.agreement_number}
        </Typography>
        <KeyValueGrid
          columns={4}
          items={[
            {
              label: 'Status',
              value: <StatusChip status={s.status} tones={SUBSCRIPTION_TONES} />,
            },
            {
              label: 'Current period',
              value:
                s.current_period_start === null
                  ? '—'
                  : `${formatDate(s.current_period_start)} – ${formatDate(s.current_period_end)}`,
            },
            {
              label: 'Billable / enrolled assets',
              value: `${String(s.billable_assets)} / ${String(s.enrolled_assets)}`,
            },
            {
              label: 'Price per asset',
              value:
                rate === null ? (
                  '—'
                ) : (
                  <span>
                    <MoneyText amount={rate.unit_price} currency={rate.currency} strong /> /{' '}
                    {humanize(rate.cadence).toLowerCase()}
                  </span>
                ),
            },
            { label: 'Minimum billable assets', value: rate?.minimum_billable_assets ?? '—' },
            { label: 'Payment terms', value: `${String(s.payment_terms_days)} days` },
            { label: 'Billing start', value: formatDate(s.billing_start_date) },
            {
              label: 'Cancellation effective',
              value: formatDate(s.cancellation_effective_date),
            },
          ]}
        />
        <Typography variant="caption" color="text.secondary">
          Pricing is negotiated with the platform and is read-only here.
        </Typography>
      </Stack>
    </Paper>
  );
}

function InvoiceDialog({ invoice, onClose }: { invoice: InvoiceDto; onClose: () => void }) {
  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="md" aria-labelledby="tenant-invoice-title">
      <DialogTitle id="tenant-invoice-title">
        Invoice {invoice.invoice_number ?? '(preview)'}
      </DialogTitle>
      <DialogContent dividers>
        <InvoiceSummary invoice={invoice} />
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
}

/** Tenant's own subscription and platform invoices (read-only). */
export function TenantSubscriptionPage() {
  const [viewing, setViewing] = useState<InvoiceDto | null>(null);
  const loadSubscription = useCallback(
    (signal: AbortSignal) => tenantBillingService.subscription(signal),
    [],
  );
  const loadInvoices = useCallback(
    (signal: AbortSignal) => tenantBillingService.invoices(signal),
    [],
  );
  const subscription = useAsyncResource(loadSubscription);
  const invoices = useAsyncResource(loadInvoices);

  const columns: DataColumn<InvoiceDto>[] = [
    { id: 'number', header: 'Invoice no.', render: (i) => i.invoice_number ?? '—' },
    {
      id: 'period',
      header: 'Period',
      render: (i) => `${formatDate(i.period_start)} – ${formatDate(i.period_end)}`,
    },
    { id: 'due', header: 'Due', render: (i) => formatDate(i.due_date) },
    {
      id: 'status',
      header: 'Status',
      render: (i) =>
        i.status !== null ? <StatusChip status={i.status} tones={INVOICE_TONES} /> : '—',
    },
    {
      id: 'total',
      header: 'Total',
      align: 'right',
      render: (i) => <MoneyText amount={i.total} currency={i.currency} />,
    },
    {
      id: 'balance',
      header: 'Balance',
      align: 'right',
      render: (i) => <MoneyText amount={i.balance} currency={i.currency} strong />,
    },
    {
      id: 'view',
      header: '',
      align: 'right',
      render: (i) => (
        <Button
          size="small"
          onClick={() => {
            setViewing(i);
          }}
        >
          View
        </Button>
      ),
    },
  ];

  return (
    <>
      <PageHeader title="Subscription" subtitle="Your Asseta subscription and platform invoices" />
      <Stack spacing={3}>
        <AsyncContent
          resource={subscription}
          errorTitle="Could not load your subscription"
          loadingLabel="Loading subscription"
        >
          {(s) => <SubscriptionSummary subscription={s} />}
        </AsyncContent>
        <Paper variant="outlined" className="p-4">
          <Typography variant="h6" component="h2" className="mb-2">
            Invoices
          </Typography>
          <AsyncContent
            resource={invoices}
            isEmpty={(xs) => xs.length === 0}
            emptyTitle="No invoices yet"
            errorTitle="Could not load invoices"
            loadingLabel="Loading invoices"
          >
            {(xs) => (
              <StaticTable
                ariaLabel="Invoices"
                columns={columns}
                rows={xs}
                getRowId={(i) => i.id ?? `${i.period_start}-${i.period_end}`}
              />
            )}
          </AsyncContent>
        </Paper>
      </Stack>
      {viewing !== null && (
        <InvoiceDialog
          invoice={viewing}
          onClose={() => {
            setViewing(null);
          }}
        />
      )}
    </>
  );
}
