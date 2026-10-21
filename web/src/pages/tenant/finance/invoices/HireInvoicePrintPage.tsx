import Print from '@mui/icons-material/Print';
import { Alert, Box, Button, Divider, Typography } from '@mui/material';
import { useCallback } from 'react';
import { Link as RouterLink, useParams } from 'react-router';
import { customerService } from '../../../../api/services/customerService';
import { hireInvoiceService } from '../../../../api/services/financeService';
import type { CustomerDto, HireInvoiceDto } from '../../../../api/types';
import { KeyValueGrid } from '../../../../components/display/KeyValueGrid';
import { AsyncContent } from '../../../../components/feedback/AsyncContent';
import { useAsyncResource } from '../../../../hooks/useAsyncResource';
import { useDisplayTimeZone } from '../../../../hooks/useDisplayTimeZone';
import { hireInvoiceDetailPath } from '../../../../navigation/routes';
import { useSession } from '../../../../session/useSession';
import { formatDate } from '../../../../utils/dates';
import { formatInstantIn } from '../../../../utils/time';
import { useMachineLabels } from '../../shared/useMachineLabels';
import { invoiceTitle, useInvoiceJobLabels } from './invoiceData';
import { InvoiceLinesTable, InvoiceTotals } from './InvoiceViews';

interface Loaded {
  invoice: HireInvoiceDto;
  customer: CustomerDto;
}

function PrintBody({ invoice: i, customer: c }: Loaded) {
  const timeZone = useDisplayTimeZone();
  const { activeTenant } = useSession();
  const machineLabel = useMachineLabels();
  const jobLabel = useInvoiceJobLabels(i.job_ids);
  return (
    <Box className="flex flex-col gap-4 print:gap-2" data-testid="invoice-print">
      <Box className="flex flex-wrap justify-between gap-4">
        <Box>
          <Typography variant="h5" component="h1" sx={{ fontWeight: 700 }}>
            {i.status === 'DRAFT' ? 'DRAFT — not an invoice' : `Invoice ${invoiceTitle(i)}`}
          </Typography>
          <Typography variant="body2">{activeTenant?.name ?? ''}</Typography>
        </Box>
        <Box className="text-right">
          <Typography variant="body2">
            Issued: {i.issued_at === null ? '—' : formatInstantIn(i.issued_at, timeZone)}
          </Typography>
          <Typography variant="body2">Due: {formatDate(i.due_date)}</Typography>
          <Typography variant="body2">Currency: {i.currency}</Typography>
        </Box>
      </Box>
      {i.status === 'VOIDED' && (
        <Alert severity="error">
          VOIDED{i.voided_at === null ? '' : ` on ${formatInstantIn(i.voided_at, timeZone)}`}:{' '}
          {i.void_reason ?? ''}. This invoice has been reversed and is not payable.
        </Alert>
      )}
      <Divider />
      <KeyValueGrid
        columns={3}
        items={[
          { label: 'Bill to', value: `${c.name} (${c.code})` },
          { label: 'Tax ID', value: c.tax_id ?? '—' },
          { label: 'Payment terms', value: `${String(c.payment_terms_days)} days` },
        ]}
      />
      <InvoiceLinesTable invoice={i} jobLabel={jobLabel} machineLabel={machineLabel} />
      <InvoiceTotals invoice={i} />
      {i.notes !== null && <Typography variant="body2">Notes: {i.notes}</Typography>}
    </Box>
  );
}

/** Print-friendly invoice (browser print); navigation chrome is hidden with print styles. */
export function HireInvoicePrintPage() {
  const { invoiceId = '' } = useParams();
  const load = useCallback(
    async (signal: AbortSignal): Promise<Loaded> => {
      const invoice = await hireInvoiceService.get(invoiceId, signal);
      const customer = await customerService.get(invoice.customer_id, signal);
      return { invoice, customer };
    },
    [invoiceId],
  );
  const res = useAsyncResource(load);
  return (
    <Box className="flex flex-col gap-3">
      <Box className="flex gap-2 print:hidden">
        <Button component={RouterLink} to={hireInvoiceDetailPath(invoiceId)} size="small">
          Back to invoice
        </Button>
        <Button
          size="small"
          variant="contained"
          startIcon={<Print />}
          onClick={() => {
            window.print();
          }}
        >
          Print
        </Button>
      </Box>
      <AsyncContent resource={res} errorTitle="Could not load the invoice">
        {(d) => <PrintBody invoice={d.invoice} customer={d.customer} />}
      </AsyncContent>
    </Box>
  );
}
