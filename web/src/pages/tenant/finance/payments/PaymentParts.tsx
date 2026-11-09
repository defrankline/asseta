import { Chip, Typography } from '@mui/material';
import type { CustomerPaymentDto } from '../../../../api/types';
import { StaticTable } from '../../../../components/data/StaticTable';
import { MoneyText } from '../../../../components/display/MoneyText';
import { shortId } from '../../shared/financeDisplay';

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
