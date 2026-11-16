import { Link } from '@mui/material';
import { useCallback } from 'react';
import { Link as RouterLink } from 'react-router';
import type { CustomerHoursSummaryDto } from '../../../../api/hoursTypes';
import { creditInvoiceService } from '../../../../api/services/creditInvoiceService';
import { StaticTable } from '../../../../components/data/StaticTable';
import { AsyncContent } from '../../../../components/feedback/AsyncContent';
import { useAsyncResource } from '../../../../hooks/useAsyncResource';
import { creditInvoicesPath } from '../../../../navigation/hoursRoutes';
import { isZeroDecimal } from '../../../../utils/money';
import { nameOr } from '../../shared/names';
import { hoursText } from '../hoursDisplay';
import { groupedAmount } from './creditInvoiceDisplay';

/** Every customer's hours: bought / activated / used / left, awaiting activation, credit owed. */
export function CustomerHoursTable({
  onOpenCustomer,
}: {
  onOpenCustomer: (customerId: string, name: string) => void;
}) {
  const load = useCallback(
    (signal: AbortSignal) => creditInvoiceService.customerHours(undefined, signal),
    [],
  );
  const res = useAsyncResource(load);
  return (
    <AsyncContent
      resource={res}
      isEmpty={(rows) => rows.length === 0}
      emptyTitle="No customer has bought hours yet"
      errorTitle="Could not load the customers’ hours"
    >
      {(rows) => (
        <StaticTable<CustomerHoursSummaryDto>
          ariaLabel="Customer hours"
          rows={rows}
          getRowId={(r) => r.customer_id}
          columns={[
            {
              id: 'customer',
              header: 'Customer',
              render: (r) => (
                <Link
                  component="button"
                  type="button"
                  onClick={() => {
                    onOpenCustomer(r.customer_id, nameOr(r.customer_name, r.customer_id));
                  }}
                >
                  {nameOr(r.customer_name, r.customer_id)}
                </Link>
              ),
            },
            { id: 'bought', header: 'Bought', align: 'right', render: (r) => hoursText(r.bought) },
            {
              id: 'activated',
              header: 'Usable (activated)',
              align: 'right',
              render: (r) => hoursText(r.activated),
            },
            { id: 'used', header: 'Used', align: 'right', render: (r) => hoursText(r.used) },
            {
              id: 'left',
              header: 'Left',
              align: 'right',
              render: (r) => <strong>{hoursText(r.left)}</strong>,
            },
            {
              id: 'awaiting',
              header: 'Awaiting activation',
              align: 'right',
              render: (r) => hoursText(r.awaiting_activation),
            },
            {
              id: 'credit',
              header: 'Credit owed',
              align: 'right',
              render: (r) =>
                isZeroDecimal(r.credit_owed) ? (
                  '—'
                ) : (
                  <Link
                    component={RouterLink}
                    to={creditInvoicesPath({ customer_id: r.customer_id })}
                  >
                    {groupedAmount(r.credit_owed)}
                  </Link>
                ),
            },
          ]}
        />
      )}
    </AsyncContent>
  );
}
