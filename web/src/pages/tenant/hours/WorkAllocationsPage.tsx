import { Alert, Box, Button, Chip } from '@mui/material';
import { useCallback, useState } from 'react';
import { Link as RouterLink, useSearchParams } from 'react-router';
import type { WorkExecutionAllocationDto } from '../../../api/hoursTypes';
import { hoursService } from '../../../api/services/hoursService';
import type { CustomerDto, MachineDto } from '../../../api/types';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import { StaticTable } from '../../../components/data/StaticTable';
import type { FetchPage } from '../../../components/data/useServerPage';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { hoursPurchasePath } from '../../../navigation/hoursRoutes';
import { exceptionsPath, jobDetailPath } from '../../../navigation/routes';
import { isZeroDecimal } from '../../../utils/money';
import { formatInstantIn } from '../../../utils/time';
import { CustomerFilter, MachineFilter } from '../shared/financePickers';
import { machineText, nameOr } from '../shared/names';
import { hoursText } from './hoursDisplay';

/** Allocation lines: which purchases a completed job drew its hours from (oldest first). */
function AllocationLines({ a, timeZone }: { a: WorkExecutionAllocationDto; timeZone: string }) {
  return (
    <StaticTable
      ariaLabel="Hours drawn from purchases"
      rows={a.lines}
      getRowId={(l) => l.entry_id}
      columns={[
        {
          id: 'purchase',
          header: 'Purchase',
          render: (l) => (
            <Button component={RouterLink} to={hoursPurchasePath(l.purchase_id)} size="small">
              {l.purchase_number}
            </Button>
          ),
        },
        { id: 'hours', header: 'Hours', align: 'right', render: (l) => hoursText(l.hours) },
        { id: 'at', header: 'When', render: (l) => formatInstantIn(l.occurred_at, timeZone) },
      ]}
    />
  );
}

/** Work-execution allocations: billable hours of completed prepaid jobs and any overrun. */
export function WorkAllocationsPage() {
  const timeZone = useDisplayTimeZone();
  const [params, setParams] = useSearchParams();
  const jobId = params.get('job_id') ?? undefined;
  const [customer, setCustomer] = useState<CustomerDto | null>(null);
  const [machine, setMachine] = useState<MachineDto | null>(null);
  const fetchPage = useCallback<FetchPage<WorkExecutionAllocationDto>>(
    (query, signal) => hoursService.listAllocations(query, signal),
    [],
  );
  const columns: DataColumn<WorkExecutionAllocationDto>[] = [
    {
      id: 'at',
      header: 'Allocated',
      sortField: 'created_at',
      render: (a) => formatInstantIn(a.created_at, timeZone),
    },
    {
      id: 'job',
      header: 'Job',
      render: (a) => (
        <Button component={RouterLink} to={jobDetailPath(a.job_id)} size="small">
          {a.job_number ?? 'Open job'}
        </Button>
      ),
    },
    { id: 'customer', header: 'Customer', render: (a) => nameOr(a.customer_name, a.customer_id) },
    {
      id: 'machine',
      header: 'Machine',
      render: (a) => machineText(a.machine_code, a.machine_name, a.machine_id),
    },
    {
      id: 'billable',
      header: 'Billable',
      align: 'right',
      render: (a) => hoursText(a.billable_hours),
    },
    { id: 'used', header: 'Covered', align: 'right', render: (a) => hoursText(a.consumed_hours) },
    {
      id: 'overrun',
      header: 'Not covered',
      align: 'right',
      render: (a) =>
        isZeroDecimal(a.overrun_hours) ? (
          '—'
        ) : (
          <Chip size="small" color="warning" label={hoursText(a.overrun_hours)} />
        ),
    },
    {
      id: 'review',
      header: 'Review',
      render: (a) =>
        a.exception_id === null ? (
          '—'
        ) : (
          <Button component={RouterLink} to={exceptionsPath(a.job_id)} size="small">
            {a.exception_status === 'OPEN' ? 'Requires review' : 'Reviewed'}
          </Button>
        ),
    },
  ];
  return (
    <>
      <PageHeader
        title="Work allocations"
        subtitle="Hours each completed prepaid job used, drawn from the customer’s oldest active purchases"
      />
      <Box className="flex flex-col gap-3">
        <Alert severity="info">
          Hours beyond what the customer had active are never used silently: they are flagged for
          review until new hours cover them.
        </Alert>
        {jobId !== undefined && (
          <Box>
            <Chip
              label="One job"
              onDelete={() => {
                const next = new URLSearchParams(params);
                next.delete('job_id');
                setParams(next);
              }}
            />
          </Box>
        )}
        <ServerDataTable
          columns={columns}
          fetchPage={fetchPage}
          getRowId={(a) => a.id}
          searchable={false}
          initialSort="-created_at"
          filters={{ job_id: jobId, customer_id: customer?.id, machine_id: machine?.id }}
          emptyTitle="No work allocations"
          renderDetail={(a) => <AllocationLines a={a} timeZone={timeZone} />}
          detailLabel={() => 'Show purchases used'}
          toolbar={
            <Box className="flex flex-wrap gap-3">
              <Box sx={{ minWidth: 240 }}>
                <CustomerFilter label="Customer" value={customer} onChange={setCustomer} />
              </Box>
              <Box sx={{ minWidth: 220 }}>
                <MachineFilter label="Machine" value={machine} onChange={setMachine} />
              </Box>
            </Box>
          }
        />
      </Box>
    </>
  );
}
