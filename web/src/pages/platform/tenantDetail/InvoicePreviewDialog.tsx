import { Button, Dialog, DialogActions, DialogContent, DialogTitle, Stack } from '@mui/material';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import dayjs from 'dayjs';
import { useCallback, useState } from 'react';
import { subscriptionService } from '../../../api/services/subscriptionService';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { EmptyState } from '../../../components/feedback/EmptyState';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { todayIsoDate } from '../../../utils/dates';
import { InvoiceSummary } from '../invoices/InvoiceSummary';

interface InvoicePreviewDialogProps {
  subscriptionId: string;
  onClose: () => void;
}

/** Read-only preview of the next invoice as of a date (nothing is issued). */
export function InvoicePreviewDialog({ subscriptionId, onClose }: InvoicePreviewDialogProps) {
  const [asOf, setAsOf] = useState(todayIsoDate);
  const load = useCallback(
    (signal: AbortSignal) => subscriptionService.previewNextInvoice(subscriptionId, asOf, signal),
    [subscriptionId, asOf],
  );
  const preview = useAsyncResource(load);
  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="lg" aria-labelledby="invoice-preview-title">
      <DialogTitle id="invoice-preview-title">Next invoice preview</DialogTitle>
      <DialogContent dividers>
        <Stack spacing={2}>
          <DatePicker
            label="As of"
            value={dayjs(asOf)}
            format="YYYY-MM-DD"
            onChange={(d) => {
              if (d !== null && d.isValid()) setAsOf(d.format('YYYY-MM-DD'));
            }}
            slotProps={{ textField: { size: 'small', sx: { maxWidth: 220 } } }}
          />
          <AsyncContent
            resource={preview}
            errorTitle="Could not preview the invoice"
            loadingLabel="Computing preview"
          >
            {(inv) =>
              inv === null ? (
                <EmptyState
                  title="Nothing due"
                  description="No invoice would be issued as of this date."
                />
              ) : (
                <InvoiceSummary invoice={inv} />
              )
            }
          </AsyncContent>
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
}
