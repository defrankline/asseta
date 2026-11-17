import { Link, Paper, Stack, Typography } from '@mui/material';
import { useCallback, useState, type ReactNode } from 'react';
import { Link as RouterLink, useParams } from 'react-router';
import { PERMISSIONS } from '../../../../access/permissionCodes';
import { useCanMutate } from '../../../../access/useCanMutate';
import type { CreditInvoiceDto, CreditInvoicePaymentDto } from '../../../../api/hoursTypes';
import { creditInvoiceService } from '../../../../api/services/creditInvoiceService';
import { StaticTable } from '../../../../components/data/StaticTable';
import { KeyValueGrid } from '../../../../components/display/KeyValueGrid';
import { MoneyText } from '../../../../components/display/MoneyText';
import { AsyncContent } from '../../../../components/feedback/AsyncContent';
import { ActionButtons } from '../../../../components/lifecycle/ActionButtons';
import { EntityDetailsLayout } from '../../../../components/lifecycle/EntityDetailsLayout';
import { useAsyncResource } from '../../../../hooks/useAsyncResource';
import { useDisplayTimeZone } from '../../../../hooks/useDisplayTimeZone';
import { HOURS_ROUTES, hoursPurchasePath } from '../../../../navigation/hoursRoutes';
import { customerDetailPath, customerPaymentPath } from '../../../../navigation/routes';
import { useNotify } from '../../../../notifications/useNotify';
import { useSession } from '../../../../session/useSession';
import { formatInstantIn } from '../../../../utils/time';
import { PersonName } from '../../shared/PersonName';
import { machineText, nameOr } from '../../shared/names';
import { HoursOffNotice } from '../HoursDialogs';
import { hoursText } from '../hoursDisplay';
import { money } from '../hoursQuote';
import { SALE_METHOD_LABELS } from '../saleMethods';
import { useHoursPolicy } from '../useHoursPolicy';
import { useMyUserId } from '../../shared/useFinanceLabels';
import { RejectCreditDialog } from '../PurchaseActionDialogs';
import { CreditInvoiceStatus, CreditRejectionNotice } from './CreditInvoiceParts';
import { invoicePaymentStatusText } from './creditInvoiceDisplay';
import { RecordInvoicePaymentDialog } from './RecordInvoicePaymentDialog';

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Paper variant="outlined" className="p-4">
      <Stack spacing={2}>
        <Typography variant="h6" component="h2">
          {title}
        </Typography>
        {children}
      </Stack>
    </Paper>
  );
}

function linkTo(to: string, text: string, linked: boolean): ReactNode {
  if (!linked) return text;
  return (
    <Link component={RouterLink} to={to}>
      {text}
    </Link>
  );
}

function paymentColumns(invoice: CreditInvoiceDto, timeZone: string, canOpenPayments: boolean) {
  return [
    {
      id: 'at',
      header: 'Received',
      render: (p: CreditInvoicePaymentDto) => formatInstantIn(p.received_at, timeZone),
    },
    {
      id: 'method',
      header: 'Method',
      render: (p: CreditInvoicePaymentDto) => SALE_METHOD_LABELS[p.method],
    },
    {
      id: 'amount',
      header: 'Amount',
      align: 'right' as const,
      render: (p: CreditInvoicePaymentDto) => (
        <MoneyText amount={p.amount} currency={invoice.currency} />
      ),
    },
    {
      id: 'ref',
      header: 'Reference',
      render: (p: CreditInvoicePaymentDto) =>
        linkTo(
          customerPaymentPath(p.payment_id),
          p.collection_number ?? p.reference ?? 'Open payment',
          canOpenPayments,
        ),
    },
    {
      id: 'by',
      header: 'Received by',
      render: (p: CreditInvoicePaymentDto) =>
        p.received_by_staff_name ?? <PersonName userId={p.recorded_by} name={p.recorded_by_name} />,
    },
    {
      id: 'status',
      header: 'Status',
      render: (p: CreditInvoicePaymentDto) => invoicePaymentStatusText(p),
    },
  ];
}

/** One credit invoice: what it is for, what is paid (and verified), the balance and its payments. */
export function CreditInvoiceDetailPage() {
  const { id = '' } = useParams();
  const notify = useNotify();
  const timeZone = useDisplayTimeZone();
  const hours = useHoursPolicy();
  const { hasPermission } = useSession();
  const canPay = useCanMutate(PERMISSIONS.tenantHoursInvoicePayment) && hours.on;
  const canOpenCustomer = hasPermission(PERMISSIONS.tenantCustomerRead);
  const canOpenPayments = hasPermission(PERMISSIONS.tenantFinanceRead);
  const canDecideCredit = useCanMutate(PERMISSIONS.tenantHoursCreditActivate) && hours.on;
  const me = useMyUserId();
  const [paying, setPaying] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const load = useCallback((signal: AbortSignal) => creditInvoiceService.get(id, signal), [id]);
  const res = useAsyncResource(load, [reloadKey]);
  const inv = res.data;
  const open = inv !== null && inv.status !== 'PAID' && inv.status !== 'CANCELLED';
  // Credit can be rejected while nothing is paid on the invoice, never by the person who recorded the sale.
  const rejectable =
    inv !== null &&
    inv.status === 'UNPAID' &&
    inv.payments.every((p) => !p.counts) &&
    !(inv.created_by !== null && inv.created_by === me);
  return (
    <EntityDetailsLayout
      title={inv === null ? 'Credit invoice' : inv.invoice_number}
      subtitle="Credit part of an order"
      back={{ label: 'All credit invoices', to: HOURS_ROUTES.creditInvoices }}
      {...(inv !== null
        ? {
            status: <CreditInvoiceStatus invoice={inv} />,
            actions: (
              <ActionButtons
                actions={[
                  {
                    key: 'pay',
                    label: 'Record payment',
                    hidden: !canPay || !open,
                    onClick: () => {
                      setPaying(true);
                    },
                  },
                  {
                    key: 'rejectCredit',
                    label: 'Reject credit',
                    destructive: true,
                    hidden: !canDecideCredit || !rejectable,
                    onClick: () => {
                      setRejecting(true);
                    },
                  },
                ]}
                primaryKey="pay"
              />
            ),
          }
        : {})}
      inactive={
        inv?.status === 'CANCELLED'
          ? inv.rejection != null
            ? {
                title: 'This invoice is cancelled: its credit was not approved.',
                since: formatInstantIn(inv.rejection.rejected_at, timeZone),
              }
            : { title: 'The order of this invoice was cancelled.', since: null }
          : null
      }
    >
      <HoursOffNotice off={hours.status === 'known' && !hours.on} />
      <AsyncContent resource={res} errorTitle="Could not load the credit invoice">
        {(d) => (
          <Stack spacing={3}>
            {d.rejection != null && (
              <CreditRejectionNotice rejection={d.rejection} timeZone={timeZone} />
            )}
            <Section title="Invoice">
              <KeyValueGrid
                columns={3}
                items={[
                  {
                    label: 'Customer',
                    value: linkTo(
                      customerDetailPath(d.customer_id),
                      nameOr(d.customer_name, d.customer_id),
                      canOpenCustomer,
                    ),
                  },
                  {
                    label: 'Order',
                    value: linkTo(
                      hoursPurchasePath(d.purchase_id),
                      d.purchase_number ?? 'Open the order',
                      true,
                    ),
                  },
                  {
                    label: 'Machine',
                    value: machineText(d.machine_code, d.machine_name, d.machine_id),
                  },
                  { label: 'Hours on credit', value: hoursText(d.hours) },
                  { label: 'Price per hour', value: money(d.unit_price, d.currency) },
                  { label: 'Issued', value: formatInstantIn(d.issued_at, timeZone) },
                  { label: 'Payment terms', value: `${d.payment_terms_days} days` },
                  { label: 'Due', value: d.due_date },
                  {
                    label: 'Overdue',
                    value: d.overdue ? `Yes, ${d.days_overdue} days` : 'No',
                  },
                  {
                    label: 'Created by',
                    value: <PersonName userId={d.created_by} name={d.created_by_name ?? null} />,
                  },
                ]}
              />
            </Section>
            <Section title="Money">
              <KeyValueGrid
                columns={4}
                items={[
                  { label: 'Amount', value: <MoneyText amount={d.amount} currency={d.currency} /> },
                  { label: 'Paid', value: <MoneyText amount={d.paid} currency={d.currency} /> },
                  {
                    label: 'Of which verified',
                    value: <MoneyText amount={d.paid_verified} currency={d.currency} />,
                  },
                  {
                    label: 'Balance',
                    value: <MoneyText amount={d.balance} currency={d.currency} strong />,
                  },
                ]}
              />
              <Typography variant="body2" color="text.secondary">
                Recorded payments count until they are rejected or reversed; verified money
                activates the order&apos;s hours.
              </Typography>
            </Section>
            <Section title="Payments">
              {d.payments.length === 0 ? (
                <Typography variant="body2" color="text.secondary">
                  No payment recorded yet.
                </Typography>
              ) : (
                <StaticTable
                  ariaLabel="Payments"
                  columns={paymentColumns(d, timeZone, canOpenPayments)}
                  rows={d.payments}
                  getRowId={(p) => p.id}
                />
              )}
            </Section>
          </Stack>
        )}
      </AsyncContent>
      {rejecting && inv !== null && (
        <RejectCreditDialog
          purchaseId={inv.purchase_id}
          purchaseNumber={inv.purchase_number ?? inv.invoice_number}
          customerName={nameOr(inv.customer_name, inv.customer_id)}
          amount={money(inv.amount, inv.currency)}
          onClose={() => {
            setRejecting(false);
          }}
          onDone={() => {
            notify.success(
              'Credit rejected; this invoice is cancelled and the seller is told why.',
            );
            setRejecting(false);
            setReloadKey((k) => k + 1);
          }}
        />
      )}
      {paying && inv !== null && (
        <RecordInvoicePaymentDialog
          invoice={inv}
          timeZone={timeZone}
          fieldNoncashPayments={hours.policy?.fieldNoncashPayments ?? false}
          onClose={() => {
            setPaying(false);
          }}
          onRecorded={(updated) => {
            notify.success(
              updated.status === 'PAID'
                ? `Payment recorded; ${updated.invoice_number} is paid in full.`
                : `Payment recorded; ${money(updated.balance, updated.currency)} left to pay.`,
            );
            setReloadKey((k) => k + 1);
          }}
        />
      )}
    </EntityDetailsLayout>
  );
}
