import { Alert, Box, Checkbox, TextField, Typography } from '@mui/material';
import { useCallback, useEffect, useState } from 'react';
import type { DataColumn } from '../../../../components/data/ServerDataTable';
import { StaticTable } from '../../../../components/data/StaticTable';
import { MoneyText } from '../../../../components/display/MoneyText';
import { StatusChip } from '../../../../components/display/StatusChip';
import { AsyncContent } from '../../../../components/feedback/AsyncContent';
import { useAsyncResource } from '../../../../hooks/useAsyncResource';
import { useDebouncedValue } from '../../../../hooks/useDebouncedValue';
import { loadEligibleJobs, MAX_SUMMARIES, type EligibleJob } from './eligibleJobs';

interface EligibleJobsStepProps {
  customerId: string;
  selected: readonly string[];
  onChange: (jobIds: string[]) => void;
  /** Every job loaded so far (for the Review step). */
  onLoaded: (jobs: EligibleJob[]) => void;
  machineLabel: (id: string) => string;
  error?: string | undefined;
}

const currencyOf = (e: EligibleJob) => e.summary.charges?.currency ?? e.job.currency;

/**
 * The customer's COMPLETED jobs with server-priced charges. Only billing-ready jobs can be picked,
 * and one invoice holds one currency (other currencies are disabled once a job is picked).
 */
export function EligibleJobsStep({
  customerId,
  selected,
  onChange,
  onLoaded,
  machineLabel,
  error,
}: EligibleJobsStepProps) {
  const [search, setSearch] = useState('');
  const q = useDebouncedValue(search.trim(), 300);
  const load = useCallback(
    (signal: AbortSignal) => loadEligibleJobs(customerId, q, signal),
    [customerId, q],
  );
  const res = useAsyncResource(load);
  useEffect(() => {
    if (res.data !== null) onLoaded(res.data);
    // onLoaded only records what was loaded.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [res.data]);
  const rows = res.data ?? [];
  const pickedCurrency = rows.find((r) => selected.includes(r.job.id));
  const lockCurrency = pickedCurrency === undefined ? null : currencyOf(pickedCurrency);
  const toggle = (id: string) => {
    onChange(selected.includes(id) ? selected.filter((s) => s !== id) : [...selected, id]);
  };
  const columns: DataColumn<EligibleJob>[] = [
    {
      id: 'pick',
      header: '',
      render: (r) => (
        <Checkbox
          size="small"
          checked={selected.includes(r.job.id)}
          disabled={!r.billable || (lockCurrency !== null && currencyOf(r) !== lockCurrency)}
          slotProps={{ input: { 'aria-label': `Invoice job ${r.job.job_number}` } }}
          onChange={() => {
            toggle(r.job.id);
          }}
        />
      ),
    },
    { id: 'job', header: 'Job', render: (r) => <strong>{r.job.job_number}</strong> },
    { id: 'machine', header: 'Machine', render: (r) => machineLabel(r.job.machine_id) },
    { id: 'hours', header: 'Billable hours', render: (r) => r.summary.billable_hours ?? '—' },
    {
      id: 'ready',
      header: 'Billing',
      render: (r) =>
        r.billable ? (
          <StatusChip status="READY" tones={{ READY: 'success' }} label="Billing-ready" />
        ) : (
          <StatusChip
            status="BLOCKED"
            tones={{ BLOCKED: 'warning' }}
            label={`Not billable (${String(r.summary.blocking_exceptions)} blocking)`}
          />
        ),
    },
    {
      id: 'total',
      header: 'Charges (server)',
      align: 'right',
      render: (r) =>
        r.summary.charges == null ? (
          '—'
        ) : (
          <MoneyText amount={r.summary.charges.total} currency={r.summary.charges.currency} />
        ),
    },
  ];
  return (
    <Box className="flex flex-col gap-2">
      <Typography variant="body2" color="text.secondary">
        Charges come from each job’s summary (the single pricing source) and are copied onto the
        draft. Jobs already on another non-voided invoice are refused by the server
        (JOB_ALREADY_INVOICED).
      </Typography>
      <TextField
        size="small"
        label="Search job number"
        value={search}
        onChange={(e) => {
          setSearch(e.target.value);
        }}
      />
      {error !== undefined && <Alert severity="error">{error}</Alert>}
      {lockCurrency !== null && (
        <Alert severity="info">
          This invoice is in {lockCurrency}. Jobs in other currencies need their own invoice.
        </Alert>
      )}
      <AsyncContent
        resource={res}
        isEmpty={(r) => r.length === 0}
        emptyTitle="No completed jobs for this customer"
        emptyDescription="Jobs become invoiceable once COMPLETED and billing-ready."
        errorTitle="Could not load the customer’s jobs"
      >
        {(data) => (
          <>
            <StaticTable
              ariaLabel="Completed jobs"
              columns={columns}
              rows={data}
              getRowId={(r) => r.job.id}
              isRowMuted={(r) => !r.billable}
            />
            {data.length >= MAX_SUMMARIES && (
              <Typography variant="caption" color="text.secondary">
                Showing the first {MAX_SUMMARIES} jobs; search by job number to narrow.
              </Typography>
            )}
          </>
        )}
      </AsyncContent>
    </Box>
  );
}
