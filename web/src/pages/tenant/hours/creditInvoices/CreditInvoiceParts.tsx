import { Alert, AlertTitle, Chip, Link, Stack } from '@mui/material';
import type { ReactNode } from 'react';
import { Link as RouterLink } from 'react-router';
import type { CreditInvoiceSummaryDto, CreditRejectionDto } from '../../../../api/hoursTypes';
import { KeyValueGrid } from '../../../../components/display/KeyValueGrid';
import { MoneyText } from '../../../../components/display/MoneyText';
import { StatusChip } from '../../../../components/display/StatusChip';
import { creditInvoicePath } from '../../../../navigation/hoursRoutes';
import { formatInstantIn } from '../../../../utils/time';
import { PersonName } from '../../shared/PersonName';
import { money } from '../hoursQuote';
import { CREDIT_INVOICE_STATUS_LABELS, CREDIT_INVOICE_STATUS_TONES } from './creditInvoiceDisplay';

/** Status chip plus an "Overdue" chip (text, never colour alone). */
export function CreditInvoiceStatus({
  invoice,
}: {
  invoice: Pick<CreditInvoiceSummaryDto, 'status' | 'overdue'> & { days_overdue?: number };
}) {
  return (
    <Stack direction="row" spacing={0.5} sx={{ flexWrap: 'wrap' }}>
      <StatusChip
        status={invoice.status}
        tones={CREDIT_INVOICE_STATUS_TONES}
        label={CREDIT_INVOICE_STATUS_LABELS[invoice.status]}
      />
      {invoice.overdue && (
        <Chip
          size="small"
          color="error"
          variant="outlined"
          label={
            invoice.days_overdue !== undefined && invoice.days_overdue > 0
              ? `Overdue ${invoice.days_overdue} d`
              : 'Overdue'
          }
        />
      )}
    </Stack>
  );
}

/** Shown after a sale with a credit line: the invoice the server created for the credit part. */
export function CreditInvoiceCreatedNotice({
  purchaseNumber,
  invoice,
  currency,
  linked,
  onClose,
}: {
  purchaseNumber: string;
  invoice: CreditInvoiceSummaryDto;
  currency: string;
  linked: boolean;
  onClose: () => void;
}) {
  return (
    <Alert severity="info" onClose={onClose}>
      <AlertTitle>
        Credit invoice <CreditInvoiceLink invoice={invoice} linked={linked} /> created
      </AlertTitle>
      Order {purchaseNumber}: {money(invoice.amount, currency)} on credit, due {invoice.due_date}.
      The customer can pay it in full or in parts; its hours wait for credit approval.
    </Alert>
  );
}

/** The invoice number linking to its page (plain text when the user may not open it). */
export function CreditInvoiceLink({
  invoice,
  linked = true,
}: {
  invoice: Pick<CreditInvoiceSummaryDto, 'id' | 'invoice_number'>;
  linked?: boolean;
}) {
  if (!linked) return <>{invoice.invoice_number}</>;
  return (
    <Link component={RouterLink} to={creditInvoicePath(invoice.id)}>
      {invoice.invoice_number}
    </Link>
  );
}

/** The credit was not approved: who, when and why (the invoice is cancelled). */
export function CreditRejectionNotice({
  rejection,
  timeZone,
}: {
  rejection: CreditRejectionDto;
  timeZone: string;
}) {
  return (
    <Alert severity="warning">
      <AlertTitle>Credit not approved</AlertTitle>
      Rejected by{' '}
      <PersonName
        userId={rejection.rejected_by}
        name={rejection.rejected_by_name ?? null}
      /> on {formatInstantIn(rejection.rejected_at, timeZone)}: {rejection.reason}. The invoice is
      cancelled and these credit hours will not be activated.
    </Alert>
  );
}

/** The order's credit invoice: number, status, due date, amount, paid and balance. */
export function CreditInvoiceSummaryGrid({
  invoice,
  currency,
}: {
  invoice: CreditInvoiceSummaryDto;
  currency: string;
}) {
  const amount = (v: string, strong = false): ReactNode => (
    <MoneyText amount={v} currency={currency} strong={strong} />
  );
  return (
    <KeyValueGrid
      columns={3}
      items={[
        { label: 'Invoice', value: <CreditInvoiceLink invoice={invoice} /> },
        { label: 'Status', value: <CreditInvoiceStatus invoice={invoice} /> },
        { label: 'Due', value: invoice.due_date },
        { label: 'Amount', value: amount(invoice.amount) },
        { label: 'Paid', value: amount(invoice.paid) },
        { label: 'Balance', value: amount(invoice.balance, true) },
      ]}
    />
  );
}
