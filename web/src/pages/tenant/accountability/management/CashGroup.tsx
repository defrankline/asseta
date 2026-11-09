import { Link } from '@mui/material';
import { Link as RouterLink } from 'react-router';
import type { CashSectionDto } from '../../../../api/custodyTypes';
import { StaticTable } from '../../../../components/data/StaticTable';
import { MoneyText } from '../../../../components/display/MoneyText';
import { nameOr } from '../../shared/names';
import { FigureGrid, FigureGroup, MoneyCard } from './figures';
import { moneyRows } from './moneyRows';
import { KpiCard } from '../../dashboard/KpiCard';

/** Guideline section 8, "Cash Accountability". Claimed money and confirmed money stay apart. */
export function CashGroup({ section: s }: { section: CashSectionDto }) {
  const money = (r: (typeof s.held_by_employee)[number], key: 'outstanding' | 'in_transit_out') => (
    <MoneyText amount={r[key]} currency={r.currency} />
  );
  return (
    <FigureGroup id="cash-accountability" title="Cash accountability">
      <FigureGrid>
        <MoneyCard title="Total cash collected" figure={s.collected} />
        <MoneyCard title="Transferred between employees" figure={s.transferred} />
        <MoneyCard title="In transit, not yet acknowledged" figure={s.in_transit} />
        <MoneyCard title="Declared for remittance" figure={s.declared_for_remittance} />
        <MoneyCard title="Confirmed received by the company" figure={s.confirmed_by_company} />
        <MoneyCard title="Outstanding cash balances" figure={s.outstanding} />
        <MoneyCard title="Unconfirmed remittances" figure={s.unconfirmed_remittances} />
        <KpiCard
          title="Disputed"
          value={s.disputed_remittances.count + s.disputed_transfers.count}
          valueText={String(s.disputed_remittances.count + s.disputed_transfers.count)}
          rows={[
            {
              key: 'remittances',
              label: 'Remittances',
              value: s.disputed_remittances.count,
              valueText: String(s.disputed_remittances.count),
              to: s.disputed_remittances.route,
            },
            ...moneyRows('remittance-amount', s.disputed_remittances),
            {
              key: 'transfers',
              label: 'Transfers',
              value: s.disputed_transfers.count,
              valueText: String(s.disputed_transfers.count),
              to: s.disputed_transfers.route,
            },
            ...moneyRows('transfer-amount', s.disputed_transfers),
          ]}
        />
      </FigureGrid>
      <StaticTable
        ariaLabel="Cash balance held by each employee"
        rows={s.held_by_employee}
        getRowId={(r) => `${r.staff_member_id}-${r.currency}`}
        columns={[
          {
            id: 'who',
            header: 'Cash balance held by each employee',
            render: (r) => (
              <Link component={RouterLink} to={r.route}>
                {nameOr(r.staff_member_name, r.staff_member_id)}
              </Link>
            ),
          },
          {
            id: 'held',
            header: 'Held',
            align: 'right',
            render: (r) => <strong>{money(r, 'outstanding')}</strong>,
          },
          {
            id: 'transit',
            header: 'In transit out',
            align: 'right',
            render: (r) => money(r, 'in_transit_out'),
          },
          {
            id: 'claimed',
            header: 'Declared, unconfirmed',
            align: 'right',
            render: (r) => (
              <MoneyText amount={r.claimed_unverified_handovers} currency={r.currency} />
            ),
          },
          {
            id: 'floats',
            header: 'Pending floats',
            align: 'right',
            render: (r) => <MoneyText amount={r.pending_floats} currency={r.currency} />,
          },
          {
            id: 'retained',
            header: 'Approved retention',
            align: 'right',
            render: (r) => <MoneyText amount={r.approved_retention} currency={r.currency} />,
          },
        ]}
      />
    </FigureGroup>
  );
}
