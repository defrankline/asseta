import {
  Box,
  Button,
  Paper,
  Stack,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material';
import { useCallback, useEffect, useState } from 'react';
import { Link as RouterLink, useSearchParams } from 'react-router';
import { customerService } from '../../../api/services/customerService';
import type { HoursBalanceDto } from '../../../api/hoursTypes';
import { hoursService } from '../../../api/services/hoursService';
import type { CustomerDto, MachineDto } from '../../../api/types';
import { ExportMenu } from '../../../components/data/ExportMenu';
import { StaticTable } from '../../../components/data/StaticTable';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { MoneyText } from '../../../components/display/MoneyText';
import { AsyncContent } from '../../../components/feedback/AsyncContent';
import { EmptyState } from '../../../components/feedback/EmptyState';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { useAsyncResource } from '../../../hooks/useAsyncResource';
import { lowBalanceAlertsPath } from '../../../navigation/hoursRoutes';
import { customerDetailPath } from '../../../navigation/routes';
import { CustomerFilter, MachineFilter } from '../shared/financePickers';
import { machineText, nameOr } from '../shared/names';
import { CustomerHoursTable } from './creditInvoices/CustomerHoursTable';
import { hoursText } from './hoursDisplay';

type View = 'all' | 'customer' | 'machine';

function BalanceTable({ rows, by }: { rows: HoursBalanceDto[]; by: 'customer' | 'machine' }) {
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
          <Box className="flex flex-wrap gap-2">
            <Button component={RouterLink} to={customerDetailPath(customer.id)} size="small">
              Hours statement (customer page)
            </Button>
            <Button
              component={RouterLink}
              to={lowBalanceAlertsPath({ customer_id: customer.id })}
              size="small"
            >
              Low-balance warnings
            </Button>
          </Box>
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

/**
 * Customer hours: every customer's bought / used / left and credit owed, or one customer's hours per
 * machine, or one machine's hours per customer.
 */
export function HoursBalancesPage() {
  const [params, setParams] = useSearchParams();
  const urlCustomer = params.get('customer_id');
  const [view, setView] = useState<View>(urlCustomer === null ? 'all' : 'customer');
  const [customer, setCustomer] = useState<CustomerDto | null>(null);
  const [machine, setMachine] = useState<MachineDto | null>(null);
  useEffect(() => {
    if (urlCustomer === null) return undefined;
    const controller = new AbortController();
    customerService.get(urlCustomer, controller.signal).then(setCustomer, () => {
      // Not readable or gone: the customer is chosen by hand.
    });
    return () => {
      controller.abort();
    };
  }, [urlCustomer]);
  return (
    <>
      <PageHeader
        title="Hours balances"
        subtitle="Hours each customer bought, used and has left, and the credit they owe"
        actions={
          <ExportMenu
            reports={[
              {
                code: 'customer_hours',
                filters: { customer_id: view === 'customer' ? customer?.id : undefined },
              },
            ]}
          />
        }
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
            <ToggleButton value="all">All customers</ToggleButton>
            <ToggleButton value="customer">By customer</ToggleButton>
            <ToggleButton value="machine">By machine</ToggleButton>
          </ToggleButtonGroup>
          {view !== 'all' && (
            <Box sx={{ minWidth: 260 }}>
              {view === 'customer' ? (
                <CustomerFilter label="Customer" value={customer} onChange={setCustomer} />
              ) : (
                <MachineFilter label="Machine" value={machine} onChange={setMachine} />
              )}
            </Box>
          )}
        </Box>
        {view === 'all' && (
          <CustomerHoursTable
            onOpenCustomer={(customerId) => {
              setView('customer');
              setParams({ customer_id: customerId });
            }}
          />
        )}
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
