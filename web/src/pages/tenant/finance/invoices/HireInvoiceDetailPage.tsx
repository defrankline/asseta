import { Alert, Box, Button, Typography } from '@mui/material';
import { useCallback, useState } from 'react';
import { Link as RouterLink, useParams } from 'react-router';
import { PERMISSIONS } from '../../../../access/permissionCodes';
import { useCanMutate } from '../../../../access/useCanMutate';
import { hireInvoiceService } from '../../../../api/services/financeService';
import type { HireInvoiceDto } from '../../../../api/types';
import type { DataColumn } from '../../../../components/data/ServerDataTable';
import { StaticTable } from '../../../../components/data/StaticTable';
import { KeyValueGrid } from '../../../../components/display/KeyValueGrid';
import { MoneyText } from '../../../../components/display/MoneyText';
import { StatusChip } from '../../../../components/display/StatusChip';
import { AsyncContent } from '../../../../components/feedback/AsyncContent';
import { ActionButtons } from '../../../../components/lifecycle/ActionButtons';
import {
  DetailSection,
  EntityDetailsLayout,
} from '../../../../components/lifecycle/EntityDetailsLayout';
import { useAsyncResource } from '../../../../hooks/useAsyncResource';
import { useDisplayTimeZone } from '../../../../hooks/useDisplayTimeZone';
import { customerDetailPath, financeTabPath } from '../../../../navigation/routes';
import { useNotify } from '../../../../notifications/useNotify';
import { formatDate } from '../../../../utils/dates';
import { formatInstantIn } from '../../../../utils/time';
import {
  PAYMENT_METHOD_LABELS,
  SETTLEMENT_LABELS,
  SETTLEMENT_TONES,
} from '../../shared/financeDisplay';
import { useCustomerLabels } from '../../shared/useFinanceLabels';
import { useMachineLabels } from '../../shared/useMachineLabels';
import { RecordPaymentDialog } from '../payments/RecordPaymentDialog';
import {
  invoiceTitle,
  useInvoiceAllocations,
  useInvoiceJobLabels,
  type InvoiceAllocation,
} from './invoiceData';
import { InvoiceLinesTable, InvoiceStatusChips, InvoiceTotals } from './InvoiceViews';
import { useInvoiceActions } from './useInvoiceActions';
import { ENTITY, entityKey } from '../../../../realtime/entities';
import { useLiveRefresh } from '../../../../realtime/hooks';

function AllocationsSection({ invoice, timeZone }: { invoice: HireInvoiceDto; timeZone: string }) {
  const res = useInvoiceAllocations(invoice);
  const cur = invoice.currency;
  const columns: DataColumn<InvoiceAllocation>[] = [
    {
      id: 'received',
      header: 'Received',
      render: (r) => formatInstantIn(r.payment.received_at, timeZone),
    },
    { id: 'method', header: 'Method', render: (r) => PAYMENT_METHOD_LABELS[r.payment.method] },
    { id: 'ref', header: 'Reference', render: (r) => r.payment.reference ?? '—' },
    {
      id: 'status',
      header: 'Payment status',
      render: (r) => (
        <StatusChip
          status={r.payment.status}
          tones={SETTLEMENT_TONES}
          label={SETTLEMENT_LABELS[r.payment.status]}
        />
      ),
    },
    {
      id: 'amount',
      header: 'Allocated',
      align: 'right',
      render: (r) => <MoneyText amount={r.allocation.amount} currency={cur} />,
    },
    {
      id: 'released',
      header: 'Released',
      render: (r) =>
        r.allocation.released_at === null
          ? '—'
          : `${formatInstantIn(r.allocation.released_at, timeZone)} · ${r.allocation.release_reason ?? ''}`,
    },
  ];
  return (
    <DetailSection title="Payments allocated">
      <Typography variant="body2" color="text.secondary" className="mb-2">
        Only VERIFIED payments count as paid. CLAIMED allocations reserve the amount until verified;
        rejected payments and voided invoices release their allocations.
      </Typography>
      <AsyncContent
        resource={res}
        isEmpty={(rows) => rows.length === 0}
        emptyTitle="No payments allocated"
        errorTitle="Could not load payments"
      >
        {(rows) => (
          <StaticTable
            ariaLabel="Payments allocated"
            columns={columns}
            rows={rows}
            getRowId={(r) => r.allocation.id}
            isRowMuted={(r) => r.allocation.released_at !== null || r.payment.status === 'REJECTED'}
          />
        )}
      </AsyncContent>
    </DetailSection>
  );
}

function InvoiceBody({ invoice: i, timeZone }: { invoice: HireInvoiceDto; timeZone: string }) {
  const customerLabel = useCustomerLabels();
  const machineLabel = useMachineLabels();
  const jobLabel = useInvoiceJobLabels(i.job_ids);
  return (
    <Box className="flex flex-col gap-6">
      {i.status === 'DRAFT' && (
        <Alert severity="info">
          Draft: lines are copied from the jobs’ current charges and can still change. The API does
          not add or remove jobs on a draft — to change the jobs, discard this draft (void) and
          create a new one. Issuing re-checks the charges and freezes the invoice.
        </Alert>
      )}
      <DetailSection title="Invoice">
        <KeyValueGrid
          columns={4}
          items={[
            {
              label: 'Customer',
              value: (
                <RouterLink to={customerDetailPath(i.customer_id)}>
                  {customerLabel(i.customer_id)}
                </RouterLink>
              ),
            },
            { label: 'Currency', value: i.currency },
            { label: 'Created', value: formatInstantIn(i.created_at, timeZone) },
            {
              label: 'Issued',
              value: i.issued_at === null ? 'Not issued' : formatInstantIn(i.issued_at, timeZone),
            },
            { label: 'Due date', value: formatDate(i.due_date) },
            { label: 'Jobs', value: i.job_ids.map(jobLabel).join(', ') },
            { label: 'Notes', value: i.notes ?? '—' },
          ]}
        />
      </DetailSection>
      <DetailSection title={i.status === 'DRAFT' ? 'Lines (draft)' : 'Lines (issued snapshot)'}>
        <InvoiceLinesTable invoice={i} jobLabel={jobLabel} machineLabel={machineLabel} />
        <InvoiceTotals invoice={i} />
      </DetailSection>
      {i.status !== 'DRAFT' && <AllocationsSection invoice={i} timeZone={timeZone} />}
    </Box>
  );
}

/** Draft / issued / voided hire invoice with its lines, totals, allocated payments and commands. */
export function HireInvoiceDetailPage() {
  const { invoiceId = '' } = useParams();
  const timeZone = useDisplayTimeZone();
  const notify = useNotify();
  const canPay = useCanMutate(PERMISSIONS.tenantFinancePayment);
  const [paying, setPaying] = useState(false);
  const load = useCallback(
    (signal: AbortSignal) => hireInvoiceService.get(invoiceId, signal),
    [invoiceId],
  );
  const res = useAsyncResource(load);
  // Issue / void / payments on this invoice are pushed by the server.
  useLiveRefresh([entityKey(ENTITY.hireInvoice, invoiceId), ENTITY.customerPayment], res.reload);
  const inv = res.data;
  const { actionsFor, dialogs } = useInvoiceActions({ onChanged: res.reload, onDetails: true });
  const actions = inv === null ? [] : actionsFor(inv);
  if (inv !== null && canPay && inv.status === 'ISSUED' && inv.payment_state !== 'PAID') {
    actions.unshift({
      key: 'pay',
      label: 'Record payment',
      onClick: () => {
        setPaying(true);
      },
    });
  }
  return (
    <>
      <EntityDetailsLayout
        title={inv === null ? 'Hire invoice' : invoiceTitle(inv)}
        subtitle="Customer hire invoice"
        back={{ label: 'All hire invoices', to: financeTabPath('invoices') }}
        {...(inv !== null
          ? {
              status: <InvoiceStatusChips invoice={inv} />,
              actions: <ActionButtons actions={actions} primaryKey="issue" />,
            }
          : {})}
        inactive={
          inv?.status === 'VOIDED'
            ? {
                title: 'This invoice is voided (reversed). It is kept unchanged for audit.',
                reason: inv.void_reason,
                since: inv.voided_at === null ? null : formatInstantIn(inv.voided_at, timeZone),
              }
            : null
        }
      >
        {inv !== null && inv.status === 'VOIDED' && (
          <Alert severity="warning">
            {inv.issued_at === null ? (
              'This draft was discarded before issue; its jobs were released and no reversal was needed.'
            ) : (
              <>
                A reversal of <MoneyText amount={inv.total} currency={inv.currency} strong /> was
                recorded on the customer’s statement. Allocated payments were released back to
                customer credit and the jobs became invoiceable again.
              </>
            )}
          </Alert>
        )}
        <AsyncContent
          resource={res}
          errorTitle="Could not load the invoice"
          loadingLabel="Loading invoice"
        >
          {(i) => <InvoiceBody invoice={i} timeZone={timeZone} />}
        </AsyncContent>
        <Box>
          <Button component={RouterLink} to={financeTabPath('payments')} size="small">
            All customer payments
          </Button>
        </Box>
      </EntityDetailsLayout>
      {paying && inv !== null && (
        <RecordPaymentDialog
          invoice={inv}
          timeZone={timeZone}
          onClose={() => {
            setPaying(false);
          }}
          onRecorded={() => {
            notify.success('Payment recorded as CLAIMED; it counts once verified.');
            res.reload();
          }}
        />
      )}
      {dialogs}
    </>
  );
}
