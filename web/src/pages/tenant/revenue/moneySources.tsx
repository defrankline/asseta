import { Link } from '@mui/material';
import { Link as RouterLink } from 'react-router';
import type { SheetMoneySourceDto } from '../../../api/types';
import type { DataColumn } from '../../../components/data/ServerDataTable';
import { StaticTable } from '../../../components/data/StaticTable';
import { MoneyText } from '../../../components/display/MoneyText';
import { hoursPurchasePath } from '../../../navigation/hoursRoutes';
import { jobDetailPath } from '../../../navigation/routes';
import { MONEY_SOURCE_LABELS } from './revenueDisplay';

/** The prepaid-hours purchase a money source came from (older invoice lines have no page). */
function moneySourceRecord(m: Pick<SheetMoneySourceDto, 'source' | 'parent_id'>) {
  return m.source === 'INVOICE_LINE' ? (
    '—'
  ) : (
    <Link component={RouterLink} to={hoursPurchasePath(m.parent_id)}>
      Open purchase
    </Link>
  );
}

const columns: DataColumn<SheetMoneySourceDto>[] = [
  { id: 'source', header: 'Source', render: (m) => MONEY_SOURCE_LABELS[m.source] },
  {
    id: 'job',
    header: 'Job',
    render: (m) => (
      <Link component={RouterLink} to={jobDetailPath(m.job_id)}>
        {m.job_number ?? 'Open job'}
      </Link>
    ),
  },
  { id: 'hours', header: 'Hours', align: 'right', render: (m) => m.hours ?? '—' },
  {
    id: 'amount',
    header: 'Amount',
    align: 'right',
    render: (m) => <MoneyText amount={m.amount} currency={m.currency} />,
  },
  { id: 'record', header: 'Record', render: moneySourceRecord },
];

/** Invoice lines and prepaid hours used that count as money for the machine's work. */
export function MoneySourcesTable({ rows }: { rows: readonly SheetMoneySourceDto[] }) {
  return (
    <StaticTable
      ariaLabel="Money sources"
      columns={columns}
      rows={[...rows]}
      getRowId={(m) => `${m.source}:${m.ref_id}`}
    />
  );
}
