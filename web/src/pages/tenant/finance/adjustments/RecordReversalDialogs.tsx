import { Alert, Box } from '@mui/material';
import type { AdjustmentRequestDto } from '../../../../api/adjustmentTypes';
import { adjustmentService } from '../../../../api/services/adjustmentService';
import type { CustomerPaymentDto } from '../../../../api/types';
import { KeyValueGrid } from '../../../../components/display/KeyValueGrid';
import { MoneyText } from '../../../../components/display/MoneyText';
import { PAYMENT_METHOD_LABELS } from '../../shared/financeDisplay';
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
            as your company policy says. Someone else decides.
          </Alert>
        </Box>
      }
      forecast={() => ({ request_type: reversalTypeOf(p.method), payment_id: p.id })}
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
