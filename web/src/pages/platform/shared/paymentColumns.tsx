import type { PaymentDto } from '../../../api/types';
import type { DataColumn } from '../../../components/data/ServerDataTable';
import { MoneyText } from '../../../components/display/MoneyText';
import { StatusChip } from '../../../components/display/StatusChip';
import { formatDate, formatInstant } from '../../../utils/dates';
import { optionLabel, PAYMENT_METHOD_OPTIONS, PAYMENT_TONES } from './billingDisplay';

/** Columns shared by the payments page and the invoice detail payments list. */
export const PAYMENT_COLUMNS: DataColumn<PaymentDto>[] = [
  { id: 'received_on', header: 'Received on', render: (p) => formatDate(p.received_on) },
  { id: 'reference', header: 'Reference', render: (p) => p.reference },
  { id: 'method', header: 'Method', render: (p) => optionLabel(PAYMENT_METHOD_OPTIONS, p.method) },
  {
    id: 'amount',
    header: 'Amount',
    align: 'right',
    render: (p) => <MoneyText amount={p.amount} currency={p.currency} />,
  },
  {
    id: 'status',
    header: 'Status',
    render: (p) => <StatusChip status={p.status} tones={PAYMENT_TONES} />,
  },
  { id: 'recorded_at', header: 'Recorded', render: (p) => formatInstant(p.recorded_at) },
];
