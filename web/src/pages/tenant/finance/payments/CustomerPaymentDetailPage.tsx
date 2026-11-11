import { Alert, Box, Link } from '@mui/material';
import { useCallback } from 'react';
import { Link as RouterLink, useParams } from 'react-router';
import type { CustomerPaymentDto } from '../../../../api/types';
import { customerPaymentService } from '../../../../api/services/financeService';
import { StatusChip } from '../../../../components/display/StatusChip';
import { useDisplayTimeZone } from '../../../../hooks/useDisplayTimeZone';
import { adjustmentRequestPath } from '../../../../navigation/adjustmentRoutes';
import { ROUTES } from '../../../../navigation/routes';
import { SETTLEMENT_LABELS, SETTLEMENT_TONES, shortId } from '../../shared/financeDisplay';
import { PersonName } from '../../shared/PersonName';
import { RecordDetail } from '../../shared/RecordDetail';
import { useCustomerLabels, useStaffLabels } from '../../shared/useFinanceLabels';
import { useRecordById } from '../../shared/useRecordById';
import { PaymentAllocations, PaymentVerifyNotice, ReversedChip } from './PaymentParts';
import { paymentItems } from './paymentRecord';
import { usePaymentActions } from './usePaymentActions';

/** One customer payment or collection, by its own link. */
export function CustomerPaymentDetailPage() {
  const { paymentId } = useParams();
  const timeZone = useDisplayTimeZone();
  const customerLabel = useCustomerLabels();
  const staffLabel = useStaffLabels();
  const load = useCallback(
    (id: string, signal: AbortSignal) => customerPaymentService.get(id, signal),
    [],
  );
  const res = useRecordById<CustomerPaymentDto>(load, paymentId);
  const { actionsFor, dialogs, isMine } = usePaymentActions({
    onChanged: res.reload,
    onView: () => undefined,
  });
  return (
    <>
      <RecordDetail
        resource={res}
        what="customer payment"
        back={{ label: 'Customer payments', to: ROUTES.tenantCustomerPayments }}
        timeZone={timeZone}
        title={(p) => `Payment ${p.collection_number ?? p.reference ?? shortId(p.id)}`}
        status={(p) => (
          <Box component="span" className="inline-flex flex-wrap gap-1">
            <StatusChip
              status={p.status}
              tones={SETTLEMENT_TONES}
              label={SETTLEMENT_LABELS[p.status]}
            />
            <ReversedChip payment={p} />
          </Box>
        )}
        actions={(p) => actionsFor(p).filter((a) => a.key !== 'view')}
        primaryKey="decide"
        items={(p) => paymentItems(p, timeZone, customerLabel, staffLabel)}
        history={(p) => [
          {
            key: 'recorded',
            at: p.recorded_at,
            label: 'Recorded',
            by: <PersonName userId={p.recorded_by} name={p.recorded_by_name} />,
          },
          {
            key: 'decided',
            at: p.verified_at,
            label: p.status === 'REJECTED' ? 'Rejected' : 'Verified',
            by: (
              <PersonName
                userId={p.verified_by ?? null}
                name={p.verified_by_name}
                empty={p.verified_automatically == null ? '—' : 'Verified automatically'}
              />
            ),
            note: p.decision_note,
          },
          { key: 'reversed', at: p.reversed_at, label: 'Reversed' },
        ]}
      >
        {(p) => (
          <>
            <PaymentVerifyNotice payment={p} mine={isMine(p)} />
            {p.reversed_at != null && p.reversal_id != null && (
              <Alert severity="warning">
                This money no longer counts for the customer.{' '}
                <Link component={RouterLink} to={adjustmentRequestPath(p.reversal_id)}>
                  Open the reversal
                </Link>
              </Alert>
            )}
            <PaymentAllocations payment={p} />
          </>
        )}
      </RecordDetail>
      {dialogs}
    </>
  );
}
