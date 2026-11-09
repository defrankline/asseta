import { Link } from '@mui/material';
import { Link as RouterLink } from 'react-router';
import type { CustomerHoursSectionDto } from '../../../../api/custodyTypes';
import { StaticTable } from '../../../../components/data/StaticTable';
import { hoursText } from '../../hours/hoursDisplay';
import { nameOr } from '../../shared/names';
import { FigureGrid, FigureGroup, HoursCard, PurchaseQueueCard } from './figures';
import { moneyRows } from './moneyRows';
import { KpiCard } from '../../dashboard/KpiCard';

/** Guideline section 8, "Customer Hours". */
export function CustomerHoursGroup({ section: s }: { section: CustomerHoursSectionDto }) {
  const shown = s.remaining_by_customer.length;
  return (
    <FigureGroup id="customer-hours" title="Customer hours">
      <FigureGrid>
        <KpiCard
          title="Total hours purchased"
          value={hoursText(s.purchased.hours)}
          valueText={hoursText(s.purchased.hours)}
          to={s.purchased.route}
          description={`${String(s.purchased.count)} purchases`}
          rows={moneyRows('value', s.purchased_value, 'Value')}
        />
        <HoursCard title="Total activated hours" figure={s.activated} />
        <HoursCard title="Total hours consumed" figure={s.consumed} />
        <HoursCard title="Hours remaining" figure={s.remaining} />
        <PurchaseQueueCard title="Unpaid purchases" queue={s.unpaid_purchases} />
        <PurchaseQueueCard title="Unconfirmed purchases" queue={s.unconfirmed_purchases} />
        <PurchaseQueueCard title="Hours awaiting activation" queue={s.awaiting_activation} />
      </FigureGrid>
      <StaticTable
        ariaLabel="Remaining hours by customer"
        rows={s.remaining_by_customer}
        getRowId={(r) => r.customer_id}
        columns={[
          {
            id: 'customer',
            header: 'Remaining hours by customer',
            render: (r) => (
              <Link component={RouterLink} to={r.route}>
                {nameOr(r.customer_name, r.customer_id)}
              </Link>
            ),
          },
          { id: 'act', header: 'Activated', align: 'right', render: (r) => hoursText(r.activated) },
          { id: 'used', header: 'Consumed', align: 'right', render: (r) => hoursText(r.consumed) },
          {
            id: 'left',
            header: 'Remaining',
            align: 'right',
            render: (r) => <strong>{hoursText(r.remaining)}</strong>,
          },
        ]}
      />
      {s.remaining_customers_total > shown && (
        <Link component={RouterLink} to={s.remaining.route}>
          {`Showing ${String(shown)} of ${String(s.remaining_customers_total)} customers. Open all balances`}
        </Link>
      )}
    </FigureGroup>
  );
}
