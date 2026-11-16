import { Link } from '@mui/material';
import { Link as RouterLink } from 'react-router';
import type { DataColumn } from '../../../components/data/ServerDataTable';
import { StaticTable } from '../../../components/data/StaticTable';
import { MoneyText } from '../../../components/display/MoneyText';
import { hoursPurchasePath } from '../../../navigation/hoursRoutes';
import type { MoneySourceRow } from './revenueDetail';
import { MONEY_SOURCE_LABELS } from './revenueDisplay';

/** The prepaid-hours purchase a money source came from (older invoice lines have no page). */
function moneySourceRecord(m: Pick<MoneySourceRow, 'source' | 'parent_id'>) {
  return m.source === 'INVOICE_LINE' ? (
    '—'
  ) : (
    <Link component={RouterLink} to={hoursPurchasePath(m.parent_id)}>
      Open purchase
    </Link>
  );
}

const columns: DataColumn<MoneySourceRow>[] = [
  { id: 'source', header: 'Source', render: (m) => MONEY_SOURCE_LABELS[m.source] },
  { id: 'hours', header: 'Hours', align: 'right', render: (m) => m.hours ?? '—' },
  {
    id: 'amount',
    header: 'Amount',
    align: 'right',
    render: (m) => <MoneyText amount={m.amount} currency={m.currency} />,
  },
  { id: 'record', header: 'Record', render: moneySourceRecord },
];

/** Prepaid hours used (and older invoice lines) that count as money for the machine's work. */
export function MoneySourcesTable({ rows }: { rows: readonly MoneySourceRow[] }) {
  return (
    <StaticTable
      ariaLabel="Money sources"
      columns={columns}
      rows={[...rows]}
      getRowId={(m) => `${m.source}:${m.ref_id}`}
    />
  );
}
