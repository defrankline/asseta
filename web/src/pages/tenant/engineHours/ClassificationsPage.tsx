import { Box, Button } from '@mui/material';
import { useCallback, useState } from 'react';
import { Link as RouterLink, useNavigate } from 'react-router';
import { engineHoursService } from '../../../api/services/engineHoursService';
import type { ClassificationDto, MachineDto } from '../../../api/types';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import type { FetchPage } from '../../../components/data/useServerPage';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { StaticSelectFilter } from '../../../components/forms/StaticSelectFilter';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { recordPath } from '../../../navigation/recordRoutes';
import { ROUTES } from '../../../navigation/routes';
import { formatInstantIn } from '../../../utils/time';
import { MachineFilter } from '../shared/financePickers';
import { PersonName } from '../shared/PersonName';
import { OUTCOME_LABELS, PROPOSAL_STATUS_OPTIONS } from './engineHoursDisplay';
import { machineOf, proposalChip, useClassificationKit } from './engineRecords';

/** Explanations of unallocated engine hours (non-customer activity or identified variance) and their decisions. */
export function ClassificationsPage() {
  const timeZone = useDisplayTimeZone();
  const navigate = useNavigate();
  const [status, setStatus] = useState('PROPOSED');
  const [machine, setMachine] = useState<MachineDto | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const kit = useClassificationKit(() => {
    setReloadKey((k) => k + 1);
  });
  const fetchPage = useCallback<FetchPage<ClassificationDto>>(
    (query, signal) => engineHoursService.listClassifications(query, signal),
    [],
  );
  const columns: DataColumn<ClassificationDto>[] = [
    { id: 'machine', header: 'Machine', render: machineOf },
    {
      id: 'period',
      header: 'Period',
      render: (c) =>
        `${formatInstantIn(c.start_at, timeZone)} → ${formatInstantIn(c.end_at, timeZone)}`,
    },
    {
      id: 'hours',
      header: 'Hours',
      align: 'right',
      render: (c) => <span className="font-mono">{c.hours}</span>,
    },
    { id: 'outcome', header: 'Explained as', render: (c) => OUTCOME_LABELS[c.outcome] },
    { id: 'reason', header: 'Category / reason', render: (c) => c.reason_name ?? '—' },
    {
      id: 'by',
      header: 'Proposed by',
      render: (c) => <PersonName userId={c.proposed_by} name={c.proposed_by_name} />,
    },
    { id: 'status', header: 'Status', render: proposalChip },
    { id: 'decide', header: '', align: 'right', render: kit.decideCell },
  ];
  return (
    <>
      <PageHeader
        title="Hour explanations"
        subtitle="Unallocated engine hours explained as non-customer activity or an identified variance"
        actions={
          <Button
            component={RouterLink}
            to={ROUTES.tenantEngineHoursUnallocated}
            variant="outlined"
          >
            Hours to explain
          </Button>
        }
      />
      <ServerDataTable
        columns={columns}
        fetchPage={fetchPage}
        getRowId={(c) => c.id}
        searchPlaceholder="Search machine code or name"
        reloadKey={reloadKey}
        filters={{ status: status || undefined, machine_id: machine?.id }}
        emptyTitle={
          status === 'PROPOSED' ? 'No explanations awaiting a decision' : 'No explanations'
        }
        isRowMuted={(c) => c.status === 'REJECTED'}
        onRowClick={(c) => {
          void navigate(recordPath('ENGINE_HOURS_CLASSIFICATION', c.id));
        }}
        toolbar={
          <Box className="flex flex-1 flex-wrap items-center gap-3">
            <StaticSelectFilter
              label="Status"
              value={status}
              options={PROPOSAL_STATUS_OPTIONS}
              allLabel="All statuses"
              onChange={setStatus}
            />
            <Box sx={{ minWidth: 240 }}>
              <MachineFilter label="Machine" value={machine} onChange={setMachine} />
            </Box>
          </Box>
        }
      />
      {kit.dialog}
    </>
  );
}
