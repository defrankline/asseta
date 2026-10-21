import {
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  Stack,
  Typography,
} from '@mui/material';
import { useCallback, useState } from 'react';
import { Can } from '../../../access/Can';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { platformInvoiceService } from '../../../api/services/platformInvoiceService';
import { platformPaymentService } from '../../../api/services/platformPaymentService';
import type { InvoiceDto } from '../../../api/types';
import { StaticTable } from '../../../components/data/StaticTable';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { useNotify } from '../../../notifications/useNotify';
import { isZeroDecimal } from '../../../utils/money';
import { PAYMENT_COLUMNS } from '../shared/paymentColumns';
import { ApplyCreditDialog } from './ApplyCreditDialog';
import { InvoiceSummary } from './InvoiceSummary';
import { RecordPaymentDialog } from './RecordPaymentDialog';

interface InvoiceDetailDialogProps {
  invoiceId: string;
  onClose: () => void;
  /** Called after a payment or credit changed the invoice. */
  onChanged?: () => void;
}

type Action = 'payment' | 'credit' | null;

function InvoicePayments({ invoiceId, reloadKey }: { invoiceId: string; reloadKey: number }) {
  const load = useCallback(
    (signal: AbortSignal) =>
      platformPaymentService.list({ page: 1, page_size: 100, invoice_id: invoiceId }, signal),
    [invoiceId],
  );
  const payments = useAsyncResource(load, [reloadKey]);
  return (
    <AsyncContent
      resource={payments}
      isEmpty={(p) => p.items.length === 0}
      emptyTitle="No payments recorded for this invoice"
      errorTitle="Could not load payments"
    >
      {(p) => (
        <StaticTable
          ariaLabel="Invoice payments"
          columns={PAYMENT_COLUMNS}
          rows={p.items}
          getRowId={(x) => x.id}
        />
      )}
    </AsyncContent>
  );
}

/** Issued invoice with immutable lines, totals and payments; record payment / apply credit. */
export function InvoiceDetailDialog({ invoiceId, onClose, onChanged }: InvoiceDetailDialogProps) {
  const notify = useNotify();
  const [action, setAction] = useState<Action>(null);
  const [version, setVersion] = useState(0);
  const load = useCallback(
    (signal: AbortSignal) => platformInvoiceService.get(invoiceId, signal),
    [invoiceId],
  );
  const invoice = useAsyncResource(load, [version]);
  const changed = (message: string) => {
    notify.success(message);
    setVersion((v) => v + 1);
    onChanged?.();
  };
  const current = invoice.data;
  const open = current !== null && current.id !== null && !isZeroDecimal(current.balance);
  const withId = current !== null && current.id !== null ? { ...current, id: current.id } : null;

  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="lg" aria-labelledby="invoice-detail-title">
      <DialogTitle id="invoice-detail-title">Invoice {current?.invoice_number ?? ''}</DialogTitle>
      <DialogContent dividers>
        <AsyncContent
          resource={invoice}
          errorTitle="Could not load invoice"
          loadingLabel="Loading invoice"
        >
          {(inv: InvoiceDto) => (
            <Stack spacing={2}>
              <InvoiceSummary invoice={inv} />
              <Divider />
              <Typography variant="subtitle2">Payments</Typography>
              <Can
                permission={PERMISSIONS.platformPaymentRead}
                fallback={
                  <Typography variant="body2" color="text.secondary">
                    You cannot view payments.
                  </Typography>
                }
              >
                <InvoicePayments invoiceId={invoiceId} reloadKey={version} />
              </Can>
            </Stack>
          )}
        </AsyncContent>
      </DialogContent>
      <DialogActions>
        <Can permission={PERMISSIONS.platformCreditManage}>
          <Button
            disabled={!open}
            onClick={() => {
              setAction('credit');
            }}
          >
            Apply credit
          </Button>
        </Can>
        <Can permission={PERMISSIONS.platformPaymentManage}>
          <Button
            variant="contained"
            disabled={!open}
            onClick={() => {
              setAction('payment');
            }}
          >
            Record payment
          </Button>
        </Can>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
      {action === 'payment' && withId !== null && (
        <RecordPaymentDialog
          invoice={withId}
          onClose={() => {
            setAction(null);
          }}
          onRecorded={() => {
            changed('Payment recorded; verify it to reduce the balance.');
          }}
        />
      )}
      {action === 'credit' && withId !== null && (
        <ApplyCreditDialog
          invoice={withId}
          onClose={() => {
            setAction(null);
          }}
          onApplied={() => {
            changed('Credit applied.');
          }}
        />
      )}
    </Dialog>
  );
}
