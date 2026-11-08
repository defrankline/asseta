import { Alert, Box, Typography } from '@mui/material';
import type { AdjustmentRequestDto } from '../../../../api/adjustmentTypes';
import { adjustmentService } from '../../../../api/services/adjustmentService';
import { hireInvoiceService } from '../../../../api/services/financeService';
import type { CustomerPaymentDto, HireInvoiceDto } from '../../../../api/types';
import { KeyValueGrid } from '../../../../components/display/KeyValueGrid';
import { MoneyText } from '../../../../components/display/MoneyText';
import { PAYMENT_METHOD_LABELS } from '../../shared/financeDisplay';
import { VoidExplanation } from '../invoices/InvoiceViews';
import { invoiceTitle } from '../invoices/invoiceData';
import { AdjustmentProposalDialog } from './AdjustmentProposalDialog';
import { reversalTypeOf } from './adjustmentDisplay';

/** Propose reversing a verified payment or collection (bounced, returned); the forecast follows. */
export function ReversePaymentDialog({
  payment: p,
  onClose,
  onDone,
}: {
  payment: CustomerPaymentDto;
  onClose: () => void;
  onDone: (r: AdjustmentRequestDto) => void;
}) {
  return (
    <AdjustmentProposalDialog
      title={p.method === 'CASH' ? 'Reverse collection' : 'Reverse payment'}
      submitLabel="Propose reversal"
      reasonKind="REVERSAL"
      initial={{}}
      summary={
        <Box className="flex flex-col gap-2">
          <KeyValueGrid
            columns={2}
            items={[
              {
                label: 'Amount',
                value: <MoneyText amount={p.amount} currency={p.currency} strong />,
              },
              { label: 'Method', value: PAYMENT_METHOD_LABELS[p.method] },
              { label: 'Reference', value: p.reference ?? '—' },
            ]}
          />
          <Alert severity="warning">
            Hours this money paid for come off (unused first); hours already used become money owed
            as your company policy says. The next page shows the forecast of hours deactivated and
            money owed. Someone else decides.
          </Alert>
        </Box>
      }
      submit={(common, _v, key) =>
        adjustmentService.propose(
          { ...common, request_type: reversalTypeOf(p.method), payment_id: p.id },
          key,
        )
      }
      onDone={onDone}
      onClose={onClose}
    />
  );
}

/** Void an issued invoice: applied at once or proposed, as the tenant's policy says. */
export function VoidIssuedInvoiceDialog({
  invoice,
  onClose,
  onDone,
}: {
  invoice: HireInvoiceDto;
  onClose: () => void;
  onDone: (result: HireInvoiceDto) => void;
}) {
  return (
    <AdjustmentProposalDialog
      title={`Void ${invoiceTitle(invoice)}`}
      submitLabel="Void invoice"
      reasonKind="REVERSAL"
      evidenceOptional
      initial={{}}
      summary={
        <Box className="flex flex-col gap-2">
          <VoidExplanation invoice={invoice} />
          <Typography variant="body2" color="text.secondary">
            If your company policy needs a second person, this becomes a request and the invoice
            stays issued until someone else decides.
          </Typography>
          <Alert severity="warning">This cannot be undone.</Alert>
        </Box>
      }
      submit={(common, _v, key) => hireInvoiceService.void(invoice.id, common, key)}
      onDone={onDone}
      onClose={onClose}
    />
  );
}
