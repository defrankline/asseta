import { Alert, Chip, Link, Typography } from '@mui/material';
import { Link as RouterLink } from 'react-router';
import { recordPath } from '../../../../navigation/recordRoutes';
import type { CustomerPaymentDto } from '../../../../api/types';
import { StaticTable } from '../../../../components/data/StaticTable';
import { MoneyText } from '../../../../components/display/MoneyText';
import { shortId } from '../../shared/financeDisplay';
import { VERIFIES_ON_HANDOVER_TEXT, waitsForHandover } from './paymentVerification';
import { SOD_RECORDER_NOTE } from './usePaymentActions';

/** "Verified by handover RMT-…" (linked), "Cash accepted on recording …", or the wait for the handover. */
export function VerificationText({ payment: p }: { payment: CustomerPaymentDto }) {
  if (p.verified_automatically === 'ON_HANDOVER') {
    const number = p.verified_by_remittance_number ?? null;
    if (p.verified_by_handover_id == null || number === null) {
      return <>{['Verified by handover', number].filter((x) => x !== null).join(' ')}</>;
    }
    return (
      <>
        Verified by handover{' '}
        <Link component={RouterLink} to={recordPath('CASH_REMITTANCE', p.verified_by_handover_id)}>
          {number}
        </Link>
      </>
    );
  }
  if (p.verified_automatically === 'ON_RECORDING') {
    return <>{p.decision_note ?? 'Cash accepted on recording'}</>;
  }
  if (waitsForHandover(p)) return <>{VERIFIES_ON_HANDOVER_TEXT}</>;
  return null;
}

/**
 * Who verifies a claimed payment: the handover (cash_activation ON_HANDOVER) or someone other than
 * the recorder (segregation of duties).
 */
export function PaymentVerifyNotice({
  payment: p,
  mine,
}: {
  payment: CustomerPaymentDto;
  mine: boolean;
}) {
  if (waitsForHandover(p)) return <Alert severity="info">{VERIFIES_ON_HANDOVER_TEXT}.</Alert>;
  if (mine && p.status === 'CLAIMED') return <Alert severity="info">{SOD_RECORDER_NOTE}</Alert>;
  return null;
}

/** A reversed payment keeps its VERIFIED status; this says the money was taken back. */
export function ReversedChip({ payment: p }: { payment: CustomerPaymentDto }) {
  return p.reversed_at == null ? null : (
    <Chip size="small" color="warning" variant="outlined" label="Reversed" />
  );
}

/** Which invoices a payment is allocated to; released allocations stay visible. */
export function PaymentAllocations({ payment: p }: { payment: CustomerPaymentDto }) {
  return (
    <>
      <Typography variant="subtitle2">Allocations</Typography>
      <StaticTable
        ariaLabel="Allocations"
        rows={p.allocations}
        getRowId={(a) => a.id}
        isRowMuted={(a) => a.released_at !== null}
        columns={[
          { id: 'inv', header: 'Invoice', render: (a) => shortId(a.invoice_id) },
          {
            id: 'amt',
            header: 'Amount',
            align: 'right',
            render: (a) => <MoneyText amount={a.amount} currency={p.currency} />,
          },
          {
            id: 'rel',
            header: 'Released',
            render: (a) => (a.released_at === null ? 'Active' : (a.release_reason ?? 'Released')),
          },
        ]}
      />
    </>
  );
}
