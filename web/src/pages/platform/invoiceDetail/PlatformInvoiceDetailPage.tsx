import { Link } from '@mui/material';
import { useCallback, useState } from 'react';
import { Link as RouterLink, useParams } from 'react-router';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { withErrorCode } from '../../../api/lifecycle';
import { usePlatformInvoicingService } from '../../../api/services/platformInvoicingService';
import type { InvoiceDto } from '../../../api/types';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { MoneyText } from '../../../components/display/MoneyText';
import { StatusChip } from '../../../components/display/StatusChip';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { ActionButtons } from '../../../components/lifecycle/ActionButtons';
import {
  DetailSection,
  EntityDetailsLayout,
} from '../../../components/lifecycle/EntityDetailsLayout';
import { LifecycleActionDialog } from '../../../components/lifecycle/LifecycleActionDialog';
import type { RowAction } from '../../../components/lifecycle/rowActions';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { ROUTES, tenantDetailPath } from '../../../navigation/routes';
import { useNotify } from '../../../notifications/useNotify';
import { ENTITY, entityKey } from '../../../realtime/entities';
import { useLiveRefresh } from '../../../realtime/hooks';
import { useSession } from '../../../session/useSession';
import { formatDate, formatInstant } from '../../../utils/dates';
import { isZeroDecimal } from '../../../utils/money';
import { ApplyCreditDialog } from '../invoices/ApplyCreditDialog';
import { RecordPaymentDialog } from '../invoices/RecordPaymentDialog';
import { INVOICE_TONES } from '../shared/billingDisplay';
import {
  INVOICE_KIND_LABELS,
  INVOICE_KIND_TONES,
  invoiceTitle,
  VOID_ERROR_HINTS,
} from './invoiceDisplay';
import { InvoiceLinesSection, PaymentAllocationsSection } from './InvoiceLinesSection';

type Action = 'void' | 'payment' | 'credit' | null;

const VOID_DESCRIPTION =
  'Voiding is a reversal, never a deletion: the invoice stays with its history and a zero balance; ' +
  'money allocated to it becomes tenant credit; fulfilled lines are reversed where possible (unused ' +
  'SMS credits are taken back, a subscription period becomes billable again) and the rest is ' +
  'flagged for review. This cannot be undone.';

/**
 * Platform invoice (subscription or ad hoc): lines with payable / paid and fulfilment, payments
 * with their line allocation, record payment, apply credit and void. Refreshes itself on pushes.
 */
export function PlatformInvoiceDetailPage() {
  const { invoiceId = '' } = useParams();
  const service = usePlatformInvoicingService();
  const notify = useNotify();
  const { hasPermission } = useSession();
  const [action, setAction] = useState<Action>(null);
  const [paymentsKey, setPaymentsKey] = useState(0);
  const load = useCallback(
    (signal: AbortSignal) => service.getInvoice(invoiceId, signal),
    [service, invoiceId],
  );
  const invoice = useAsyncResource(load);
  const reloadAll = useCallback(() => {
    invoice.reload();
    setPaymentsKey((k) => k + 1);
  }, [invoice]);
  // Payments, verification and fulfilment arrive asynchronously.
  useLiveRefresh([entityKey(ENTITY.platformInvoice, invoiceId), ENTITY.platformPayment], reloadAll);

  const close = () => {
    setAction(null);
  };
  const done = (message: string) => {
    notify.success(message);
    reloadAll();
  };

  const actionsFor = (inv: InvoiceDto): RowAction[] => {
    const open = inv.status !== 'VOIDED' && !isZeroDecimal(inv.balance);
    return [
      {
        key: 'payment',
        label: 'Record payment',
        hidden: !open || !hasPermission(PERMISSIONS.platformPaymentManage),
        onClick: () => {
          setAction('payment');
        },
      },
      {
        key: 'credit',
        label: 'Apply credit',
        hidden: !open || !hasPermission(PERMISSIONS.platformCreditManage),
        onClick: () => {
          setAction('credit');
        },
      },
      {
        key: 'void',
        label: 'Void invoice',
        destructive: true,
        hidden: inv.status === 'VOIDED' || !hasPermission(PERMISSIONS.platformInvoiceVoid),
        onClick: () => {
          setAction('void');
        },
      },
    ];
  };

  return (
    <AsyncContent
      resource={invoice}
      loadingLabel="Loading invoice"
      errorTitle="Could not load the invoice"
    >
      {(inv) => {
        const withId = { ...inv, id: inv.id ?? invoiceId };
        return (
          <EntityDetailsLayout
            title={`Invoice ${invoiceTitle(inv)}`}
            back={{ label: 'Invoices', to: ROUTES.platformInvoices }}
            status={
              <>
                <StatusChip
                  status={inv.kind}
                  tones={INVOICE_KIND_TONES}
                  label={INVOICE_KIND_LABELS[inv.kind]}
                />
                {inv.status !== null && <StatusChip status={inv.status} tones={INVOICE_TONES} />}
              </>
            }
            actions={<ActionButtons actions={actionsFor(inv)} primaryKey="payment" />}
            inactive={
              inv.status === 'VOIDED'
                ? {
                    title: 'This invoice is void.',
                    reason: inv.void_reason ?? null,
                    since: inv.voided_at == null ? null : formatInstant(inv.voided_at),
                  }
                : null
            }
          >
            <DetailSection title="Summary">
              <KeyValueGrid
                columns={3}
                items={[
                  {
                    label: 'Tenant',
                    value: (
                      <Link component={RouterLink} to={tenantDetailPath(inv.tenant_id)}>
                        View tenant
                      </Link>
                    ),
                  },
                  {
                    label: 'Issued',
                    value: inv.issued_at === null ? '—' : formatInstant(inv.issued_at),
                  },
                  { label: 'Due', value: formatDate(inv.due_date) },
                  {
                    label: 'Period',
                    value: `${formatDate(inv.period_start)} – ${formatDate(inv.period_end)}`,
                  },
                  {
                    label: 'Total',
                    value: <MoneyText amount={inv.total} currency={inv.currency} strong />,
                  },
                  {
                    label: 'Paid (verified)',
                    value: <MoneyText amount={inv.amount_paid} currency={inv.currency} />,
                  },
                  {
                    label: 'Credits applied',
                    value: <MoneyText amount={inv.credits_applied} currency={inv.currency} />,
                  },
                  {
                    label: 'Balance',
                    value: <MoneyText amount={inv.balance} currency={inv.currency} strong />,
                  },
                  { label: 'Notes', value: inv.notes ?? '—' },
                ]}
              />
            </DetailSection>
            <InvoiceLinesSection invoice={inv} />
            {hasPermission(PERMISSIONS.platformPaymentRead) && (
              <PaymentAllocationsSection invoice={withId} reloadKey={paymentsKey} />
            )}
            {action === 'void' && (
              <LifecycleActionDialog<InvoiceDto>
                title={`Void invoice ${invoiceTitle(inv)}`}
                description={VOID_DESCRIPTION}
                confirmLabel="Void invoice"
                destructive
                onConfirm={async (reason, key) => {
                  try {
                    return await service.voidInvoice(withId.id, { reason }, key);
                  } catch (err) {
                    throw withErrorCode(err, VOID_ERROR_HINTS);
                  }
                }}
                onDone={(v) => {
                  done(`Invoice ${invoiceTitle(v)} voided.`);
                }}
                onClose={close}
                onReload={reloadAll}
              />
            )}
            {action === 'payment' && (
              <RecordPaymentDialog
                invoice={withId}
                onClose={close}
                onRecorded={() => {
                  done('Payment recorded; verify it to apply it to the invoice.');
                }}
              />
            )}
            {action === 'credit' && (
              <ApplyCreditDialog
                invoice={withId}
                onClose={close}
                onApplied={() => {
                  done('Credit applied.');
                }}
              />
            )}
          </EntityDetailsLayout>
        );
      }}
    </AsyncContent>
  );
}
