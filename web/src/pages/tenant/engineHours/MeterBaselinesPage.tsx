import Add from '@mui/icons-material/Add';
import { Box, Button } from '@mui/material';
import { useCallback, useState } from 'react';
import { Link as RouterLink } from 'react-router';
import { PERMISSIONS } from '../../../access/permissionCodes';
import { useMutationGuard } from '../../../access/useCanMutate';
import { engineHoursService } from '../../../api/services/engineHoursService';
import { meterService } from '../../../api/services/meterService';
import type { BaselineDto, MachineDto } from '../../../api/types';
import { ServerDataTable, type DataColumn } from '../../../components/data/ServerDataTable';
import type { FetchPage } from '../../../components/data/useServerPage';
import { KeyValueGrid } from '../../../components/display/KeyValueGrid';
import { StatusChip } from '../../../components/display/StatusChip';
import { PageHeader } from '../../../components/feedback/PageHeader';
import { StaticSelectFilter } from '../../../components/forms/StaticSelectFilter';
import { DetailsDrawer } from '../../../components/lifecycle/DetailsDrawer';
import { AttachmentPhoto } from '../../../components/meter/AttachmentPhoto';
import { useDisplayTimeZone } from '../../../hooks/useDisplayTimeZone';
import { engineHoursMachinePath } from '../../../navigation/routes';
import { useNotify } from '../../../notifications/useNotify';
import { formatInstantIn } from '../../../utils/time';
import { MachineFilter } from '../shared/financePickers';
import { PersonName } from '../shared/PersonName';
import { ProposeBaselineDialog } from './BaselineDialogs';
import { DecideBaselineDialog } from './DecideDialogs';
import {
  hoursText,
  PROPOSAL_STATUS_LABELS,
  PROPOSAL_STATUS_OPTIONS,
  PROPOSAL_STATUS_TONES,
} from './engineHoursDisplay';
import { DecideButton } from './MeterDecisionDialog';

const machineOf = (b: BaselineDto) =>
  b.machine_code == null
    ? `${b.machine_id.slice(0, 8)}…`
    : `${b.machine_code}${b.machine_name == null ? '' : ` · ${b.machine_name}`}`;

/** Meter baselines and proposals: the approved starting reading of each machine's engine-hour ledger. */
export function MeterBaselinesPage() {
  const notify = useNotify();
  const timeZone = useDisplayTimeZone();
  const can = useMutationGuard();
  const canDecide = can(PERMISSIONS.tenantMeterApprove);
  const [status, setStatus] = useState('PROPOSED');
  const [machine, setMachine] = useState<MachineDto | null>(null);
  const [viewing, setViewing] = useState<BaselineDto | null>(null);
  const [deciding, setDeciding] = useState<BaselineDto | null>(null);
  const [proposing, setProposing] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const reload = () => {
    setReloadKey((k) => k + 1);
  };
  const fetchPage = useCallback<FetchPage<BaselineDto>>(
    (query, signal) => engineHoursService.listBaselines(query, signal),
    [],
  );
  const decideAction = (b: BaselineDto) =>
    canDecide && b.status === 'PROPOSED' ? (
      <DecideButton
        proposedBy={b.proposed_by}
        onClick={() => {
          setViewing(null);
          setDeciding(b);
        }}
      />
    ) : null;
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
      render: (b) => (b.source === 'READING' ? 'Existing reading' : 'New reading'),
    },
    { id: 'by', header: 'Proposed by', render: (b) => <PersonName userId={b.proposed_by} /> },
    {
      id: 'status',
      header: 'Status',
      render: (b) => (
        <StatusChip
          status={b.status}
          tones={PROPOSAL_STATUS_TONES}
          label={PROPOSAL_STATUS_LABELS[b.status]}
        />
      ),
    },
    { id: 'decide', header: '', align: 'right', render: decideAction },
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
        onRowClick={setViewing}
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
      {viewing !== null && (
        <DetailsDrawer
          title={`Baseline · ${machineOf(viewing)}`}
          status={
            <StatusChip
              status={viewing.status}
              tones={PROPOSAL_STATUS_TONES}
              label={PROPOSAL_STATUS_LABELS[viewing.status]}
            />
          }
          actions={
            <Box className="flex flex-wrap gap-2">
              <Button component={RouterLink} to={engineHoursMachinePath(viewing.machine_id)}>
                Engine hours
              </Button>
              {decideAction(viewing)}
            </Box>
          }
          onClose={() => {
            setViewing(null);
          }}
        >
          <KeyValueGrid
            columns={2}
            items={[
              { label: 'Reading', value: hoursText(viewing.reading) },
              { label: 'Taken', value: formatInstantIn(viewing.captured_at, timeZone) },
              {
                label: 'Source',
                value: viewing.source === 'READING' ? 'Existing reading' : 'New reading',
              },
              { label: 'Note', value: viewing.note ?? '—' },
              { label: 'Proposed by', value: <PersonName userId={viewing.proposed_by} /> },
              { label: 'Proposed', value: formatInstantIn(viewing.proposed_at, timeZone) },
              { label: 'Decided by', value: <PersonName userId={viewing.decided_by} /> },
              { label: 'Decided', value: formatInstantIn(viewing.decided_at, timeZone) },
              { label: 'Decision note', value: viewing.decision_note ?? '—' },
              {
                label: 'GPS',
                value:
                  viewing.latitude === null || viewing.longitude === null
                    ? 'No fix'
                    : `${String(viewing.latitude)}, ${String(viewing.longitude)}${
                        viewing.accuracy_m === null ? '' : ` (±${String(viewing.accuracy_m)} m)`
                      }`,
              },
              {
                label: 'Photo',
                value:
                  viewing.photo_attachment_id === null ? (
                    'None'
                  ) : (
                    <AttachmentPhoto
                      attachmentId={viewing.photo_attachment_id}
                      fetchUrl={(id) => meterService.attachmentUrl(id)}
                      label="View photo"
                    />
                  ),
              },
            ]}
          />
        </DetailsDrawer>
      )}
      {deciding !== null && (
        <DecideBaselineDialog
          baseline={deciding}
          timeZone={timeZone}
          onClose={() => {
            setDeciding(null);
          }}
          onDecided={(b) => {
            notify.success(`Baseline ${PROPOSAL_STATUS_LABELS[b.status].toLowerCase()}.`);
            reload();
          }}
        />
      )}
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
