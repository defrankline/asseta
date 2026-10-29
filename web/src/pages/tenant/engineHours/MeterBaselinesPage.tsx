import Add from '@mui/icons-material/Add';
import { Box, Button, Chip, Paper, Tab, Tabs } from '@mui/material';
import { useCallback, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { useMutationGuard } from '../../../access/useCanMutate';
import { engineHoursService } from '../../../api/services/engineHoursService';
import type { BaselineDto, MachineDto, MachineEngineHoursSummaryDto } from '../../../api/types';
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
import type { ReadingMachine } from '../jobDetail/ConsoleCaptureDialog';
import { ProposeBaselineDialog } from './BaselineDialogs';
import { PROPOSAL_STATUS_OPTIONS } from './engineHoursDisplay';
import { baselineSource, machineOf, proposalChip, useBaselineKit } from './engineRecords';

const NO_BASELINE_FILTER = { status: 'NO_BASELINE' };

/** Machines whose engine-hour ledger has no approved starting reading yet, each with a Propose action. */
function MissingBaselinesTable({
  canPropose,
  reloadKey,
  onPropose,
}: {
  canPropose: boolean;
  reloadKey: number;
  onPropose: (machine: ReadingMachine) => void;
}) {
  const fetchPage = useCallback<FetchPage<MachineEngineHoursSummaryDto>>(
    (query, signal) => engineHoursService.listMachines(query, signal),
    [],
  );
  const columns: DataColumn<MachineEngineHoursSummaryDto>[] = [
    {
      id: 'machine',
      header: 'Machine',
      render: (m) => (
        <span>
          <strong>{m.machine_code}</strong> · {m.machine_name}
        </span>
      ),
    },
    {
      id: 'state',
      header: 'Baseline',
      render: (m) =>
        m.baseline_pending ? (
          <Chip size="small" variant="outlined" label="Awaiting decision" />
        ) : (
          'Not proposed yet'
        ),
    },
    {
      id: 'propose',
      header: '',
      align: 'right',
      render: (m) =>
        canPropose && !m.baseline_pending ? (
          <Button
            size="small"
            onClick={(e) => {
              e.stopPropagation();
              onPropose({ id: m.machine_id, label: `${m.machine_code} · ${m.machine_name}` });
            }}
          >
            Propose
          </Button>
        ) : null,
    },
  ];
  return (
    <ServerDataTable
      columns={columns}
      fetchPage={fetchPage}
      getRowId={(m) => m.machine_id}
      searchPlaceholder="Search machine code or name"
      reloadKey={reloadKey}
      filters={NO_BASELINE_FILTER}
      emptyTitle="Every machine has an approved baseline"
    />
  );
}

/** Meter baselines and proposals: the approved starting reading of each machine's engine-hour ledger. */
export function MeterBaselinesPage() {
  const notify = useNotify();
  const timeZone = useDisplayTimeZone();
  const can = useMutationGuard();
  const [status, setStatus] = useState('PROPOSED');
  const [machine, setMachine] = useState<MachineDto | null>(null);
  const [proposing, setProposing] = useState<ReadingMachine | 'choose' | null>(null);
  const [params, setParams] = useSearchParams();
  /** `?missing=true` (go-live checklist link): the machines still without an approved baseline. */
  const missing = params.get('missing') === 'true';
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
                setProposing('choose');
              }}
            >
              Propose baseline
            </Button>
          ) : undefined
        }
      />
      <Paper variant="outlined" className="mb-3">
        <Tabs
          value={missing ? 'missing' : 'proposals'}
          onChange={(_e, v: string) => {
            setParams(v === 'missing' ? { missing: 'true' } : {});
          }}
          aria-label="Meter baseline views"
        >
          <Tab value="proposals" label="Baselines and proposals" />
          <Tab value="missing" label="Machines without a baseline" />
        </Tabs>
      </Paper>
      {missing ? (
        <MissingBaselinesTable
          canPropose={can(PERMISSIONS.tenantMeterCapture)}
          reloadKey={reloadKey}
          onPropose={setProposing}
        />
      ) : (
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
      )}
      {kit.dialog}
      {proposing !== null && (
        <ProposeBaselineDialog
          {...(proposing === 'choose' ? {} : { machine: proposing })}
          onClose={() => {
            setProposing(null);
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
