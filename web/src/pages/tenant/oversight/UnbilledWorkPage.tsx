import { Box, Button, Link, Typography } from '@mui/material';
import { useCallback, useState } from 'react';
import { Link as RouterLink, useNavigate } from 'react-router';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { useCanMutate } from '../../../access/useCanMutate';
import type { UnbilledJobDto } from '../../../api/oversightTypes';
import { oversightService } from '../../../api/services/oversightService';
import type { CustomerDto, JobSiteDto, MachineDto } from '../../../api/types';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import type { FetchPage } from '../../../components/data/useServerPage';
import { MoneyText } from '../../../components/display/MoneyText';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import {
  customerDetailPath,
  hireInvoiceDetailPath,
  jobDetailPath,
  machineDetailPath,
} from '../../../navigation/routes';
import { useNotify } from '../../../notifications/useNotify';
import { formatInstantIn } from '../../../utils/time';
import { CreateInvoiceDialog } from '../finance/invoices/CreateInvoiceDialog';
import { CustomerFilter, MachineFilter } from '../shared/financePickers';
import { JobSiteFilter } from '../shared/lookupPickers';
import { machineText, nameOr } from '../shared/names';

const stop = (e: { stopPropagation: () => void }) => {
  e.stopPropagation();
};

/**
 * Unbilled work (DEC-031 M2): completed, billing-ready jobs not on an issued invoice after the
 * company's days. Oldest first; each opens its job, a draft invoice when one holds it, or starts one.
 */
export function UnbilledWorkPage() {
  const timeZone = useDisplayTimeZone();
  const navigate = useNavigate();
  const notify = useNotify();
  const canInvoice = useCanMutate(PERMISSIONS.tenantFinanceInvoice);
  const [customer, setCustomer] = useState<CustomerDto | null>(null);
  const [machine, setMachine] = useState<MachineDto | null>(null);
  const [site, setSite] = useState<JobSiteDto | null>(null);
  const [invoicing, setInvoicing] = useState<UnbilledJobDto | null>(null);
  const fetchPage = useCallback<FetchPage<UnbilledJobDto>>(
    (query, signal) => oversightService.listUnbilledWork(query, signal),
    [],
  );
  const columns: DataColumn<UnbilledJobDto>[] = [
    {
      id: 'job',
      header: 'Job',
      render: (j) => (
        <Link component={RouterLink} to={jobDetailPath(j.job_id)} onClick={stop}>
          {nameOr(j.job_number, j.job_id)}
        </Link>
      ),
    },
    {
      id: 'customer',
      header: 'Customer',
      render: (j) => (
        <Link component={RouterLink} to={customerDetailPath(j.customer_id)} onClick={stop}>
          {nameOr(j.customer_name, j.customer_id)}
        </Link>
      ),
    },
    {
      id: 'machine',
      header: 'Machine',
      render: (j) => (
        <Link component={RouterLink} to={machineDetailPath(j.machine_id)} onClick={stop}>
          {machineText(j.machine_code, j.machine_name, j.machine_id)}
        </Link>
      ),
    },
    { id: 'site', header: 'Site', render: (j) => nameOr(j.job_site_name, j.job_site_id) },
    {
      id: 'supervisor',
      header: 'Supervisor',
      render: (j) => nameOr(j.supervisor_staff_name, j.supervisor_staff_id),
    },
    {
      id: 'completed',
      header: 'Completed',
      render: (j) => formatInstantIn(j.completed_at, timeZone),
    },
    { id: 'days', header: 'Days not invoiced', align: 'right', render: (j) => j.days_unbilled },
    {
      id: 'hours',
      header: 'Billable h',
      align: 'right',
      render: (j) => (j.billable_hours === null ? '—' : j.billable_hours),
    },
    {
      id: 'total',
      header: 'Worth',
      align: 'right',
      render: (j) =>
        j.total === null ? '—' : <MoneyText amount={j.total} currency={j.currency} />,
    },
    {
      id: 'invoice',
      header: 'Invoice',
      render: (j) =>
        j.draft_invoice_id !== null ? (
          <Box>
            <Link
              component={RouterLink}
              to={hireInvoiceDetailPath(j.draft_invoice_id)}
              onClick={stop}
            >
              Open draft invoice
            </Link>
            <Typography variant="caption" color="text.secondary" component="div">
              Not issued yet
            </Typography>
          </Box>
        ) : canInvoice ? (
          <Button
            size="small"
            variant="outlined"
            onClick={(e) => {
              e.stopPropagation();
              setInvoicing(j);
            }}
          >
            Create invoice
          </Button>
        ) : (
          '—'
        ),
    },
  ];
  return (
    <>
      <PageHeader
        title="Unbilled work"
        subtitle="Completed, billing-ready jobs not yet on an issued invoice after the company's set days"
      />
      <ServerDataTable
        columns={columns}
        fetchPage={fetchPage}
        getRowId={(j) => j.job_id}
        searchPlaceholder="Search job number or customer"
        filters={{
          customer_id: customer?.id,
          machine_id: machine?.id,
          site_id: site?.id,
        }}
        emptyTitle="No unbilled work"
        emptyDescription="Completed jobs ready to bill appear here once they pass the company's days without an issued invoice."
        onRowClick={(j) => {
          void navigate(jobDetailPath(j.job_id));
        }}
        toolbar={
          <Box className="flex flex-wrap gap-3">
            <Box sx={{ minWidth: 240 }}>
              <CustomerFilter label="Customer" value={customer} onChange={setCustomer} />
            </Box>
            <Box sx={{ minWidth: 220 }}>
              <MachineFilter label="Machine" value={machine} onChange={setMachine} />
            </Box>
            <Box sx={{ minWidth: 220 }}>
              <JobSiteFilter label="Site" value={site} onChange={setSite} />
            </Box>
          </Box>
        }
      />
      {invoicing !== null && (
        <CreateInvoiceDialog
          customerId={invoicing.customer_id}
          jobIds={[invoicing.job_id]}
          onClose={() => {
            setInvoicing(null);
          }}
          onCreated={(inv) => {
            notify.success('Draft invoice created.');
            void navigate(hireInvoiceDetailPath(inv.id));
          }}
        />
      )}
    </>
  );
}
