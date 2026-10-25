import { Box, Paper, Stack, ToggleButton, ToggleButtonGroup, Typography } from '@mui/material';
import { useCallback, useState } from 'react';
import type { HoursBalanceDto } from '../../../api/hoursTypes';
import { hoursService } from '../../../api/services/hoursService';
import type { CustomerDto, MachineDto } from '../../../api/types';
import { StaticTable } from '../../../components/data/StaticTable';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { MoneyText } from '../../../components/display/MoneyText';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { EmptyState } from '../../../components/feedback/EmptyState';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { CustomerFilter, MachineFilter } from '../shared/financePickers';
import { machineText, nameOr } from '../shared/names';
import { hoursText } from './hoursDisplay';

type View = 'customer' | 'machine';

function BalanceTable({ rows, by }: { rows: HoursBalanceDto[]; by: View }) {
  return (
    <StaticTable
      ariaLabel="Hours balances"
      rows={rows}
      getRowId={(b) => `${b.customer_id}-${b.machine_id}`}
      columns={[
        by === 'customer'
          ? {
              id: 'machine',
              header: 'Machine',
              render: (b) => machineText(b.machine_code, b.machine_name, b.machine_id),
            }
          : {
              id: 'customer',
              header: 'Customer',
              render: (b) => nameOr(b.customer_name, b.customer_id),
            },
        { id: 'purchases', header: 'Purchases', align: 'right', render: (b) => b.purchases },
        {
          id: 'await',
          header: 'Awaiting activation',
          align: 'right',
          render: (b) => hoursText(b.awaiting_activation),
        },
        { id: 'act', header: 'Activated', align: 'right', render: (b) => hoursText(b.activated) },
        {
          id: 'in',
          header: 'Transferred in',
          align: 'right',
          render: (b) => hoursText(b.transferred_in),
        },
        {
          id: 'out',
          header: 'Transferred out',
          align: 'right',
          render: (b) => hoursText(b.transferred_out),
        },
        { id: 'used', header: 'Used', align: 'right', render: (b) => hoursText(b.consumed) },
        { id: 'exp', header: 'Expired', align: 'right', render: (b) => hoursText(b.expired) },
        { id: 'rev', header: 'Reversed', align: 'right', render: (b) => hoursText(b.reversed) },
        {
          id: 'rem',
          header: 'Remaining',
          align: 'right',
          render: (b) => <strong>{hoursText(b.remaining)}</strong>,
        },
      ]}
    />
  );
}

function CustomerBalances({ customer }: { customer: CustomerDto }) {
  const load = useCallback(
    async (signal: AbortSignal) => {
      const [balances, exposure] = await Promise.all([
        hoursService.customerBalances(customer.id, signal),
        hoursService.creditExposure(customer.id, undefined, signal),
      ]);
      return { balances, exposure };
    },
    [customer.id],
  );
  const res = useAsyncResource(load);
  return (
    <AsyncContent resource={res} errorTitle="Could not load the balances">
      {(d) => (
        <Stack spacing={2}>
          <Paper variant="outlined" className="p-3">
            <Typography variant="subtitle2" gutterBottom>
              Credit
            </Typography>
            <KeyValueGrid
              columns={3}
              items={[
                {
                  label: 'Approved limit',
                  value:
                    d.exposure.limit_amount === null ? (
                      'No credit arrangement'
                    ) : (
                      <MoneyText amount={d.exposure.limit_amount} currency={d.exposure.currency} />
                    ),
                },
                {
                  label: 'Used on credit, not yet paid',
                  value: <MoneyText amount={d.exposure.exposure} currency={d.exposure.currency} />,
                },
                {
                  label: 'Available',
                  value:
                    d.exposure.available === null ? (
                      '—'
                    ) : (
                      <MoneyText amount={d.exposure.available} currency={d.exposure.currency} />
                    ),
                },
              ]}
            />
          </Paper>
          {d.balances.length === 0 ? (
            <EmptyState title="No hours bought by this customer" />
          ) : (
            <BalanceTable rows={d.balances} by="customer" />
          )}
        </Stack>
      )}
    </AsyncContent>
  );
}

function MachineBalances({ machine }: { machine: MachineDto }) {
  const load = useCallback(
    (signal: AbortSignal) => hoursService.machineBalances(machine.id, signal),
    [machine.id],
  );
  const res = useAsyncResource(load);
  return (
    <AsyncContent
      resource={res}
      isEmpty={(rows) => rows.length === 0}
      emptyTitle="No customer hours on this machine"
      errorTitle="Could not load the balances"
    >
      {(rows) => <BalanceTable rows={rows} by="machine" />}
    </AsyncContent>
  );
}

/** Remaining customer hours per customer (by machine) or per machine (by customer). */
export function HoursBalancesPage() {
  const [view, setView] = useState<View>('customer');
  const [customer, setCustomer] = useState<CustomerDto | null>(null);
  const [machine, setMachine] = useState<MachineDto | null>(null);
  return (
    <>
      <PageHeader
        title="Hours balances"
        subtitle="Activated, used and remaining prepaid hours, derived from the hours ledger"
      />
      <Stack spacing={2}>
        <Box className="flex flex-wrap items-center gap-3">
          <ToggleButtonGroup
            exclusive
            size="small"
            value={view}
            aria-label="Balances by"
            onChange={(_e, v: View | null) => {
              if (v !== null) setView(v);
            }}
          >
            <ToggleButton value="customer">By customer</ToggleButton>
            <ToggleButton value="machine">By machine</ToggleButton>
          </ToggleButtonGroup>
          <Box sx={{ minWidth: 260 }}>
            {view === 'customer' ? (
              <CustomerFilter label="Customer" value={customer} onChange={setCustomer} />
            ) : (
              <MachineFilter label="Machine" value={machine} onChange={setMachine} />
            )}
          </Box>
        </Box>
        {view === 'customer' &&
          (customer === null ? (
            <EmptyState title="Choose a customer to see their hours" />
          ) : (
            <CustomerBalances key={customer.id} customer={customer} />
          ))}
        {view === 'machine' &&
          (machine === null ? (
            <EmptyState title="Choose a machine to see its customers’ hours" />
          ) : (
            <MachineBalances key={machine.id} machine={machine} />
          ))}
      </Stack>
    </>
  );
}
