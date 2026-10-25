import Add from '@mui/icons-material/Add';
import { Box, Button } from '@mui/material';
import { useCallback, useState } from 'react';
import { useNavigate } from 'react-router';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { useMutationGuard } from '../../../access/useCanMutate';
import { engineHoursService } from '../../../api/services/engineHoursService';
import type { BaselineDto, MachineDto } from '../../../api/types';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import type { FetchPage } from '../../../components/data/useServerPage';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { StaticSelectFilter } from '../../../components/forms/StaticSelectFilter';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { recordPath } from '../../../navigation/recordRoutes';
import { useNotify } from '../../../notifications/useNotify';
import { formatInstantIn } from '../../../utils/time';
import { MachineFilter } from '../shared/financePickers';
import { PersonName } from '../shared/PersonName';
import { ProposeBaselineDialog } from './BaselineDialogs';
import { PROPOSAL_STATUS_OPTIONS } from './engineHoursDisplay';
import { baselineSource, machineOf, proposalChip, useBaselineKit } from './engineRecords';

/** Meter baselines and proposals: the approved starting reading of each machine's engine-hour ledger. */
export function MeterBaselinesPage() {
  const notify = useNotify();
  const timeZone = useDisplayTimeZone();
  const can = useMutationGuard();
  const [status, setStatus] = useState('PROPOSED');
  const [machine, setMachine] = useState<MachineDto | null>(null);
  const [proposing, setProposing] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const reload = () => {
    setReloadKey((k) => k + 1);
  };
  const navigate = useNavigate();
  const kit = useBaselineKit(reload);
  const fetchPage = useCallback<FetchPage<BaselineDto>>(
    (query, signal) => engineHoursService.listBaselines(query, signal),
    [],
  );
  const columns: DataColumn<BaselineDto>[] = [
    { id: 'machine', header: 'Machine', render: machineOf },
    {
      id: 'reading',
      header: 'Reading',
      align: 'right',
      render: (b) => <span className="font-mono">{b.reading}</span>,
    },
    { id: 'taken', header: 'Taken', render: (b) => formatInstantIn(b.captured_at, timeZone) },
    {
      id: 'source',
      header: 'Source',
      render: baselineSource,
    },
    {
      id: 'by',
      header: 'Proposed by',
      render: (b) => <PersonName userId={b.proposed_by} name={b.proposed_by_name} />,
    },
    { id: 'status', header: 'Status', render: proposalChip },
    { id: 'decide', header: '', align: 'right', render: kit.decideCell },
  ];
  return (
    <>
      <PageHeader
        title="Meter baselines"
        subtitle="The approved starting reading of each machine; engine hours are reconciled from it"
        actions={
          can(PERMISSIONS.tenantMeterCapture) ? (
            <Button
              variant="contained"
              startIcon={<Add />}
              onClick={() => {
                setProposing(true);
              }}
            >
              Propose baseline
            </Button>
          ) : undefined
        }
      />
      <ServerDataTable
        columns={columns}
        fetchPage={fetchPage}
        getRowId={(b) => b.id}
        searchPlaceholder="Search machine code or name"
        reloadKey={reloadKey}
        filters={{ status: status || undefined, machine_id: machine?.id }}
        emptyTitle={status === 'PROPOSED' ? 'No baselines awaiting a decision' : 'No baselines'}
        isRowMuted={(b) => b.status === 'REJECTED'}
        onRowClick={(b) => {
          void navigate(recordPath('METER_BASELINE', b.id));
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
      {proposing && (
        <ProposeBaselineDialog
          onClose={() => {
            setProposing(false);
          }}
          onProposed={() => {
            notify.success('Baseline proposed; a second person decides it.');
            reload();
          }}
        />
      )}
    </>
  );
}
