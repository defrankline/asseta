import { Box } from '@mui/material';
import { useCallback, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router';
import { PERMISSIONS } from '../../../access/permissionCodes';
import type { MachineReportDto } from '../../../api/machineReportTypes';
import { machineReportService } from '../../../api/services/machineReportService';
import type { CustomerDto, MachineDto } from '../../../api/types';
import { ExportMenu } from '../../../components/data/ExportMenu';
import { ServerDataTable } from '../../../components/data/ServerDataTable';
import type { FetchPage } from '../../../components/data/useServerPage';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { StaticSelectFilter } from '../../../components/forms/StaticSelectFilter';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { machineReportPath } from '../../../navigation/routes';
import { initialFilter } from '../../../navigation/urlFilters';
import { useSession } from '../../../session/useSession';
import { CustomerFilter, MachineFilter } from '../shared/financePickers';
import { urlPeriod } from '../shared/urlPeriod';
import { UrlPeriodChip } from '../shared/UrlPeriodChip';
import { REPORT_QUEUE_OPTIONS, REPORT_STATUS_OPTIONS } from './machineReportDisplay';
import { reportColumns } from './reportColumns';

/**
 * Approvals › Machine reports: reports waiting for a decision first (approvers), every report with
 * filters by status, machine, customer and period.
 */
export function MachineReportsPage() {
  const navigate = useNavigate();
  const timeZone = useDisplayTimeZone();
  const { hasPermission } = useSession();
  const approver = hasPermission(PERMISSIONS.tenantMachineReportApprove);
  const [params, setParams] = useSearchParams();
  const { dateFrom, dateTo } = urlPeriod(params);
  const [queue, setQueue] = useState(() =>
    initialFilter(params, 'queue', REPORT_QUEUE_OPTIONS, approver ? 'PENDING' : ''),
  );
  const [status, setStatus] = useState(() =>
    initialFilter(params, 'status', REPORT_STATUS_OPTIONS, ''),
  );
  const [machine, setMachine] = useState<MachineDto | null>(null);
  const [customer, setCustomer] = useState<CustomerDto | null>(null);
  const fetchPage = useCallback<FetchPage<MachineReportDto>>(
    (query, signal) => machineReportService.list(query, signal),
    [],
  );
  return (
    <>
      <PageHeader
        title="Machine reports"
        subtitle="Every engine hour accounted for: customers' hours and non-productive time, approved by someone other than the submitter"
        actions={
          <ExportMenu
            reports={[
              {
                code: 'machine_hours',
                filters: { machine_id: machine?.id, from: dateFrom, to: dateTo },
              },
            ]}
          />
        }
      />
      <ServerDataTable
        columns={reportColumns(timeZone, { submitter: true })}
        fetchPage={fetchPage}
        getRowId={(r) => r.id}
        searchPlaceholder="Search report number or machine"
        initialSort="-submitted_at"
        filters={{
          queue: queue === '' ? undefined : queue,
          status: status === '' ? undefined : status,
          machine_id: machine?.id,
          customer_id: customer?.id,
          date_from: dateFrom,
          date_to: dateTo,
        }}
        emptyTitle={queue === 'PENDING' ? 'No report is waiting for a decision' : 'No reports'}
        onRowClick={(r) => {
          void navigate(machineReportPath(r.id));
        }}
        toolbar={
          <Box className="flex flex-wrap items-center gap-2">
            <StaticSelectFilter
              label="Queue"
              value={queue}
              options={REPORT_QUEUE_OPTIONS}
              allLabel="All reports"
              onChange={setQueue}
            />
            <StaticSelectFilter
              label="Status"
              value={status}
              options={REPORT_STATUS_OPTIONS}
              allLabel="All statuses"
              onChange={setStatus}
            />
            <Box sx={{ minWidth: 200 }}>
              <MachineFilter label="Machine" value={machine} onChange={setMachine} />
            </Box>
            <Box sx={{ minWidth: 200 }}>
              <CustomerFilter label="Customer" value={customer} onChange={setCustomer} />
            </Box>
            <UrlPeriodChip params={params} setParams={setParams} />
          </Box>
        }
      />
    </>
  );
}
